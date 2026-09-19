"""`bearings pull`: copy (a sample of) a remote table into DuckDB so every local feature works on it.

Rows stream from the SQL warehouse as Arrow batches into a temporary Parquet file; the DuckDB write
lock is only taken for the final, fast `CREATE TABLE … AS SELECT * FROM read_parquet(…)`.
By default the copy lands under the remote alias (`opera_dbx.reservation`), where it replaces the
metadata-only entry in the app; `--as <schema>` puts it somewhere else.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import tempfile
import time
from pathlib import Path

from ..db import META, connect, fq, qi, remote_aliases, ro, safe_name
from . import RemoteError
from . import connections as cx
from .sync import remote_fq

FORBIDDEN = re.compile(r";|--|/\*|\b(insert|update|delete|merge|drop|create|alter|grant|revoke|truncate|copy|optimize|vacuum|call)\b", re.I)
BATCH = 100_000
PARALLEL = int(__import__("os").environ.get("BEARINGS_REMOTE_POOL", "3"))
_write_lock = __import__("threading").Lock()


KEY_BUCKETS = 1_000_000


def key_filter(col: str, ppm: int) -> str:
    """Rows whose key hashes into the first `ppm` of a million buckets. The same expression on parent and child
    keeps the same key values on both sides, so the samples join (xxhash64 is deterministic on Databricks)."""
    q = "`" + col.replace("`", "``") + "`"
    return f"pmod(xxhash64(CAST({q} AS STRING)), {KEY_BUCKETS}) < {int(ppm)}"


def build_sql(src: dict, table: str, rows: int | None, where: str | None, first: bool = False, total: int | None = None,
              key_sample: dict | None = None) -> str:
    """SELECT for a pull. A random sample uses TABLESAMPLE (p PERCENT) – Spark's `(n ROWS)` form just takes the
    first n rows – with p sized from the table's row count (a cheap metadata count on Delta) plus 10% headroom.
    A key sample keeps the rows whose key falls in a hash range shared with related tables (see key_filter)."""
    if where and FORBIDDEN.search(where):
        raise RemoteError("--where must be a simple filter expression")
    if key_sample:
        return f"SELECT * FROM {remote_fq(src, table)} WHERE {key_filter(key_sample['column'], key_sample['ppm'])}"
    sql = f"SELECT * FROM {remote_fq(src, table)}"
    if rows and not where and not first and total and total > rows:
        pct = min(100.0, round(100.0 * rows / total * 1.1, 6))
        sql += f" TABLESAMPLE ({pct} PERCENT)"
    if where:
        sql += f" WHERE {where}"
    if rows:
        sql += f" LIMIT {int(rows)}"
    return sql


def pull(db_path: Path, ref: str, rows: int | None = None, where: str | None = None, target_schema: str | None = None,
         target_table: str | None = None, first: bool = False, profile: bool = True, key_sample: dict | None = None,
         echo=lambda *_: None) -> dict:
    """ref = <alias>.<table>. Returns {schema, table, rows, columns, sql, seconds}."""
    if "." not in ref:
        raise RemoteError("Use <alias>.<table>, e.g. opera_dbx.reservation")
    alias, table = ref.split(".", 1)
    with ro(db_path) as con:
        src = remote_aliases(con).get(alias)
        if not src:
            raise RemoteError(f"'{alias}' is not an attached remote schema")
        known = con.execute(f"SELECT table_name FROM {META}.remote_tables WHERE alias=? AND NOT dropped", [alias]).fetchall()
        names = {t for (t,) in known}
        if table not in names:
            lower = {t.lower(): t for t in names}
            if table.lower() not in lower:
                raise RemoteError(f"No table '{table}' in {alias} (run `bearings sync -s {alias}` if it's new)")
            table = lower[table.lower()]
        comments = con.execute(f"SELECT column_name, comment FROM {META}.remote_columns WHERE alias=? AND table_name=? AND comment IS NOT NULL",
                               [alias, table]).fetchall()
        tcomment = con.execute(f"SELECT comment FROM {META}.remote_tables WHERE alias=? AND table_name=?", [alias, table]).fetchone()
    ts, tt = safe_name(target_schema) if target_schema else alias, safe_name(target_table) if target_table else table
    build_sql(src, table, rows, where, first, key_sample=key_sample)  # validate --where before connecting
    conn = cx.get(src["connection"])
    try:
        import pyarrow.parquet as pq
    except ImportError as e:  # pragma: no cover
        raise RemoteError("`bearings pull` needs the Databricks extra: uv sync --extra databricks") from e

    t0 = time.time()
    n = 0
    with tempfile.TemporaryDirectory(prefix="bearings-pull-") as tmp:
        part = Path(tmp) / "pull.parquet"
        writer = None
        from . import query as rq
        try:
            with rq.cursor(conn.name) as cur:
                total = None
                if not where:  # cheap on Delta (metadata); tells whether the copy is complete
                    cur.execute(f"SELECT count(*) FROM {remote_fq(src, table)}")
                    total = int(list(cur.fetchone())[0])
                    echo(f"  {total:,} rows in {src['catalog']}.{src['schema']}.{table}")
                version = delta_version(cur, src, table)
                sql = build_sql(src, table, rows, where, first, total, key_sample=key_sample)
                echo(f"  {sql}")
                cur.execute(sql)
                while True:
                    batch = cur.fetchmany_arrow(BATCH)
                    if batch is None or batch.num_rows == 0:
                        if writer is None and batch is not None:
                            writer = pq.ParquetWriter(part, batch.schema)  # keep the column layout for an empty result
                        break
                    if writer is None:
                        writer = pq.ParquetWriter(part, batch.schema)
                    writer.write_table(batch)
                    n += batch.num_rows
                    echo(f"  … {n:,} rows")
        finally:
            if writer is not None:
                writer.close()
        if writer is None:
            raise RemoteError("The query returned no result set")
        _write_lock.acquire()  # parallel pulls download together, write to DuckDB one at a time
        try:
            con = connect(db_path, read_only=False, retries=5)
        except Exception:
            _write_lock.release()
            raise
        try:
            con.execute(f"CREATE SCHEMA IF NOT EXISTS {qi(ts)}")
            con.execute(f"CREATE OR REPLACE TABLE {fq(ts, tt)} AS SELECT * FROM read_parquet(?)", [str(part)])
            ncols = len(con.execute(f"DESCRIBE {fq(ts, tt)}").fetchall())
            con.execute(f"INSERT INTO {META}.load_log VALUES (?,?,?,?,?,?,?)",
                        [ts, tt, f"databricks://{conn.name}/{src['catalog']}.{src['schema']}.{table}", "databricks", n, ncols,
                         dt.datetime.now()])
            # carry the Unity Catalog descriptions over, so the copy stays searchable by comment
            con.execute(f"DELETE FROM {META}.comments WHERE schema_name=? AND table_name=?", [ts, tt])
            rowsc = [[ts, tt, c, cm] for c, cm in comments]
            if tcomment and tcomment[0]:
                rowsc.append([ts, tt, "", tcomment[0]])
            if rowsc:
                con.executemany(f"INSERT INTO {META}.comments VALUES (?,?,?,?)", rowsc)
            complete = where is None and total is not None and n >= total
            is_cache = (ts, tt) == (alias, table)
            masked: list[str] = []
            if is_cache:
                from . import pii
                masked = pii.apply(con, db_path, alias, table, local_copy=True)
                now = dt.datetime.now().replace(microsecond=0)
                method = None if complete else (f"key:{key_sample['column']}" + (f" ({key_sample['note']})" if key_sample.get("note") else "")
                                                if key_sample else "random")
                con.execute(f"DELETE FROM {META}.remote_cache WHERE alias=? AND table_name=?", [alias, table])
                con.execute(f"""INSERT INTO {META}.remote_cache (alias, table_name, cached_rows, total_rows, complete, cached_at,
                                    sample_method, masked_columns, source_version, latest_version, checked_at)
                                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                            [alias, table, n, total, complete, now, method, json.dumps(masked) if masked else None, version, version, now])
            has_profile = con.execute(f"SELECT count(*) FROM {META}.table_profile WHERE schema_name=? AND table_name=? AND NOT coalesce(stale, false)",
                                      [ts, tt]).fetchone()[0]
            if profile and (complete or not has_profile or not is_cache):
                # complete copy: profile it locally (exact, fast). A sample of a remote table keeps its whole-table
                # profile from Databricks when it has one – a sample's counts would understate the real table.
                from .. import profiler
                tp, cols = profiler.profile_table(con, ts, tt)
                if not complete and total:
                    tp.update(row_count=total, sampled_rows=n)
                profiler.save(con, tp, cols)
        finally:
            con.close()
            _write_lock.release()
    return {"schema": ts, "table": tt, "rows": n, "total_rows": total, "complete": complete, "columns": ncols, "sql": sql,
            "masked": masked, "version": version, "seconds": round(time.time() - t0, 1)}


def delta_version(cur, src: dict, table: str) -> int | None:
    """Current Delta version of a table (None for views / non-Delta tables or when history isn't readable)."""
    try:
        cur.execute(f"DESCRIBE HISTORY {remote_fq(src, table)} LIMIT 1")
        tbl = cur.fetchall_arrow()
        if tbl.num_rows and "version" in tbl.column_names:
            return int(tbl.column("version")[0].as_py())
    except Exception:
        pass
    return None


def check_freshness(db_path: Path, aliases: list[str] | None = None, echo=lambda *_: None) -> list[dict]:
    """Compare each cached table's Delta version with the current one on Databricks (one small query per
    table, 3 at a time). Tables whose data moved get their profile marked stale – `refresh` / `cache --changed`
    then re-profile and re-cache them. Returns the changed tables."""
    from concurrent.futures import ThreadPoolExecutor

    from . import query as rq
    with ro(db_path) as con:
        srcs = remote_aliases(con)
        rows = con.execute(f"SELECT alias, table_name, source_version FROM {META}.remote_cache WHERE source_version IS NOT NULL").fetchall()
    rows = [r for r in rows if r[0] in srcs and (not aliases or r[0] in aliases)]

    def one(r):
        a, t, v = r
        res = rq.run(srcs[a]["connection"], f"DESCRIBE HISTORY {remote_fq(srcs[a], t)} LIMIT 1", limit=1)
        cols = res["columns"]
        return a, t, v, int(res["rows"][0][cols.index("version")]) if res["rows"] and "version" in cols else None

    results = []
    with ThreadPoolExecutor(max_workers=rq.POOL_SIZE) as ex:
        for f in [ex.submit(one, r) for r in rows]:
            try:
                results.append(f.result())
            except Exception as e:
                echo(f"  ? {str(e).splitlines()[0] if str(e) else 'version check failed'}")
    changed = []
    now = dt.datetime.now().replace(microsecond=0)
    con = connect(db_path, read_only=False, retries=5)
    try:
        for a, t, v, latest in results:
            con.execute(f"UPDATE {META}.remote_cache SET latest_version=?, checked_at=? WHERE alias=? AND table_name=?", [latest, now, a, t])
            if latest is not None and v is not None and latest > v:
                con.execute(f"UPDATE {META}.table_profile SET stale=true WHERE schema_name=? AND table_name=?", [a, t])
                changed.append({"alias": a, "table": t, "cached_version": v, "latest_version": latest})
                echo(f"  ↻ {a}.{t}: data changed (version {v} → {latest})")
    finally:
        con.close()
    return changed


def plan_key_samples(con, big: dict[tuple[str, str], int], limits: dict[str, int], min_confidence: float = 0.8) -> dict:
    """Join-consistent sampling for big tables linked by discovered relationships.

    For child.fk → parent.pk where both are too big to cache whole, the parent is sampled on pk and the child on
    fk with the same hash range, so every cached child row finds its parent in the cache. One sampling fraction
    per group (parent + its keyed children), sized so the biggest member fits its schema's cache size.
    Returns {(schema, table): {"column", "ppm", "note"}}; tables not in it get a plain random sample."""
    rels = con.execute(f"""SELECT from_schema, from_table, from_column, to_schema, to_table, to_column, confidence
                           FROM {META}.relationships WHERE confidence >= ? ORDER BY confidence DESC""", [min_confidence]).fetchall()
    key: dict[tuple[str, str], str] = {}
    group: dict[tuple[str, str], tuple[str, str]] = {}
    for fs, ft, fc, ts, tt, tc, _ in rels:
        child, parent = (fs, ft), (ts, tt)
        if child not in big or parent not in big or child == parent:
            continue
        if parent not in key and parent not in group:
            key[parent], group[parent] = tc, parent
        if key.get(parent) != tc or child in key:
            continue  # parent is sampled on another column: this child can't follow it
        key[child], group[child] = fc, group[parent]
    members: dict = {}
    for t, g in group.items():
        members.setdefault(g, []).append(t)
    out = {}
    for g, ms in members.items():
        if len(ms) < 2:
            continue
        frac = min(limits.get(t[0], DEFAULT_CACHE_ROWS) / big[t] for t in ms)
        ppm = max(1, int(frac * KEY_BUCKETS))
        for t in ms:
            note = f"with {len(ms) - 1} related table(s)" if t == g else f"matches {g[0]}.{g[1]}"
            out[t] = {"column": key[t], "ppm": ppm, "note": note}
    return out


DEFAULT_CACHE_ROWS = int(__import__("os").environ.get("BEARINGS_CACHE_MAX_ROWS", "300000"))


def cache_limit(con, alias: str) -> int:
    """Rows to cache for this remote schema: its own setting, else the default (BEARINGS_CACHE_MAX_ROWS or 300,000)."""
    from ..db import has_meta_column
    if has_meta_column(con, "remote_sources", "cache_max_rows"):
        r = con.execute(f"SELECT cache_max_rows FROM {META}.remote_sources WHERE alias=?", [alias]).fetchone()
        if r and r[0]:
            return int(r[0])
    return DEFAULT_CACHE_ROWS


def set_cache_limit(db_path: Path, alias: str, max_rows: int) -> None:
    con = connect(db_path, read_only=False, retries=5)
    try:
        con.execute(f"UPDATE {META}.remote_sources SET cache_max_rows=? WHERE alias=?", [int(max_rows), alias])
    finally:
        con.close()


def cache(db_path: Path, aliases: list[str] | None = None, tables: list[str] | None = None, max_rows: int | None = None,
          refresh: bool = False, only_changed: bool = False, echo=lambda *_: None) -> list[dict]:
    """Cache remote tables locally: tables up to N rows whole, a random N-row sample of bigger ones.
    N = max_rows, else the schema's cache setting, else the default. Already cached tables are skipped unless
    refresh=True (only_changed: just those whose source changed since – their profile is marked stale)."""
    with ro(db_path) as con:
        srcs = remote_aliases(con)
        limits = {a: (max_rows or cache_limit(con, a)) for a in srcs}
        stale = {(s_, t) for s_, t in con.execute(
            f"SELECT schema_name, table_name FROM {META}.table_profile WHERE coalesce(stale, false)").fetchall()}
    out = []
    for a in (aliases or list(srcs)):
        if a not in srcs:
            continue
        sel = [t for t in (tables or []) if t.split(".", 1)[0] == a] or None
        if only_changed:
            sel = [f"{s_}.{t}" for s_, t in stale if s_ == a]
            if not sel:
                continue
        n = limits[a]
        echo(f"  {a}: tables up to {n:,} rows whole, a {n:,}-row sample of bigger ones")
        out += pull_many(db_path, aliases=[a], tables=sel, max_rows=n, sample_rows=n, refresh=refresh or only_changed, echo=echo)
    return out


def pull_many(db_path: Path, aliases: list[str] | None = None, tables: list[str] | None = None, max_rows: int | None = None,
              sample_rows: int | None = None, refresh: bool = False, echo=lambda *_: None) -> list[dict]:
    """Pull several remote tables. Tables up to `max_rows` are copied whole; bigger ones are skipped, or sampled
    down to `sample_rows` when given. Already pulled tables are skipped unless refresh=True."""
    from ..db import user_tables
    with ro(db_path) as con:
        srcs = remote_aliases(con)
        rows = con.execute(f"""SELECT r.alias, r.table_name, coalesce(p.row_count, r.row_count)
                               FROM {META}.remote_tables r LEFT JOIN {META}.table_profile p
                                 ON p.schema_name = r.alias AND p.table_name = r.table_name
                               WHERE NOT r.dropped ORDER BY 1, 2""").fetchall()
        local = set(user_tables(con))
    want = {t.lower() for t in tables or []}
    plan = []
    for a, t, n in rows:
        if a not in srcs or (aliases and a not in aliases) or (want and f"{a}.{t}".lower() not in want):
            continue
        if (a, t) in local and not refresh:
            continue
        if max_rows and n is not None and n > max_rows:
            if not sample_rows:
                echo(f"  – {a}.{t}: {n:,} rows > {max_rows:,}, stays remote")
                continue
            plan.append((a, t, sample_rows))
        else:
            plan.append((a, t, None))
    keyed = {}
    if sample_rows and any(r for _, _, r in plan):
        with ro(db_path) as con:
            sizes = {(a, t): n for a, t, n in rows if n is not None}
            big = {(a, t): sizes[(a, t)] for a, t, r in plan if r and (a, t) in sizes}
            # tables already cached as a (keyed) sample count as big too, so a re-cache keeps groups consistent
            big.update({k: v for k, v in sizes.items() if max_rows and v > max_rows})
            keyed = plan_key_samples(con, big, {a: sample_rows for a, _, _ in plan})
    from concurrent.futures import ThreadPoolExecutor

    def one(item):
        a, t, r = item
        try:
            return item, pull(db_path, f"{a}.{t}", rows=r, key_sample=keyed.get((a, t)) if r else None, echo=lambda *_: None), None
        except Exception as e:
            return item, None, e

    out = []
    # the first table alone (it may wait for the warehouse to wake), then PARALLEL at a time
    first = [one(plan[0])] if plan else []
    with ThreadPoolExecutor(max_workers=max(1, PARALLEL)) as ex:
        for (a, t, r), res, err in [*first, *ex.map(one, plan[1:])]:
            if err is not None:
                echo(f"  ✗ {a}.{t}: {str(err).splitlines()[0] if str(err) else type(err).__name__}")
                out.append({"schema": a, "table": t, "error": str(err).splitlines()[0] if str(err) else type(err).__name__})
                continue
            kind = "cached" if res.get("complete") else f"sample of {res['total_rows']:,}" if res.get("total_rows") else "sample"
            if keyed.get((a, t)) and not res.get("complete"):
                kind += f", keyed on {keyed[(a, t)]['column']}"
            if res.get("masked"):
                kind += f", {len(res['masked'])} PII col(s) masked"
            echo(f"  ✓ {a}.{t:<40} {res['rows']:>12,} rows  {kind:<22} {res['seconds']}s")
            out.append(res)
    return out
