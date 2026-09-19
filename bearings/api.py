"""FastAPI app serving the JSON API and the built React UI."""
from __future__ import annotations

import datetime as dt
import decimal
import os
import re
import time
import uuid
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from . import catalog, export, profiler, relationships
from .db import META, DatabaseBusy, ann_connect, default_db_path, fq, qi, ro

DB = default_db_path()
STATIC = Path(__file__).parent / "static"

app = FastAPI(title="Bearings", version="0.1.0")


@app.exception_handler(DatabaseBusy)
async def busy(_: Request, e: DatabaseBusy):
    return JSONResponse({"detail": "Database is busy (a `bearings load/profile/relate` is running). Try again when it finishes."}, status_code=503)


def jsonable(v):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return None if v != v or v in (float("inf"), float("-inf")) else v
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.datetime, dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return str(v)
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (bytes, bytearray, memoryview)):
        b = bytes(v)
        return "0x" + b[:32].hex() + ("…" if len(b) > 32 else "")
    if isinstance(v, dict):
        return {str(k): jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple, set)):
        return [jsonable(x) for x in v]
    return str(v)


def _table_or_404(cat, schema, table):
    tb = cat["tables"].get((schema, table))
    if not tb:
        raise HTTPException(404, f"Table {schema}.{table} not found")
    return tb


# ---------------------------------------------------------------- catalog / search
def _default_scope():
    return [x for x in os.environ.get("BEARINGS_SCHEMAS", "").split(",") if x]


@app.get("/api/stats")
def stats(schemas: str | None = None):
    if not DB.exists():
        return {"db": str(DB), "exists": False, "tables": 0, "columns": 0, "profiled": 0, "relationships": 0,
                "schemas": [], "default_scope": _default_scope()}
    sc = catalog.parse_schemas(schemas)
    with ro(DB) as con:
        full = catalog.build(con, DB)
        rels = export.relationships(con)
    cat = catalog.scoped(full, sc)
    ts = cat["tables"].values()
    per = {}
    for t in full["tables"].values():
        d = per.setdefault(t["schema"], {"schema": t["schema"], "tables": 0, "columns": 0, "rows": 0})
        d["tables"] += 1
        d["columns"] += len(t["columns"])
        d["rows"] += t["row_count"] or 0
    rel = sum(1 for r in rels if not sc or (r["from_schema"] in sc and r["to_schema"] in sc))
    return {"db": str(DB), "exists": True, "tables": len(ts), "columns": sum(len(t["columns"]) for t in ts),
            "profiled": sum(1 for t in ts if t["profiled"]), "relationships": rel,
            "schemas": sorted(per), "schema_stats": [per[k] for k in sorted(per)], "default_scope": _default_scope()}


@app.get("/api/tables")
def tables(schemas: str | None = None):
    with ro(DB) as con:
        cat = catalog.scoped(catalog.build(con, DB), catalog.parse_schemas(schemas))
    return [catalog._table_summary(t) | {"matched_columns": [], "table_score": 0, "score": 0} for t in cat["tables"].values()]


@app.get("/api/search")
def search(q: str, mode: str = "name", exact: bool = False, match: str = "fuzzy", columns_only: bool = False,
           schemas: str | None = None):
    if not q.strip():
        return {"query": q, "mode": mode, "has_column_matches": False, "tables": []}
    if match not in ("exact", "contains", "fuzzy"):
        raise HTTPException(400, "match must be exact, contains or fuzzy")
    with ro(DB) as con:
        cat = catalog.scoped(catalog.build(con, DB), catalog.parse_schemas(schemas))
        t0 = time.time()
        res = (catalog.search_values(con, cat, q, exact=exact) if mode == "value"
               else catalog.search(cat, q, match=match, columns_only=columns_only))
    res["elapsed_ms"] = round((time.time() - t0) * 1000)
    return jsonable(res)


@app.get("/api/table/{schema}/{table}")
def table_detail(schema: str, table: str):
    with ro(DB) as con:
        cat = catalog.build(con, DB)
        tb = _table_or_404(cat, schema, table)
        tprof, cprof = profiler.load_profile(con, schema, table)
        rels = [r for r in export.relationships(con)
                if (r["from_schema"], r["from_table"]) == (schema, table) or (r["to_schema"], r["to_table"]) == (schema, table)]
    cols = []
    for c in tb["columns"]:
        cols.append({**c, "profile": cprof.get(c["column"])})
    return jsonable({**{k: v for k, v in tb.items() if k != "columns"}, "columns": cols, "table_profile": tprof, "relationships": rels})


@app.get("/api/table/{schema}/{table}/sample")
def sample(schema: str, table: str, n: int = 20, columns: str | None = None, nonnull: str | None = None,
           where: str | None = None, seed: int | None = None):
    n = max(1, min(n, 1000))
    with ro(DB) as con:
        cat = catalog.build(con, DB)
        tb = _table_or_404(cat, schema, table)
        valid = {c["column"] for c in tb["columns"]}
        cols = [c for c in (columns.split(",") if columns else []) if c in valid] or [c["column"] for c in tb["columns"]]
        conds = [f"{qi(c)} IS NOT NULL" for c in (nonnull.split(",") if nonnull else []) if c in valid]
        if where:
            if re.search(r";|\b(insert|update|delete|drop|create|alter|attach|copy|install|load|pragma|set)\b", where, re.I):
                raise HTTPException(400, "Only a simple filter expression is allowed")
            conds.append(f"({where})")
        wh = f"WHERE {' AND '.join(conds)}" if conds else ""
        seed_sql = f" REPEATABLE ({int(seed)})" if seed is not None else ""
        sql = f"SELECT {', '.join(qi(c) for c in cols)} FROM {fq(schema, table)} {wh} USING SAMPLE {n} ROWS (reservoir){seed_sql}"
        try:
            cur = con.execute(sql)
        except Exception as e:
            raise HTTPException(400, str(e).split("\n")[0])
        rows = cur.fetchall()
        types = {c["column"]: c["type"] for c in tb["columns"]}
    return jsonable({"columns": cols, "types": [types[c] for c in cols], "rows": rows, "sql": sql})


@app.get("/api/table/{schema}/{table}/profile")
def table_profile(schema: str, table: str, live: bool = False, column: str | None = None, sample_rows: int | None = None):
    with ro(DB) as con:
        cat = catalog.build(con, DB)
        _table_or_404(cat, schema, table)
        if not live:
            tp, cp = profiler.load_profile(con, schema, table)
            if column:
                if column in cp:
                    return jsonable({"stored": True, "table": tp, "columns": [cp[column]]})
                live = True  # fall through to live compute for that column
            else:
                return jsonable({"stored": tp is not None, "table": tp, "columns": list(cp.values())})
        t0 = time.time()
        tp, cols = profiler.profile_table(con, schema, table, columns=[column] if column else None, sample_rows=sample_rows)
    return jsonable({"stored": False, "live": True, "elapsed_ms": round((time.time() - t0) * 1000), "table": tp, "columns": cols})


@app.get("/api/table/{schema}/{table}/export.md", response_class=PlainTextResponse)
def table_md(schema: str, table: str):
    with ro(DB) as con:
        cat = catalog.build(con, DB)
        _table_or_404(cat, schema, table)
        return export.markdown(con, cat, schema, table)


@app.post("/api/table/{schema}/{table}/uniqueness")
def uniqueness(schema: str, table: str, body: dict = Body(...)):
    cols = body.get("columns") or []
    with ro(DB) as con:
        cat = catalog.build(con, DB)
        tb = _table_or_404(cat, schema, table)
        valid = {c["column"] for c in tb["columns"]}
        cols = [c for c in cols if c in valid]
        if not cols:
            raise HTTPException(400, "Pick at least one column")
        key = ", ".join(qi(c) for c in cols)
        rows, distinct, nulls = con.execute(
            f"""SELECT count(*), (SELECT count(*) FROM (SELECT DISTINCT {key} FROM {fq(schema, table)})),
                       count(*) FILTER (WHERE {' OR '.join(f'{qi(c)} IS NULL' for c in cols)}) FROM {fq(schema, table)}""").fetchone()
        dups = con.execute(f"""SELECT {key}, count(*) n FROM {fq(schema, table)} GROUP BY ALL HAVING count(*) > 1 ORDER BY n DESC LIMIT 10""").fetchall()
    return jsonable({"columns": cols, "rows": rows, "distinct": distinct, "rows_with_nulls": nulls,
                     "is_unique": rows == distinct and nulls == 0, "duplicate_examples": [list(d) for d in dups]})


# ---------------------------------------------------------------- multi-table lookup
OPS = {"=", "!=", ">", "<", ">=", "<=", "~"}


def _cond(col: str, dtype: str, op: str, values: list[str]) -> tuple[str, list]:
    fam = profiler.family(dtype)
    q = qi(col)
    if op == "~":
        return f"CAST({q} AS VARCHAR) ILIKE ?", [f"%{values[0]}%"]
    if fam == "string":
        if op in ("=", "!="):
            ph = ", ".join("lower(?)" for _ in values)
            return f"lower(trim({q})) {'NOT ' if op == '!=' else ''}IN ({ph})", values
        return f"{q} {op} ?", [values[0]]
    if fam == "numeric":
        if op in ("=", "!="):
            ph = ", ".join("TRY_CAST(? AS DOUBLE)" for _ in values)
            return f"{q} {'NOT ' if op == '!=' else ''}IN ({ph})", values
        return f"{q} {op} TRY_CAST(? AS DOUBLE)", [values[0]]
    if fam == "temporal":
        if op in ("=", "!="):
            ors = " OR ".join(f"CAST({q} AS VARCHAR) LIKE ?" for _ in values)
            return (f"NOT ({ors})" if op == "!=" else f"({ors})"), [v + "%" for v in values]
        return f"{q} {op} TRY_CAST(? AS TIMESTAMP)", [values[0]]
    if op in ("=", "!="):
        ph = ", ".join("?" for _ in values)
        return f"lower(CAST({q} AS VARCHAR)) {'NOT ' if op == '!=' else ''}IN ({ph})", [v.lower() for v in values]
    return f"CAST({q} AS VARCHAR) {op} ?", [values[0]]


@app.post("/api/lookup")
def lookup(body: dict = Body(...)):
    """Query several tables at once: WHERE <matched column(s)> <op> <value>.
    body = {targets: [{schema, table, columns: [...]}], op: '=', value: '9401', limit: 100}
    '=' / '!=' accept a comma-separated list (IN). '~' means contains."""
    op = body.get("op", "=")
    if op not in OPS:
        raise HTTPException(400, f"op must be one of {sorted(OPS)}")
    raw = str(body.get("value", "")).strip()
    if raw == "":
        raise HTTPException(400, "Enter a value")
    values = [v.strip().strip("'\"") for v in raw.split(",")] if op in ("=", "!=") else [raw.strip("'\"")]
    values = [v for v in values if v != ""]
    limit = max(1, min(int(body.get("limit") or 100), 5000))
    out = []
    with ro(DB) as con:
        cat = catalog.build(con, DB)
        for tg in body.get("targets") or []:
            tb = cat["tables"].get((tg.get("schema"), tg.get("table")))
            if not tb:
                continue
            types = {c["column"]: c["type"] for c in tb["columns"]}
            cols = [c for c in (tg.get("columns") or []) if c in types]
            pii = [c["column"] for c in tb["columns"]
                   if any(f.startswith("pii_") for f in (c.get("flags") or []))
                   or re.search(r"\bpii\b", ((c.get("annotation") or {}).get("tags") or ""), re.I)]
            res = {"schema": tb["schema"], "table": tb["table"], "match_columns": cols, "pii_columns": pii,
                   "row_count": tb.get("row_count"), "candidate_keys": tb.get("candidate_keys") or [],
                   "columns": [c["column"] for c in tb["columns"]], "types": [c["type"] for c in tb["columns"]]}
            if not cols:
                res.update(error="No matching column in this table", count=0, rows=[])
                out.append(res)
                continue
            parts, params = [], []
            for c in cols:
                cond, p = _cond(c, types[c], op, values)
                parts.append(cond)
                params += p
            where = " OR ".join(f"({x})" for x in parts)
            src = fq(tb["schema"], tb["table"])
            t0 = time.time()
            try:
                n = con.execute(f"SELECT count(*) FROM {src} WHERE {where}", params).fetchone()[0]
                rows = con.execute(f"SELECT * FROM {src} WHERE {where} LIMIT {limit}", params).fetchall() if n else []
                shown_where = where
                for prm in params:
                    shown_where = shown_where.replace("?", "'" + str(prm).replace("'", "''") + "'", 1)
                res.update(count=n, rows=rows, sql=f"SELECT *\nFROM {src}\nWHERE {shown_where}",
                           elapsed_ms=round((time.time() - t0) * 1000))
            except Exception as e:
                res.update(error=str(e).split("\n")[0], count=0, rows=[])
            out.append(res)
    return jsonable({"op": op, "values": values, "limit": limit, "results": out})


# ---------------------------------------------------------------- relationships
@app.get("/api/relationships")
def rels(schema: str | None = None, table: str | None = None, schemas: str | None = None):
    sc = catalog.parse_schemas(schemas)
    with ro(DB) as con:
        rs = export.relationships(con)
    if sc:
        rs = [r for r in rs if r["from_schema"] in sc and r["to_schema"] in sc]
    if table:
        rs = [r for r in rs if table in (r["from_table"], r["to_table"]) and (not schema or schema in (r["from_schema"], r["to_schema"]))]
    return jsonable(rs)


def _split(ref: str):
    parts = ref.split(".")
    if len(parts) != 3:
        raise HTTPException(400, "Use schema.table.column")
    return parts


@app.get("/api/overlap")
def overlap(left: str, right: str):
    ls, lt, lc = _split(left)
    rs, rt, rc = _split(right)
    with ro(DB) as con:
        cat = catalog.build(con, DB)
        _table_or_404(cat, ls, lt)
        _table_or_404(cat, rs, rt)
        a, m = relationships.overlap(con, ls, lt, lc, rs, rt, rc)
        b, m2 = relationships.overlap(con, rs, rt, rc, ls, lt, lc)
        orphans = [r[0] for r in con.execute(
            f"""SELECT DISTINCT CAST({qi(lc)} AS VARCHAR) v FROM {fq(ls, lt)} WHERE {qi(lc)} IS NOT NULL
                AND CAST({qi(lc)} AS VARCHAR) NOT IN (SELECT CAST({qi(rc)} AS VARCHAR) FROM {fq(rs, rt)} WHERE {qi(rc)} IS NOT NULL) LIMIT 10""").fetchall()]
    return {"left": left, "right": right, "left_distinct": a, "left_in_right": m,
            "left_in_right_pct": round(100 * m / a, 2) if a else 0, "right_distinct": b, "right_in_left": m2,
            "right_in_left_pct": round(100 * m2 / b, 2) if b else 0, "left_orphans": orphans,
            "name_score": relationships.name_score(lc, rt, rc)}


# ---------------------------------------------------------------- annotations
ANN_FIELDS = ("tags", "cdm_entity", "cdm_attribute", "notes")


@app.get("/api/annotations")
def list_annotations(schemas: str | None = None):
    sc = catalog.parse_schemas(schemas)
    c = ann_connect(DB)
    try:
        rows = [dict(r) for r in c.execute("SELECT * FROM annotations ORDER BY schema_name, table_name, column_name").fetchall()]
        return [r for r in rows if not sc or r["schema_name"] in sc]
    finally:
        c.close()


@app.put("/api/annotations")
def put_annotation(body: dict = Body(...)):
    s, t, col = body.get("schema"), body.get("table"), body.get("column") or ""
    if not s or not t:
        raise HTTPException(400, "schema and table are required")
    vals = {k: (body.get(k) or "").strip() for k in ANN_FIELDS}
    if vals["tags"]:
        vals["tags"] = ", ".join(dict.fromkeys(x.strip() for x in vals["tags"].split(",") if x.strip()))
    c = ann_connect(DB)
    try:
        if not any(vals.values()):
            c.execute("DELETE FROM annotations WHERE schema_name=? AND table_name=? AND column_name=?", (s, t, col))
        else:
            c.execute("""INSERT INTO annotations (schema_name, table_name, column_name, tags, cdm_entity, cdm_attribute, notes, updated_at)
                         VALUES (?,?,?,?,?,?,?,?)
                         ON CONFLICT(schema_name, table_name, column_name) DO UPDATE SET
                           tags=excluded.tags, cdm_entity=excluded.cdm_entity, cdm_attribute=excluded.cdm_attribute,
                           notes=excluded.notes, updated_at=excluded.updated_at""",
                      (s, t, col, *[vals[k] for k in ANN_FIELDS], dt.datetime.now().isoformat(timespec="seconds")))
        c.commit()
    finally:
        c.close()
    return {"ok": True, "schema": s, "table": t, "column": col, **vals}


# ---------------------------------------------------------------- exports
@app.get("/api/export/catalog.xlsx")
def export_xlsx(schemas: str | None = None):
    sc = catalog.parse_schemas(schemas)
    with ro(DB) as con:
        data = export.excel(con, catalog.scoped(catalog.build(con, DB), sc), sc)
    name = f"dm_catalog_{'_'.join(sorted(sc)) + '_' if sc else ''}{dt.date.today():%Y%m%d}.xlsx"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.get("/api/export/catalog.json")
def export_json(schemas: str | None = None):
    sc = catalog.parse_schemas(schemas)
    with ro(DB) as con:
        data = export.as_json(con, catalog.scoped(catalog.build(con, DB), sc), sc)
    return Response(data, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="dm_catalog_{dt.date.today():%Y%m%d}.json"'})


# ---------------------------------------------------------------- ad-hoc SQL (read-only connection)
@app.post("/api/sql")
def run_sql(body: dict = Body(...)):
    sql = (body.get("sql") or "").strip().rstrip(";")
    limit = max(1, min(int(body.get("limit") or 1000), 10000))
    if not sql:
        raise HTTPException(400, "Empty query")
    if ";" in sql:
        raise HTTPException(400, "One statement at a time")
    if not re.match(r"^\s*(select|with|from|describe|show|summarize|explain|values|pivot|unpivot|table)\b", sql, re.I):
        raise HTTPException(400, "Read-only: SELECT / WITH / FROM / DESCRIBE / SHOW / SUMMARIZE / EXPLAIN only")
    with ro(DB) as con:
        t0 = time.time()
        try:
            cur = con.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            types = [str(d[1]) for d in cur.description] if cur.description else []
            rows = cur.fetchmany(limit + 1)
        except Exception as e:
            raise HTTPException(400, str(e))
    truncated = len(rows) > limit
    return jsonable({"columns": cols, "types": types, "rows": rows[:limit], "truncated": truncated,
                     "elapsed_ms": round((time.time() - t0) * 1000)})


# ---------------------------------------------------------------- UI
if (STATIC / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = STATIC / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(STATIC / "index.html")
else:
    @app.get("/", include_in_schema=False)
    def no_ui():
        return PlainTextResponse("UI not built. Run `npm install && npm run build` in web/ (or use `npm run dev`).")
