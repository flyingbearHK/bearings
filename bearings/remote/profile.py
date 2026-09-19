"""Profile remote Databricks tables on the SQL warehouse and keep the result in DuckDB `_meta`.

For each table:
1. `count(*)` (a Delta metadata read).
2. A sample (the whole table when it's small) streams into an in-memory DuckDB and goes through the
   same profiler as local tables: top values, patterns, histograms, PII hints, flags.
3. For tables bigger than the sample, one aggregate query per 25 columns gets the *exact* row, null
   and blank counts and min/max over the whole table, plus `approx_count_distinct`; columns that look
   unique get an exact `count(DISTINCT …)`, so key detection isn't fooled by the sample.
4. Key fingerprints: the distinct values of key-like columns (ids, codes, unique columns) are stored in
   `_meta.key_values`, so relationship discovery and value search work locally without the rows.

Only aggregates and a bounded sample leave the warehouse; the sample itself is discarded after profiling.
"""
from __future__ import annotations

import datetime as dt
import re
import time
from pathlib import Path

import duckdb

from .. import profiler
from ..db import META, connect, has_meta, qi, remote_aliases, ro, user_tables
from ..relationships import ID_SUFFIX
from . import RemoteError
from . import connections as cx
from .pull import build_sql
from .sync import remote_fq

DEFAULT_SAMPLE = 200_000
KEY_CAP = 500_000


def spark_family(t: str) -> str:
    u = (t or "").strip().upper()
    if re.match(r"^(ARRAY|MAP|STRUCT|VARIANT|BINARY|INTERVAL|OBJECT|GEOGRAPHY|GEOMETRY|VOID)", u):
        return "other"
    if u == "BOOLEAN":
        return "bool"
    if re.match(r"^(DATE|TIMESTAMP)", u):
        return "temporal"
    if re.match(r"^(STRING|VARCHAR|CHAR)", u):
        return "string"
    if re.match(r"^(TINYINT|SMALLINT|INT|INTEGER|BIGINT|LONG|SHORT|BYTE|FLOAT|DOUBLE|REAL|DECIMAL|DEC|NUMERIC)", u):
        return "numeric"
    return "other"


def bq(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _is_keyish(p: dict) -> bool:
    f = profiler.family(p["data_type"])
    if f not in ("string", "numeric") or re.match(r"^(FLOAT|DOUBLE|REAL)", p["data_type"], re.I):
        return False
    nn = (p["row_count"] or 0) - (p["null_count"] or 0)
    if nn <= 0 or not p["distinct_count"] or p["distinct_count"] < 2:
        return False
    return bool(ID_SUFFIX.search(p["column_name"])) or p["distinct_count"] / nn >= 0.98


def targets(db_path: Path, aliases: list[str] | None = None, tables: list[str] | None = None,
            only_new: bool = False, only_stale: bool = False) -> list[tuple[str, str]]:
    """Metadata-only remote tables to profile (pulled copies are profiled locally by `bearings profile`)."""
    with ro(db_path) as con:
        srcs = remote_aliases(con)
        if not srcs:
            return []
        rows = con.execute(f"SELECT alias, table_name FROM {META}.remote_tables WHERE NOT dropped ORDER BY 1, 2").fetchall()
        local = set(user_tables(con))
        if has_meta(con, "remote_cache"):  # a cached *sample* still needs the whole-table profile from Databricks
            local -= {(a, t) for a, t in con.execute(f"SELECT alias, table_name FROM {META}.remote_cache WHERE NOT complete").fetchall()}
        prof = {(s, t): bool(st) for s, t, st in con.execute(
            f"SELECT schema_name, table_name, coalesce(stale, false) FROM {META}.table_profile").fetchall()}
    out = []
    want = {t.lower() for t in tables or []}
    for a, t in rows:
        if a not in srcs or (a, t) in local:
            continue
        if aliases and a not in aliases:
            continue
        if want and f"{a}.{t}".lower() not in want:
            continue
        if only_new and (a, t) in prof:
            continue
        if only_stale and not prof.get((a, t), True):
            continue
        out.append((a, t))
    return out


def _exact_stats(cur, src: str, cols: list[tuple[str, str]]) -> dict[str, dict]:
    """One pass over the whole remote table per 25 columns: non-null, blank, approx distinct, min, max."""
    out: dict[str, dict] = {}
    for i in range(0, len(cols), 25):
        chunk = cols[i:i + 25]
        exprs = []
        for c, t in chunk:
            f, q = spark_family(t), bq(c)
            if f == "other":
                exprs += [f"count({q})", "NULL", "NULL", "NULL", "NULL"]
                continue
            exprs += [f"count({q})", f"approx_count_distinct({q})", f"CAST(min({q}) AS STRING)", f"CAST(max({q}) AS STRING)",
                      f"count_if(trim({q}) = '')" if f == "string" else "NULL"]
        # every expression needs its own name: Databricks returns Arrow, which rejects duplicate column names (e.g. several NULLs)
        cur.execute("SELECT " + ", ".join(f"{e} AS _c{k}" for k, e in enumerate(exprs)) + f" FROM {src}")
        row = list(cur.fetchone())
        for j, (c, t) in enumerate(chunk):
            nn, dist, lo, hi, blank = row[j * 5:(j + 1) * 5]
            out[c] = {"nn": int(nn or 0), "dist": None if dist is None else int(dist), "min": lo, "max": hi,
                      "blank": None if blank is None else int(blank)}
    return out


def _exact_distinct(cur, src: str, cols: list[str]) -> dict[str, int]:
    out = {}
    for i in range(0, len(cols), 25):
        chunk = cols[i:i + 25]
        cur.execute("SELECT " + ", ".join(f"count(DISTINCT {bq(c)}) AS _d{k}" for k, c in enumerate(chunk)) + f" FROM {src}")
        for c, n in zip(chunk, list(cur.fetchone())):
            out[c] = int(n or 0)
    return out


def _remote_key_values(cur, src: str, cols: list[str], cap: int) -> dict[str, list[str]]:
    """Distinct values of key columns straight from the warehouse (for tables bigger than the sample)."""
    out: dict[str, list[str]] = {c: [] for c in cols}
    for c in cols:
        q = bq(c)
        cur.execute(f"SELECT DISTINCT CAST({q} AS STRING) AS v FROM {src} WHERE {q} IS NOT NULL LIMIT {cap + 1}")
        while True:
            b = cur.fetchmany_arrow(100_000)
            if b is None or b.num_rows == 0:
                break
            out[c] += [x for x in b.column(0).to_pylist() if x is not None]
    return out


def widen_decimals(tbl):
    """Arrow DECIMAL(p,s) -> DECIMAL(38,s). Values from Databricks can exceed a column's declared precision
    (e.g. 183823530.0 in DECIMAL(18,10)); DuckDB then fails on arithmetic that stays in the declared type.
    Returns (table, {column: declared type} for columns whose values really exceed their declared precision)."""
    import pyarrow as pa
    import pyarrow.compute as pc
    fields, arrays, overflow = [], [], {}
    for f, col in zip(tbl.schema, tbl.columns):
        if pa.types.is_decimal(f.type) and f.type.precision < 38:
            wide = col.cast(pa.decimal128(38, f.type.scale))
            try:
                mx = pc.max(pc.abs(wide.cast(pa.float64()))).as_py()
            except Exception:
                mx = None
            if mx is not None and mx >= 10 ** (f.type.precision - f.type.scale):
                overflow[f.name] = f"DECIMAL({f.type.precision},{f.type.scale})"
            fields.append(pa.field(f.name, wide.type, f.nullable))
            arrays.append(wide)
        else:
            fields.append(f)
            arrays.append(col)
    return pa.Table.from_arrays(arrays, schema=pa.schema(fields)), overflow


def profile_table(db_path: Path, alias: str, table: str, sample_rows: int = DEFAULT_SAMPLE, top_n: int = 10,
                  key_cap: int = KEY_CAP, fingerprints: bool = True, echo=lambda *_: None) -> dict:
    t0 = time.time()
    with ro(db_path) as con:
        src_info = remote_aliases(con).get(alias)
        if not src_info:
            raise RemoteError(f"'{alias}' is not an attached remote schema")
        rcols = con.execute(f"SELECT column_name, data_type FROM {META}.remote_columns WHERE alias=? AND table_name=? ORDER BY ordinal",
                            [alias, table]).fetchall()
    if not rcols:
        raise RemoteError(f"No columns known for {alias}.{table} – run `bearings sync -s {alias}` first")
    conn = cx.get(src_info["connection"])
    src = remote_fq(src_info, table)
    step = "connect"
    from . import query as rq
    ctx = rq.cursor(conn.name)
    try:
        cur = ctx.__enter__()
        try:
            step = "count rows"
            cur.execute(f"SELECT count(*) FROM {src}")
            total = int(list(cur.fetchone())[0])
            sampled = total > sample_rows
            step = "read sample" if sampled else "read table"
            cur.execute(build_sql(src_info, table, sample_rows if sampled else None, None, total=total))
            sample = cur.fetchall_arrow()
            mem = duckdb.connect()
            try:
                step = "load sample into DuckDB"
                mem.execute(f"CREATE SCHEMA {qi(alias)}")
                sample, overflow = widen_decimals(sample)
                mem.register("_sample", sample)
                mem.execute(f"CREATE TABLE {qi(alias)}.{qi(table)} AS SELECT * FROM _sample")
                mem.unregister("_sample")
                step = "profile sample"
                tp, cols = profiler.profile_table(mem, alias, table, top_n=top_n)
                exact: dict = {}
                if sampled:
                    step = "whole-table statistics"
                    exact = _exact_stats(cur, src, rcols)
                    maybe_unique = [p["column_name"] for p in cols
                                    if (e := exact.get(p["column_name"])) and e["nn"] and e["dist"] is not None and e["dist"] >= 0.95 * e["nn"]]
                    exact_dist = _exact_distinct(cur, src, maybe_unique) if maybe_unique else {}
                    for p in cols:
                        e = exact.get(p["column_name"])
                        if not e:
                            continue
                        dist = exact_dist.get(p["column_name"], e["dist"] if e["dist"] is not None else p["distinct_count"])
                        p.update(row_count=total, null_count=total - e["nn"],
                                 null_pct=round(100.0 * (total - e["nn"]) / total, 2) if total else 0.0,
                                 distinct_count=dist, distinct_pct=round(100.0 * dist / e["nn"], 2) if e["nn"] else 0.0,
                                 blank_count=e["blank"] if e["blank"] is not None else p["blank_count"],
                                 min_val=profiler._trim(e["min"]) if e["min"] is not None else p["min_val"],
                                 max_val=profiler._trim(e["max"]) if e["max"] is not None else p["max_val"],
                                 approx=False)
                        p["flags"] = profiler.compute_flags(p, p["patterns"])
                    tp.update(row_count=total, sampled_rows=sample.num_rows,
                              candidate_keys=[p["column_name"] for p in cols if "candidate_pk" in p["flags"]])
                # key fingerprints
                keys: dict[str, list[str]] = {}
                complete: dict[str, bool] = {}
                if fingerprints:
                    step = "key fingerprints"
                    kc = [p["column_name"] for p in cols if _is_keyish(p) and p["distinct_count"] <= key_cap * 4]
                    if kc and not sampled:
                        for c in kc:
                            keys[c] = [r[0] for r in mem.execute(
                                f"SELECT DISTINCT CAST({qi(c)} AS VARCHAR) FROM {qi(alias)}.{qi(table)} WHERE {qi(c)} IS NOT NULL LIMIT {key_cap + 1}").fetchall()]
                    elif kc:
                        keys = _remote_key_values(cur, src, kc, key_cap)
                    for c in list(keys):
                        complete[c] = len(keys[c]) <= key_cap
                        keys[c] = keys[c][:key_cap]
                    if sampled:  # a complete fingerprint is an exact distinct count – better than the approximate one
                        for p in cols:
                            c = p["column_name"]
                            if complete.get(c) and p["distinct_count"] != len(keys[c]):
                                nn = p["row_count"] - p["null_count"]
                                p.update(distinct_count=len(keys[c]), distinct_pct=round(100.0 * len(keys[c]) / nn, 2) if nn else 0.0)
                                p["flags"] = profiler.compute_flags(p, p["patterns"])
                        tp["candidate_keys"] = [p["column_name"] for p in cols if "candidate_pk" in p["flags"]]
            finally:
                mem.close()
        except BaseException as e:
            ctx.__exit__(type(e), e, e.__traceback__)
            raise
        else:
            ctx.__exit__(None, None, None)
    except RemoteError:
        raise
    except Exception as e:  # say which step failed, so odd tables are diagnosable
        raise RemoteError(f"{step}: {str(e).splitlines()[0] if str(e) else type(e).__name__}") from e
    for p in cols:  # data-quality finding: values larger than the column's declared type allows
        if p["column_name"] in overflow:
            p["data_type"] = overflow[p["column_name"]]
            p["flags"].append("precision_overflow")
            tp.setdefault("errors", []).append(
                f"{p['column_name']}: values exceed its declared {overflow[p['column_name']]} (max {p['max_val']})")
    tp["column_count"] = len(rcols)
    _save(db_path, alias, table, tp, cols, keys, complete, {p["column_name"]: p["distinct_count"] for p in cols})
    return {"alias": alias, "table": table, "rows": total, "sampled_rows": sample.num_rows if sampled else None,
            "columns": len(cols), "candidate_keys": tp["candidate_keys"], "flagged": sum(1 for p in cols if p["flags"]),
            "fingerprints": len(keys), "seconds": round(time.time() - t0, 1), "errors": tp.get("errors", [])}


def _save(db_path, alias, table, tp, cols, keys, complete, dist):
    import pyarrow as pa
    now = dt.datetime.now().replace(microsecond=0)
    flat = [(c, v) for c, vs in keys.items() for v in vs]
    kv = pa.table({"schema_name": [alias] * len(flat), "table_name": [table] * len(flat),
                   "column_name": [c for c, _ in flat], "v": pa.array([v for _, v in flat], pa.string())})
    from .pull import _write_lock
    with _write_lock:  # parallel profiling: one DuckDB writer at a time
        _save_locked(db_path, alias, table, tp, cols, keys, complete, kv, flat, dist, now)


def _save_locked(db_path, alias, table, tp, cols, keys, complete, kv, flat, dist, now):
    con = connect(db_path, read_only=False, retries=5)
    try:
        con.execute("BEGIN TRANSACTION")
        profiler.save(con, tp, cols)
        from . import pii
        con.execute(f"DELETE FROM {META}.key_values WHERE schema_name=? AND table_name=?", [alias, table])
        con.execute(f"DELETE FROM {META}.key_fingerprint WHERE schema_name=? AND table_name=?", [alias, table])
        if flat:
            con.register("_kv", kv)
            con.execute(f"INSERT INTO {META}.key_values SELECT * FROM _kv")
            con.unregister("_kv")
        if keys:
            con.executemany(f"INSERT INTO {META}.key_fingerprint VALUES (?,?,?,?,?,?,?)",
                            [[alias, table, c, dist.get(c), len(vs), complete[c], now] for c, vs in keys.items()])
        pii.apply(con, db_path, alias, table, local_copy=False)  # masking on: no real PII values in the stored profile
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()


def fingerprinted(con) -> dict[tuple[str, str, str], bool]:
    """(schema, table, column) -> complete? for stored key fingerprints."""
    if not has_meta(con, "key_fingerprint"):
        return {}
    return {(s, t, c): bool(k) for s, t, c, k in con.execute(
        f"SELECT schema_name, table_name, column_name, complete FROM {META}.key_fingerprint").fetchall()}


def profile_many(db_path: Path, targets: list[tuple[str, str]], sample_rows: int = DEFAULT_SAMPLE, top_n: int = 10,
                 fingerprints: bool = True, echo=lambda *_: None) -> tuple[int, int]:
    """Profile several remote tables, 3 at a time on pooled warehouse sessions. Returns (ok, failed)."""
    from concurrent.futures import ThreadPoolExecutor

    from .pull import PARALLEL
    total = len(targets)
    done = {"n": 0}
    lock = __import__("threading").Lock()

    def one(t):
        a, tb = t
        try:
            r = profile_table(db_path, a, tb, sample_rows=sample_rows, top_n=top_n, fingerprints=fingerprints)
            with lock:
                done["n"] += 1
                smp = f" (sample {r['sampled_rows']:,})" if r["sampled_rows"] else ""
                echo(f"  ✓ [{done['n']}/{total}] {a}.{tb:<36} {r['rows']:>12,} rows{smp}  {r['columns']:>4} cols  "
                     f"PK: {', '.join(r['candidate_keys'][:2]) or '—':<22} {r['fingerprints']} key cols  {r['seconds']}s")
                for err in r.get("errors", [])[:5]:
                    echo(f"      ⚠ {err}")
            return True
        except Exception as e:
            with lock:
                done["n"] += 1
                echo(f"  ✗ [{done['n']}/{total}] {a}.{tb}: {str(e).splitlines()[0] if str(e) else type(e).__name__}")
            return False

    if not targets:
        return 0, 0
    first = [one(targets[0])]  # may wait for the warehouse to wake up
    with ThreadPoolExecutor(max_workers=max(1, PARALLEL)) as ex:
        res = first + list(ex.map(one, targets[1:]))
    return sum(res), len(res) - sum(res)
