"""Live queries on the SQL warehouse for remote tables: sample rows, key check, multi-table lookup,
value search and the SQL console.

- One pooled connection per connection profile (sign-in and session setup happen once per server run);
  a lock serialises statements on it, and a broken connection is reopened once.
- Every statement runs with a session STATEMENT_TIMEOUT and a row cap; results come back as Arrow.
- SQL is written in Databricks dialect here (backtick identifiers, named `:p` parameters).
"""
from __future__ import annotations

import os
import re
import threading
import time
from contextlib import contextmanager

from . import RemoteError
from . import connections as cx
from .profile import bq, spark_family
from .sync import remote_fq

TIMEOUT_S = int(os.environ.get("BEARINGS_REMOTE_TIMEOUT", "120"))
READ_ONLY = re.compile(r"^\s*(select|with|describe|desc|show|explain|values|table)\b", re.I)
# a SELECT can't change anything; these only matter for `WITH … INSERT` and friends
FORBIDDEN = re.compile(r";|--|/\*|\b(insert|update|delete|merge|drop|create|alter|grant|revoke|truncate|optimize|vacuum)\b", re.I)

POOL_SIZE = int(os.environ.get("BEARINGS_REMOTE_POOL", "3"))
CACHE_TTL_S = int(os.environ.get("BEARINGS_REMOTE_CACHE_TTL", "600"))
_cache: dict = {}            # (conn, sql, params, limit) -> (time, result)
_cache_lock = threading.Lock()
_warm: dict[str, dict] = {}  # conn -> {state: warming|ready|error, since, error, ms}
_pool: dict[str, list[dict]] = {}
_pool_lock = threading.Lock()


def _checkout(conn_name: str) -> dict:
    """A free pooled slot for this connection (up to POOL_SIZE in parallel; beyond that, wait for one)."""
    while True:
        with _pool_lock:
            slots = _pool.setdefault(conn_name, [])
            for e in slots:
                if e["lock"].acquire(blocking=False):
                    return e
            if len(slots) < POOL_SIZE:
                e = {"con": None, "lock": threading.Lock()}
                e["lock"].acquire()
                slots.append(e)
                return e
            first = slots[0]
        with first["lock"]:  # wait until something frees up, then look again
            pass


@contextmanager
def cursor(conn_name: str, timeout_s: int = 1800):
    """A cursor on a pooled warehouse session (sign-in and session setup are paid once, not per table), with a
    longer statement timeout for bulk work (restored afterwards). A broken session is dropped so the next
    checkout opens a fresh one."""
    conn = cx.get(conn_name)
    e = _checkout(conn_name)
    try:
        if e["con"] is None:
            e["con"] = cx.sql_connect(conn, {"STATEMENT_TIMEOUT": str(TIMEOUT_S)})
        cur = e["con"].cursor()
        longer = False
        try:
            try:
                cur.execute(f"SET STATEMENT_TIMEOUT = {int(timeout_s)}")
                longer = True
            except Exception:
                pass
            yield cur
        except Exception as ex:
            if re.search(r"session|connection|closed|expired|reset by peer|broken pipe|invalid.*handle", str(ex), re.I):
                try:
                    e["con"].close()
                except Exception:
                    pass
                e["con"] = None
            raise
        finally:
            try:
                if longer and e["con"] is not None:
                    cur.execute(f"SET STATEMENT_TIMEOUT = {int(TIMEOUT_S)}")
            except Exception:
                pass
            try:
                cur.close()
            except Exception:
                pass
    finally:
        e["lock"].release()


def close_all():
    with _pool_lock:
        for slots in _pool.values():
            for e in slots:
                try:
                    if e["con"] is not None:
                        e["con"].close()
                except Exception:
                    pass
                e["con"] = None
        _pool.clear()


def _cache_key(conn_name, sql, params, limit):
    return (conn_name, sql, tuple(sorted((params or {}).items())), limit)


def clear_cache():
    with _cache_lock:
        _cache.clear()


def run(conn_name: str, sql: str, params: dict | None = None, limit: int = 1000, timeout_s: int | None = None,
        cache: bool = False) -> dict:
    """Execute one statement; returns {columns, types, rows, truncated, elapsed_ms, sql}.
    cache=True: reuse an identical result from the last CACHE_TTL_S seconds (lookups, key checks, value search)."""
    if cache and CACHE_TTL_S > 0:
        with _cache_lock:
            hit = _cache.get(_cache_key(conn_name, sql, params, limit))
        if hit and time.time() - hit[0] < CACHE_TTL_S:
            return {**hit[1], "cached": True, "elapsed_ms": 0}
    res = _run(conn_name, sql, params, limit, timeout_s)
    if cache and CACHE_TTL_S > 0:
        with _cache_lock:
            if len(_cache) > 500:
                _cache.clear()
            _cache[_cache_key(conn_name, sql, params, limit)] = (time.time(), res)
    return res


def warm_status(conn_name: str) -> dict:
    return _warm.get(conn_name) or {"state": "cold"}


def warm(conn_name: str, background: bool = True) -> dict:
    """Wake the SQL warehouse (a serverless one takes ~15-20 s after idling) so the first real click is fast."""
    st = _warm.get(conn_name)
    if st and st["state"] == "warming":
        return st
    if st and st["state"] == "ready" and time.time() - st["since"] < 300:
        return st
    _warm[conn_name] = {"state": "warming", "since": time.time()}

    def go():
        t0 = time.time()
        try:
            _run(conn_name, "SELECT 1 AS warm", None, 1, None)
            _warm[conn_name] = {"state": "ready", "since": time.time(), "ms": round((time.time() - t0) * 1000)}
        except Exception as e:
            _warm[conn_name] = {"state": "error", "since": time.time(), "error": str(e).splitlines()[0] if str(e) else type(e).__name__}

    if background:
        threading.Thread(target=go, daemon=True).start()
    else:
        go()
    return _warm[conn_name]


def _run(conn_name: str, sql: str, params: dict | None, limit: int, timeout_s: int | None) -> dict:
    conn = cx.get(conn_name)
    e = _checkout(conn_name)
    t0 = time.time()
    try:
        for attempt in (1, 2):
            try:
                if e["con"] is None:
                    e["con"] = cx.sql_connect(conn, {"STATEMENT_TIMEOUT": str(timeout_s or TIMEOUT_S)})
                cur = e["con"].cursor()
                try:
                    cur.execute(sql, params) if params else cur.execute(sql)
                    tbl = cur.fetchmany_arrow(limit + 1)
                finally:
                    try:
                        cur.close()
                    except Exception:
                        pass
                break
            except Exception as ex:
                msg = str(ex)
                # a dropped / expired session: reopen once; a SQL error: report it
                if attempt == 1 and re.search(r"session|connection|closed|expired|reset by peer|broken pipe|invalid.*handle", msg, re.I) \
                        and not re.search(r"PARSE_SYNTAX|UNRESOLVED|TABLE_OR_VIEW_NOT_FOUND|INSUFFICIENT_PERMISSIONS|DIVIDE_BY_ZERO|CAST", msg):
                    try:
                        e["con"].close()
                    except Exception:
                        pass
                    e["con"] = None
                    continue
                raise RemoteError(_clean(msg)) from ex
    finally:
        e["lock"].release()
    _warm[conn_name] = {"state": "ready", "since": time.time()}
    truncated = tbl.num_rows > limit
    if truncated:
        tbl = tbl.slice(0, limit)
    cols = tbl.column_names
    rows = [list(r.values()) for r in tbl.to_pylist()] if tbl.num_rows else []
    return {"columns": cols, "types": [str(f.type).upper() for f in tbl.schema], "rows": rows, "truncated": truncated,
            "elapsed_ms": round((time.time() - t0) * 1000), "sql": sql, "engine": f"databricks:{conn_name}"}


def _clean(msg: str) -> str:
    m = re.search(r"\[([A-Z_]+(?:\.[A-Z_]+)?)\]\s*(.+?)(?:\sSQLSTATE|\n|$)", msg)
    return f"[{m.group(1)}] {m.group(2)}" if m else (msg.splitlines()[0] if msg else "Databricks error")


# ------------------------------------------------------------------ operations used by the API
def sample(src: dict, table: str, cols: list[str], n: int, nonnull: list[str], where: str | None, seed: int | None,
           row_count: int | None) -> dict:
    if where and FORBIDDEN.search(where):
        raise RemoteError("Only a simple filter expression is allowed")
    conds = [f"{bq(c)} IS NOT NULL" for c in nonnull]
    if where:
        conds.append(f"({where})")
    cols_sql = ", ".join(bq(c) for c in cols)
    where_sql = f" WHERE {' AND '.join(conds)}" if conds else ""
    base = remote_fq(src, table)
    rep = f" REPEATABLE ({int(seed)})" if seed is not None else ""
    if row_count and row_count > 5 * n:
        # Bernoulli sample sized for ~5x the rows needed (more when filtering), no sort of the whole table
        pct = min(100.0, round(100.0 * n * (20 if conds else 5) / row_count, 6))
        sql = f"SELECT {cols_sql} FROM {base} TABLESAMPLE ({pct} PERCENT){rep}{where_sql} LIMIT {int(n)}"
        r = run(src["connection"], sql, limit=n)
        if len(r["rows"]) >= n or pct >= 100.0:
            return r
    # small table, unknown size, or a filter that thinned the sample too much: random order over what's left
    sql = f"SELECT {cols_sql} FROM {base}{where_sql} ORDER BY rand({int(seed) if seed is not None else ''}) LIMIT {int(n)}"
    return run(src["connection"], sql, limit=n)


def uniqueness(src: dict, table: str, cols: list[str]) -> dict:
    frm, key = remote_fq(src, table), ", ".join(bq(c) for c in cols)
    anynull = " OR ".join(f"{bq(c)} IS NULL" for c in cols)
    r = run(src["connection"], f"""SELECT count(*) AS n_rows, (SELECT count(*) FROM (SELECT DISTINCT {key} FROM {frm})) AS n_distinct,
                                          count_if({anynull}) AS n_nulls FROM {frm}""", limit=1, cache=True)
    rows, distinct, nulls = r["rows"][0]
    d = run(src["connection"], f"SELECT {key}, count(*) AS n FROM {frm} GROUP BY {key} HAVING count(*) > 1 ORDER BY n DESC LIMIT 10",
            limit=10, cache=True)
    return {"rows": rows, "distinct": distinct, "rows_with_nulls": nulls, "duplicate_examples": d["rows"],
            "elapsed_ms": r["elapsed_ms"] + d["elapsed_ms"]}


def condition(col: str, dtype: str, op: str, values: list[str], params: dict) -> str:
    """Databricks version of the lookup filter (see api._cond for the DuckDB one)."""
    f = spark_family(dtype)
    q = bq(col)

    def p(v):
        k = f"p{len(params)}"
        params[k] = v
        return f":{k}"

    if op == "~":
        return f"CAST({q} AS STRING) ILIKE {p('%' + values[0] + '%')}"
    if f == "string":
        if op in ("=", "!="):
            return f"lower(trim({q})) {'NOT ' if op == '!=' else ''}IN ({', '.join(p(v.lower()) for v in values)})"
        return f"{q} {op} {p(values[0])}"
    if f == "numeric":
        if op in ("=", "!="):
            return f"{q} {'NOT ' if op == '!=' else ''}IN ({', '.join(f'try_cast({p(v)} AS DOUBLE)' for v in values)})"
        return f"{q} {op} try_cast({p(values[0])} AS DOUBLE)"
    if f == "temporal":
        if op in ("=", "!="):
            ors = " OR ".join(f"CAST({q} AS STRING) LIKE {p(v + '%')}" for v in values)
            return f"NOT ({ors})" if op == "!=" else f"({ors})"
        return f"{q} {op} try_cast({p(values[0])} AS TIMESTAMP)"
    if op in ("=", "!="):
        return f"lower(CAST({q} AS STRING)) {'NOT ' if op == '!=' else ''}IN ({', '.join(p(v.lower()) for v in values)})"
    return f"CAST({q} AS STRING) {op} {p(values[0])}"


def lookup(src: dict, table: str, cols: list[tuple[str, str]], op: str, values: list[str], limit: int) -> dict:
    params: dict = {}
    where = " OR ".join(f"({condition(c, t, op, values, params)})" for c, t in cols)
    frm = remote_fq(src, table)
    # rows and the total match count in one round trip (the window count is taken before LIMIT)
    r = run(src["connection"], f"SELECT *, count(*) OVER () AS __bearings_n FROM {frm} WHERE {where} LIMIT {int(limit)}",
            params, limit=limit, cache=True)
    count = r["rows"][0][-1] if r["rows"] else 0
    rows = {"rows": [row[:-1] for row in r["rows"]], "elapsed_ms": r["elapsed_ms"]}
    n = {"elapsed_ms": 0}
    shown = where
    for k, v in params.items():
        shown = shown.replace(f":{k}", "'" + str(v).replace("'", "''") + "'")
    return {"count": count, "rows": rows["rows"], "sql": f"SELECT *\nFROM {frm}\nWHERE {shown}",
            "elapsed_ms": n["elapsed_ms"] + rows["elapsed_ms"]}


def value_search(src: dict, table: str, columns: list[dict], value: str, exact: bool) -> list[dict]:
    """Which columns of one remote table contain the value? One pass over the table."""
    try:
        num = float(value.replace(",", ""))
    except ValueError:
        num = None
    esc = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    tests, params = [], {"v": value if exact else f"%{esc}%"}
    if num is not None:
        params["n"] = num
    for c in columns:
        f, q = spark_family(c["type"]), bq(c["column"])
        if f == "string":
            tests.append((c, f"lower({q}) = lower(:v)" if exact else f"{q} ILIKE :v"))
        elif f == "numeric" and num is not None:
            tests.append((c, f"{q} = :n"))
        elif f == "temporal" and re.match(r"^\d{4}-\d{2}-\d{2}", value):
            params["d"] = value + "%"
            tests.append((c, f"CAST({q} AS STRING) LIKE :d"))
    if not tests:
        return []
    frm = remote_fq(src, table)
    r = run(src["connection"], "SELECT " + ", ".join(f"count_if({cond}) AS _h{i}" for i, (_, cond) in enumerate(tests)) + f" FROM {frm}",
            params, limit=1, cache=True)
    out = []
    for (c, cond), n in zip(tests, r["rows"][0]):
        if n:
            ex = run(src["connection"], f"SELECT DISTINCT CAST({bq(c['column'])} AS STRING) AS v FROM {frm} WHERE {cond} LIMIT 3", params,
                     limit=3, cache=True)
            out.append({"column": c["column"], "hits": int(n), "examples": [x[0] for x in ex["rows"]]})
    return out


def rewrite_aliases(sql: str, sources: dict[str, dict], conn_name: str) -> str:
    """In the SQL console, `dev_raw_pms.reservation` means the attached remote table: expand it to
    `catalog`.`schema`.`reservation` for the aliases on this connection (outside quoted strings)."""
    parts = re.split(r"('(?:[^']|'')*')", sql)
    for a, s in sources.items():
        if s["connection"] != conn_name:
            continue
        pat = re.compile(rf"(?<![\w.`]){re.escape(a)}\s*\.\s*(`[^`]+`|\w+)", re.I)
        rep = lambda m, s=s: f"{bq(s['catalog'])}.{bq(s['schema'])}.{m.group(1) if m.group(1).startswith('`') else bq(m.group(1))}"  # noqa: E731
        parts = [p if i % 2 else pat.sub(rep, p) for i, p in enumerate(parts)]
    return "".join(parts)


def console(conn_name: str, sql: str, sources: dict[str, dict], limit: int) -> dict:
    sql = sql.strip().rstrip(";")
    if ";" in sql:
        raise RemoteError("One statement at a time")
    if not READ_ONLY.match(sql) or FORBIDDEN.search(re.sub(r"'(?:[^']|'')*'", "''", sql)):
        raise RemoteError("Read-only: SELECT / WITH / DESCRIBE / SHOW / EXPLAIN only")
    return run(conn_name, rewrite_aliases(sql, sources, conn_name), limit=limit)


def value_search_many(tables: list[dict], value: str, exact: bool) -> tuple[dict, list[dict]]:
    """value_search over several remote tables, POOL_SIZE at a time. Returns ({(schema, table): hits}, errors)."""
    from concurrent.futures import ThreadPoolExecutor
    out, errors = {}, []

    def one(tb):
        return tb, value_search(tb["remote"], tb["table"], tb["columns"], value, exact)

    with ThreadPoolExecutor(max_workers=max(1, POOL_SIZE)) as ex:
        futs = [ex.submit(one, tb) for tb in tables]
        for f, tb in zip(futs, tables):
            try:
                _, hits = f.result()
                if hits:
                    out[(tb["schema"], tb["table"])] = hits
            except Exception as e:
                errors.append({"table": f"{tb['schema']}.{tb['table']}", "error": str(e).splitlines()[0] if str(e) else type(e).__name__})
    return out, errors
