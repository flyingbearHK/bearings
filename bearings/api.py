"""FastAPI app serving the JSON API and the built React UI."""
from __future__ import annotations

import datetime as dt
import decimal
import os
import re
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from . import catalog, export, profiler, relationships
from .db import META, DatabaseBusy, ann_connect, default_db_path, fq, qi, remote_aliases, ro

DB = default_db_path()
STATIC = Path(__file__).parent / "static"

@asynccontextmanager
async def _lifespan(_app):
    _warm_on_start()  # wake the remote SQL engine(s) (Databricks warehouses) in the background, if remote schemas are attached
    yield


from . import __version__  # noqa: E402

app = FastAPI(title="Bearings", version=__version__, lifespan=_lifespan)


@app.exception_handler(DatabaseBusy)
async def busy(_: Request, e: DatabaseBusy):
    return JSONResponse({"detail": "Database is busy (a `bearings load/profile/relate` is running). Try again when it finishes."}, status_code=503)


def _remote_error_handler():
    try:
        from .remote import RemoteError
    except Exception:  # pragma: no cover
        return

    @app.exception_handler(RemoteError)
    async def remote_error(_: Request, e):  # noqa: ANN001
        return JSONResponse({"detail": f"{getattr(e, 'platform', None) or 'Remote'}: {e}"}, status_code=400)


_remote_error_handler()


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


def remote_hint(schema: str, table: str, platform: str = "remote") -> str:
    return (f"{schema}.{table} is a {platform} table – its rows aren't in the local database. Profile it remotely "
            f"(⚡ Profile / bearings profile -t {schema}.{table}), or copy a sample with:  bearings pull {schema}.{table} --rows 100000")


def _use_remote(tb, remote: bool) -> bool:
    """Local first: a cached (or local) table runs in DuckDB unless Remote is asked for; a table that isn't
    cached can only run remotely."""
    return catalog.is_remote(tb) or bool(remote and tb.get("remote"))


def _source(tb, remote_used: bool) -> dict:
    if remote_used:
        return {"source": "remote", "platform": (tb.get("remote") or {}).get("platform")}
    if tb.get("storage") == "sample":
        c = (tb.get("remote") or {}).get("cache") or {}
        return {"source": "sample", "cached_rows": c.get("rows"), "total_rows": c.get("total")}
    return {"source": tb.get("storage") or "local"}


def _local_or_409(tb):
    """Row-level features need the rows in DuckDB (live remote queries are a later phase)."""
    if catalog.is_remote(tb):
        raise HTTPException(409, remote_hint(tb["schema"], tb["table"], (tb.get("remote") or {}).get("platform") or "remote"))
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
    with ro(DB) as con:
        srcs = remote_aliases(con)
    for a, src in srcs.items():  # attached schemas show up even before their first table syncs
        per[a] = {"schema": a, "tables": 0, "columns": 0, "rows": 0}
    for t in full["tables"].values():
        d = per.setdefault(t["schema"], {"schema": t["schema"], "tables": 0, "columns": 0, "rows": 0})
        d["tables"] += 1
        d["columns"] += len(t["columns"])
        d["rows"] += t["row_count"] or 0
    from .remote.connectors import platform
    for a, src in srcs.items():
        p = platform(src["connection"])
        per[a].update(kind="remote", connection=src["connection"], catalog=src["catalog"], remote_schema=src["schema"],
                      platform=p["label"], compute_label=p["compute_label"],
                      synced_at=str(src["synced_at"]) if src["synced_at"] else None)
    for d in per.values():
        d.setdefault("kind", "local")
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
           schemas: str | None = None, remote: bool = False, max_remote: int = 50):
    """remote=true (value mode): also scan remote tables in scope live on their platform (one query per table)."""
    if not q.strip():
        return {"query": q, "mode": mode, "has_column_matches": False, "tables": []}
    if match not in ("exact", "contains", "fuzzy"):
        raise HTTPException(400, "match must be exact, contains or fuzzy")
    with ro(DB) as con:
        cat = catalog.scoped(catalog.build(con, DB), catalog.parse_schemas(schemas))
        t0 = time.time()
        res = (catalog.search_values(con, cat, q, exact=exact) if mode == "value"
               else catalog.search(cat, q, match=match, columns_only=columns_only))
    if mode == "value":  # hits in a cached sample may miss rows that only exist remotely
        for t in res["tables"]:
            if t.get("storage") == "sample":
                t["partial"] = True
                for m in t["matched_columns"]:
                    m["matched_by"] = "value (cached sample)"
    if mode == "value" and remote:
        from .remote import query as rq
        rem = [tb for tb in cat["tables"].values() if catalog.is_remote(tb) or tb.get("storage") == "sample"]
        todo = rem[:max(1, min(max_remote, 200))]
        live = {}
        found, errors = rq.value_search_many(todo, q.strip(), exact)  # DuckDB released; tables in parallel
        for tb in todo:
            hits = found.get((tb["schema"], tb["table"]))
            if hits:
                by = {c["column"]: c for c in tb["columns"]}
                matched = [{**catalog._col_summary(by[h["column"]]), "score": 100, "matched_by": f"value (live on {tb['remote'].get('platform') or 'remote'})",
                            "hits": h["hits"], "examples": h["examples"], "live": True} for h in hits]
                matched.sort(key=lambda x: -x["hits"])
                live[(tb["schema"], tb["table"])] = {**catalog._table_summary(tb), "score": 100, "table_score": 0, "table_matched_by": None,
                                                     "matched_columns": matched, "hits": sum(m["hits"] for m in matched), "live": True}
        res["tables"] = [t for t in res["tables"] if (t["schema"], t["table"]) not in {(x["schema"], x["table"]) for x in todo}] + list(live.values())
        res["tables"].sort(key=lambda x: -x["hits"])
        res.update(has_column_matches=bool(res["tables"]), remote_searched=len(todo) - len(errors), remote_errors=errors,
                   remote_not_searched=len(rem) - len(todo), skipped_remote=0, searched_remote_cached=0)
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
           where: str | None = None, seed: int | None = None, remote: bool = False):
    n = max(1, min(n, 1000))
    with ro(DB) as con:
        cat = catalog.build(con, DB)
        tb = _table_or_404(cat, schema, table)
    valid = {c["column"] for c in tb["columns"]}
    cols = [c for c in (columns.split(",") if columns else []) if c in valid] or [c["column"] for c in tb["columns"]]
    if _use_remote(tb, remote):  # live on the SQL warehouse
        from .remote import query as rq
        r = rq.sample(tb["remote"], tb["remote"]["table"], cols, n, [c for c in (nonnull.split(",") if nonnull else []) if c in valid],
                      where, seed, tb.get("row_count"))
        types = {c["column"]: c["type"] for c in tb["columns"]}
        return jsonable({"columns": r["columns"], "types": [types.get(c, t) for c, t in zip(r["columns"], r["types"])],
                         "rows": r["rows"], "sql": r["sql"], "remote": True, "elapsed_ms": r["elapsed_ms"], **_source(tb, True)})
    with ro(DB) as con:
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
    return jsonable({"columns": cols, "types": [types[c] for c in cols], "rows": rows, "sql": sql, **_source(tb, False)})


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
        _local_or_409(cat["tables"][(schema, table)])
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
    if _use_remote(tb, bool(body.get("remote"))):
        from .remote import query as rq
        r = rq.uniqueness(tb["remote"], tb["remote"]["table"], cols)
        return jsonable({"columns": cols, **r, "is_unique": r["rows"] == r["distinct"] and r["rows_with_nulls"] == 0, "remote": True,
                         **_source(tb, True)})
    with ro(DB) as con:
        key = ", ".join(qi(c) for c in cols)
        rows, distinct, nulls = con.execute(
            f"""SELECT count(*), (SELECT count(*) FROM (SELECT DISTINCT {key} FROM {fq(schema, table)})),
                       count(*) FILTER (WHERE {' OR '.join(f'{qi(c)} IS NULL' for c in cols)}) FROM {fq(schema, table)}""").fetchone()
        dups = con.execute(f"""SELECT {key}, count(*) n FROM {fq(schema, table)} GROUP BY ALL HAVING count(*) > 1 ORDER BY n DESC LIMIT 10""").fetchall()
    return jsonable({"columns": cols, "rows": rows, "distinct": distinct, "rows_with_nulls": nulls,
                     "is_unique": rows == distinct and nulls == 0, "duplicate_examples": [list(d) for d in dups], **_source(tb, False)})


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
            res.update(_source(tb, _use_remote(tb, bool(body.get("remote")))))
            if _use_remote(tb, bool(body.get("remote"))):  # run after the DuckDB connection is released
                res.update(remote=True, _remote=(tb["remote"], tb["remote"]["table"], [(c, types[c]) for c in cols]))
                out.append(res)
                continue
            parts, params = [], []
            masked = set(((tb.get("remote") or {}).get("cache") or {}).get("masked") or [])
            salt_ = None
            if masked & set(cols) and op in ("=", "!="):
                r_ = con.execute(f"SELECT value FROM {META}.settings WHERE key='pii_salt'").fetchone()
                salt_ = r_[0] if r_ else None
            for c in cols:
                vals = values
                if salt_ and c in masked:  # the cache holds hashed PII: hash the typed value the same way
                    from .remote.pii import mask_value
                    vals = [mask_value(v, salt_, "@" in v) for v in values]
                cond, p = _cond(c, types[c], op, vals)
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
    for res in out:
        if "_remote" in res:
            from .remote import query as rq
            src, tbl_name, cols_t = res.pop("_remote")
            try:
                res.update(rq.lookup(src, tbl_name, cols_t, op, values, limit))
            except Exception as e:
                res.update(error=f"{getattr(e, 'platform', None) or src.get('platform') or 'Remote'}: {str(e).splitlines()[0]}", count=0, rows=[])
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
        tl, tr = _table_or_404(cat, ls, lt), _table_or_404(cat, rs, rt)
        local = {(s_, t_) for (s_, t_), tb in cat["tables"].items() if not catalog.is_remote(tb)}
        try:
            a, m = relationships.overlap(con, ls, lt, lc, rs, rt, rc, local=local)
            b, m2 = relationships.overlap(con, rs, rt, rc, ls, lt, lc, local=local)
            a_sql, a_p, a_full = relationships._values(con, ls, lt, lc, local)
            b_sql, b_p, b_full = relationships._values(con, rs, rt, rc, local)
        except relationships.NoValues as e:
            raise HTTPException(409, f"{e} is a remote column without a key fingerprint. Profile its table remotely first "
                                     f"(bearings profile -t {e.args[0].rsplit('.', 1)[0]}) or pull it.")
        orphans = [r[0] for r in con.execute(
            f"SELECT v FROM ({a_sql}) WHERE v NOT IN (SELECT v FROM ({b_sql})) LIMIT 10", a_p + b_p).fetchall()]
    via = [f"{x['schema']}.{x['table']}" for x in (tl, tr) if catalog.is_remote(x)]
    return {"left": left, "right": right, "left_distinct": a, "left_in_right": m,
            "left_in_right_pct": round(100 * m / a, 2) if a else 0, "right_distinct": b, "right_in_left": m2,
            "right_in_left_pct": round(100 * m2 / b, 2) if b else 0, "left_orphans": orphans,
            "name_score": relationships.name_score(lc, rt, rc),
            "via_fingerprints": via, "complete": a_full and b_full}


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
    engine = body.get("engine") or "duckdb"
    if engine != "duckdb" and ":" in engine:  # "<type>:<connection>", e.g. databricks:dev (or remote:dev)
        from .remote import query as rq
        with ro(DB) as con:
            srcs = remote_aliases(con)
        return jsonable(rq.console(engine.split(":", 1)[1], sql, srcs, limit))
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
            msg = str(e)
            if "does not exist" in msg:
                aliases = remote_aliases(con)
                hit = next((a for a in aliases if re.search(rf"\b{re.escape(a)}\s*\.", sql, re.I)), None)
                if hit:
                    from .remote.connectors import platform
                    lbl = platform(aliases[hit]["connection"])["label"]
                    msg += (f"\n\n'{hit}' is a remote {lbl} schema: its rows aren't in the local database. "
                            f"Switch the engine to {lbl} to query it live, or copy a sample with  bearings pull {hit}.<table> --rows 100000")
            raise HTTPException(400, msg)
    truncated = len(rows) > limit
    return jsonable({"columns": cols, "types": types, "rows": rows[:limit], "truncated": truncated,
                     "elapsed_ms": round((time.time() - t0) * 1000)})


# ---------------------------------------------------------------- background jobs (load, remote sync / profile / pull)
_jobs: dict[str, dict] = {}
_jobs_lock = threading.Lock()


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    return jsonable(job)


# ---------------------------------------------------------------- add data from the app (local files)
LOCAL_CLIENTS = {"127.0.0.1", "::1", "localhost", "testclient"}


def _local_only(request: Request):
    """Reading paths on this machine is for the person at it: refuse when the app is served to others (--host 0.0.0.0)."""
    host = request.client.host if request.client else ""
    if host not in LOCAL_CLIENTS and os.environ.get("BEARINGS_ALLOW_REMOTE_PATHS") != "1":
        raise HTTPException(403, "Loading from a path works only in a browser on the machine running Bearings – drop the files instead")


def _load_source(request: Request, body: dict) -> tuple[Path, bool]:
    from . import ingest
    if body.get("upload"):
        try:
            d = ingest.upload_dir(DB, body["upload"])
        except ValueError as e:
            raise HTTPException(400, str(e))
        if not d.exists():
            raise HTTPException(404, "Upload not found (it may have been removed)")
        while True:  # a dropped folder: load the folder itself (its name suggests the schema)
            kids = [k for k in d.iterdir() if not k.name.startswith(".")]
            if len(kids) == 1 and kids[0].is_dir():
                d = kids[0]
                continue
            return d, True
    raw = (body.get("path") or "").strip().strip('"').strip("'")
    if not raw:
        raise HTTPException(400, "Give a file or folder path, or drop files")
    _local_only(request)
    p = Path(os.path.expanduser(raw))
    if not p.exists():
        raise HTTPException(404, f"Not found: {p}")
    return p, False


def _load_opts(body: dict):
    from .loaders import LoadOptions
    sheets = body.get("sheets") or []
    if isinstance(sheets, str):
        sheets = [x.strip() for x in sheets.split(",") if x.strip()]
    hr = body.get("header_row")
    return LoadOptions(all_varchar=bool(body.get("all_varchar")), delim=body.get("delim") or None, sheets=sheets,
                       header_row=int(hr) if hr not in (None, "") else None)


@app.get("/api/load/formats")
def load_formats():
    from .loaders import readers
    return [{"name": r.name, "label": r.label, "extensions": list(r.extensions), "available": r.available(),
             "folder_as_table": r.folder_as_table} for r in readers()]


@app.get("/api/load/ls")
def load_ls(request: Request, path: str | None = None):
    """Folder picker: sub-folders and loadable files of a folder on this machine."""
    from . import ingest
    _local_only(request)
    try:
        return ingest.listdir(path)
    except (FileNotFoundError, PermissionError) as e:
        raise HTTPException(404, str(e))


@app.post("/api/load/upload")
async def load_upload(request: Request, batch: str, name: str):
    """Receive one dropped file (raw body) into data/uploads/<batch>/<name>. A dropped folder keeps its sub-folders,
    so a folder of part-files still becomes one table."""
    from . import ingest
    try:
        dest = ingest.upload_dir(DB, batch) / ingest.safe_relpath(name)
    except ValueError as e:
        raise HTTPException(400, str(e))
    dest.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(dest, "wb") as f:
        async for chunk in request.stream():
            f.write(chunk)
            n += len(chunk)
    return {"batch": batch, "name": str(ingest.safe_relpath(name)), "bytes": n}


@app.post("/api/load/preview")
def load_preview(request: Request, body: dict = Body(...)):
    """What loading `path` (or an upload batch) would create. body = {path | upload, sheets?, header_row?}"""
    from . import ingest
    src, is_upload = _load_source(request, body)
    try:
        res = ingest.preview(src, _load_opts(body), is_upload=is_upload)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    if is_upload:  # show the dropped names, not the server-side folder
        root = str(src) + os.sep
        for it in res["items"]:
            it["source"] = it["source"].replace(root, "")
        res["comments_display"] = [c.replace(root, "") for c in res["comments"]]
        res["path"] = None
    existing = set()
    if DB.exists():
        with ro(DB) as con:
            existing = {(s_, t) for s_, t in con.execute(
                "SELECT table_schema, table_name FROM information_schema.tables WHERE table_catalog = current_database()").fetchall()}
    res["existing"] = sorted(f"{s_}.{t}" for s_, t in existing)
    return jsonable(res)


def _run_load_job(job_id: str, src: Path, schema: str, opts, body: dict):
    from . import ingest
    job = _jobs[job_id]
    try:
        comments = [c for c in body.get("comments") or [] if Path(c).resolve().is_relative_to(src.resolve())] if src.is_dir() \
            else [c for c in body.get("comments") or [] if Path(c) == src]
        res = ingest.run(DB, src, schema, opts, mode="append" if body.get("mode") == "append" else "replace",
                         tables=body.get("tables"), comments=comments, profile=body.get("profile", True) is not False,
                         relate=body.get("relate", True) is not False, progress=lambda p: job.update(p))
        job["results"] = res["loaded"]
        job["errors"] = res["errors"]
        job["summary"] = {k: res[k] for k in ("schema", "comments", "profiled", "relationships", "seconds")}
        job["status"] = "failed" if res["errors"] and not res["loaded"] else "done"
    except Exception as e:  # noqa: BLE001 - report anything to the UI
        job["errors"].append({"table": "", "error": str(e).splitlines()[0] if str(e) else type(e).__name__})
        job["status"] = "failed"
    catalog._cache["key"] = None
    job.update(current=None, finished_at=dt.datetime.now().isoformat(timespec="seconds"))


@app.post("/api/load")
def load_data(request: Request, body: dict = Body(...)):
    """Load files into DuckDB in the background, then profile them and look for relationships.
    body = {path | upload, schema, mode?: replace|append, tables?: [...], comments?: [...], all_varchar?, delim?,
            sheets?, header_row?, profile?: true, relate?: true, wait?: false}"""
    src, _ = _load_source(request, body)
    schema = (body.get("schema") or "").strip() or "main"
    if schema.startswith("_") or schema.lower() in ("information_schema", "pg_catalog"):
        raise HTTPException(400, f"'{schema}' is reserved – pick another schema name")
    with ro(DB) if DB.exists() else _nullctx() as con:
        if con is not None and schema in remote_aliases(con):
            raise HTTPException(400, f"'{schema}' is an attached remote schema – load into another schema")
    with _jobs_lock:
        if any(j["status"] == "running" and j.get("kind") == "load" for j in _jobs.values()):
            raise HTTPException(409, "Another load is still running – wait for it to finish")
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {"id": job_id, "kind": "load", "schema": schema, "status": "running", "phase": "load", "current": None,
                         "done": 0, "total": 0, "results": [], "errors": [], "started_at": dt.datetime.now().isoformat(timespec="seconds")}
    args = (job_id, src, schema, _load_opts(body), body)
    if body.get("wait"):
        _run_load_job(*args)
    else:
        threading.Thread(target=_run_load_job, args=args, daemon=True).start()
    return jsonable(_jobs[job_id])


class _nullctx:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


# ---------------------------------------------------------------- remote sources (connectors: Databricks, …)


def _remote_enabled() -> bool:
    """Is at least one remote connector's extra installed?"""
    from .remote.connectors import any_installed
    return any_installed()


@app.get("/api/remote")
def remote_overview():
    """Attached remote schemas, known connection profiles and running sync jobs."""
    from .remote import connections as cx
    from .remote import connectors
    try:
        conns = [c.connector.public_info() for c in cx.load_all().values()]
    except Exception as e:  # a broken connections.toml shouldn't break the app
        conns, err = [], str(e)
    else:
        err = None
    sources = []
    if DB.exists():
        with ro(DB) as con:
            srcs = remote_aliases(con)
            counts = {}
            if srcs:
                counts = {a: (n, d) for a, n, d in con.execute(
                    f"SELECT alias, count(*) FILTER (WHERE NOT dropped), count(*) FILTER (WHERE dropped) FROM {META}.remote_tables GROUP BY 1").fetchall()}
                last = {a: n for a, n in con.execute(
                    f"""SELECT alias, count(*) FROM {META}.sync_log l
                        WHERE synced_at = (SELECT max(synced_at) FROM {META}.sync_log WHERE alias = l.alias) GROUP BY 1""").fetchall()}
            prof = {a: (n, st) for a, n, st in con.execute(
                f"SELECT schema_name, count(*), count(*) FILTER (WHERE coalesce(stale, false)) FROM {META}.table_profile GROUP BY 1").fetchall()} \
                if srcs else {}
            for a, src in srcs.items():
                n, d = counts.get(a, (0, 0))
                pn, ps = prof.get(a, (0, 0))
                sources.append({**src, "tables": n, "dropped_tables": d, "last_sync_changes": last.get(a, 0),
                                "profiled": pn, "stale": ps})
    with _jobs_lock:
        running = [j for j in _jobs.values() if j["status"] == "running"]
    types = [{"type": t, "label": cls.label, "installed": cls.installed(), "extra": cls.extra} for t, cls in connectors.types().items()]
    return jsonable({"enabled": _remote_enabled(), "connections": conns, "connections_error": err, "types": types,
                     "sources": sources, "running_jobs": running})


def _run_sync_job(job_id: str, aliases: list[str], dry_run: bool):
    from .remote import sync as rsync
    job = _jobs[job_id]
    for a in aliases:
        job["current"] = a
        try:
            job["results"].append(rsync.sync(DB, a, dry_run=dry_run))
        except Exception as e:
            job["errors"].append({"alias": a, "error": str(e).splitlines()[0] if str(e) else type(e).__name__})
    job.update(status="failed" if job["errors"] and not job["results"] else "done", current=None,
               finished_at=dt.datetime.now().isoformat(timespec="seconds"))


@app.post("/api/remote/sync")
def remote_sync(body: dict = Body(default={})):
    """Re-sync remote metadata. body = {aliases?: [...], catalog?: str, connection?: str, dry_run?: bool, wait?: bool}.
    Runs in the background (returns a job id) unless wait=true."""
    from .remote import RemoteError
    from .remote import sync as rsync
    try:
        aliases = rsync.aliases_for(DB, body.get("aliases") or None, body.get("catalog"), body.get("connection"))
    except RemoteError as e:
        raise HTTPException(400, str(e))
    if not aliases:
        raise HTTPException(400, "No attached remote schemas match")
    with _jobs_lock:
        busy = [j for j in _jobs.values() if j["status"] == "running" and j.get("kind") == "sync" and set(j["aliases"]) & set(aliases)]
        if busy:
            return jsonable(busy[0])
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {"id": job_id, "kind": "sync", "aliases": aliases, "status": "running", "current": None, "results": [], "errors": [],
                         "dry_run": bool(body.get("dry_run")), "started_at": dt.datetime.now().isoformat(timespec="seconds")}
    if body.get("wait"):
        _run_sync_job(job_id, aliases, bool(body.get("dry_run")))
    else:
        threading.Thread(target=_run_sync_job, args=(job_id, aliases, bool(body.get("dry_run"))), daemon=True).start()
    return jsonable(_jobs[job_id])


def _run_profile_job(job_id: str, targets: list[tuple[str, str]], sample_rows: int | None):
    from .remote import profile as rprofile
    job = _jobs[job_id]
    for a, t in targets:
        job["current"] = f"{a}.{t}"
        try:
            job["results"].append(rprofile.profile_table(DB, a, t, sample_rows=sample_rows or rprofile.DEFAULT_SAMPLE))
        except Exception as e:
            job["errors"].append({"alias": f"{a}.{t}", "error": str(e).splitlines()[0] if str(e) else type(e).__name__})
        job["done"] = len(job["results"]) + len(job["errors"])
    job.update(status="failed" if job["errors"] and not job["results"] else "done", current=None,
               finished_at=dt.datetime.now().isoformat(timespec="seconds"))


@app.post("/api/remote/profile")
def remote_profile(body: dict = Body(default={})):
    """Profile metadata-only remote tables on the SQL warehouse (background job).
    body = {aliases?: [...], tables?: ["alias.table"], only_new?: bool, only_stale?: bool, sample_rows?: int, wait?: bool}"""
    from .remote import profile as rprofile
    targets = rprofile.targets(DB, body.get("aliases") or None, body.get("tables") or None,
                               bool(body.get("only_new")), bool(body.get("only_stale")))
    if not targets:
        raise HTTPException(400, "Nothing to profile (no matching metadata-only remote tables)")
    keys = [f"{a}.{t}" for a, t in targets]
    with _jobs_lock:
        busy = [j for j in _jobs.values() if j["status"] == "running" and j.get("kind") == "profile" and set(j["aliases"]) & set(keys)]
        if busy:
            return jsonable(busy[0])
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {"id": job_id, "kind": "profile", "aliases": keys, "total": len(keys), "done": 0, "status": "running",
                         "current": None, "results": [], "errors": [], "started_at": dt.datetime.now().isoformat(timespec="seconds")}
    args = (job_id, targets, body.get("sample_rows"))
    if body.get("wait"):
        _run_profile_job(*args)
    else:
        threading.Thread(target=_run_profile_job, args=args, daemon=True).start()
    return jsonable(_jobs[job_id])


def _run_pull_job(job_id: str, targets: list[str], rows: int | None, use_policy: bool = False):
    from .remote import pull as rpull
    job = _jobs[job_id]
    for ref in targets:
        job["current"] = ref
        try:
            if use_policy:  # the schema's cache setting: whole up to N rows, an N-row sample of bigger tables
                r = rpull.cache(DB, aliases=[ref.split(".", 1)[0]], tables=[ref], refresh=True)
                if r and "error" in r[0]:
                    raise RuntimeError(r[0]["error"])
                job["results"] += r
            else:
                job["results"].append(rpull.pull(DB, ref, rows=rows))
        except Exception as e:
            job["errors"].append({"alias": ref, "error": str(e).splitlines()[0] if str(e) else type(e).__name__})
        job["done"] = len(job["results"]) + len(job["errors"])
    catalog._cache["key"] = None
    job.update(status="failed" if job["errors"] and not job["results"] else "done", current=None,
               finished_at=dt.datetime.now().isoformat(timespec="seconds"))


@app.post("/api/remote/pull")
def remote_pull(body: dict = Body(...)):
    """Copy remote tables into DuckDB (background job). body = {tables: ["alias.table"], rows?: N (random sample),
    cache?: true (use the schema's cache setting instead of rows)}"""
    targets = [t for t in body.get("tables") or [] if "." in t]
    if not targets:
        raise HTTPException(400, "Give tables as alias.table")
    with _jobs_lock:
        busy = [j for j in _jobs.values() if j["status"] == "running" and j.get("kind") == "pull" and set(j["aliases"]) & set(targets)]
        if busy:
            return jsonable(busy[0])
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {"id": job_id, "kind": "pull", "aliases": targets, "total": len(targets), "done": 0, "status": "running",
                         "current": None, "results": [], "errors": [], "started_at": dt.datetime.now().isoformat(timespec="seconds")}
    args = (job_id, targets, body.get("rows"), bool(body.get("cache")))
    if body.get("wait"):
        _run_pull_job(*args)
    else:
        threading.Thread(target=_run_pull_job, args=args, daemon=True).start()
    return jsonable(_jobs[job_id])


@app.post("/api/remote/warm")
def remote_warm(body: dict = Body(default={})):
    """Wake the SQL warehouse(s) behind the attached schemas (or one connection) in the background."""
    from .remote import query as rq
    conns = _warehouse_connections(body.get("connection"))
    return {c: rq.warm(c) for c in conns}


@app.get("/api/remote/warm")
def remote_warm_status():
    from .remote import query as rq
    return {c: rq.warm_status(c) for c in _warehouse_connections(None)}


def _warehouse_connections(only: str | None) -> list[str]:
    if not _remote_enabled() or not DB.exists():
        return []
    from .remote import connections as cx
    with ro(DB) as con:
        used = {s_["connection"] for s_ in remote_aliases(con).values()}
    try:
        conns = cx.load_all()
    except Exception:
        return []
    return [c for c in sorted(used) if c in conns and conns[c].connector.can_query() and (not only or c == only)]


def _warm_on_start():
    if os.environ.get("BEARINGS_REMOTE_WARM", "1") == "0":
        return
    try:
        from .remote import query as rq
        for c in _warehouse_connections(None):
            rq.warm(c)
    except Exception:  # never block the app from starting
        pass


@app.get("/api/remote/jobs/{job_id}")
def remote_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "No such job")
    return jsonable(job)


@app.get("/api/remote/changes")
def remote_changes(alias: str | None = None, limit: int = 200):
    from .remote import sync as rsync
    if not DB.exists():
        return []
    with ro(DB) as con:
        return jsonable(rsync.recent_changes(con, alias, max(1, min(limit, 5000))))


@app.get("/api/annotations/orphans")
def annotation_orphans(schemas: str | None = None):
    """Annotations whose column (or remote table) no longer exists, with remap suggestions."""
    from . import orphans
    with ro(DB) as con:
        cat = catalog.build(con, DB)
        aliases = set(remote_aliases(con))
    return jsonable(orphans.find(cat, catalog.annotations(DB), aliases, catalog.parse_schemas(schemas)))


@app.post("/api/annotations/remap")
def annotation_remap(body: dict = Body(...)):
    """body = {schema, table, column, new_column, new_table?}"""
    from . import orphans
    try:
        res = orphans.remap(DB, body["schema"], body["table"], body.get("column", ""), body["new_column"], body.get("new_table"))
    except KeyError as e:
        raise HTTPException(404 if "No annotation" in str(e) else 400, str(e).strip("'\""))
    except ValueError as e:
        raise HTTPException(409, str(e))
    catalog._cache["key"] = None
    return res


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
