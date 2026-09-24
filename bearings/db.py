"""Connection helpers and the _meta schema."""
from __future__ import annotations

import os
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

import duckdb

META = "_meta"

META_DDL = f"""
CREATE SCHEMA IF NOT EXISTS {META};
CREATE TABLE IF NOT EXISTS {META}.load_log (
  schema_name VARCHAR, table_name VARCHAR, source VARCHAR, file_format VARCHAR,
  row_count BIGINT, column_count INTEGER, loaded_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS {META}.comments (
  schema_name VARCHAR, table_name VARCHAR, column_name VARCHAR, comment VARCHAR
);
CREATE TABLE IF NOT EXISTS {META}.table_profile (
  schema_name VARCHAR, table_name VARCHAR, row_count BIGINT, column_count INTEGER,
  candidate_keys VARCHAR, sampled_rows BIGINT, profiled_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS {META}.column_profile (
  schema_name VARCHAR, table_name VARCHAR, column_name VARCHAR, ordinal INTEGER,
  data_type VARCHAR, row_count BIGINT, null_count BIGINT, null_pct DOUBLE,
  blank_count BIGINT, distinct_count BIGINT, distinct_pct DOUBLE,
  min_val VARCHAR, max_val VARCHAR, mean DOUBLE, stddev DOUBLE,
  p25 VARCHAR, p50 VARCHAR, p75 VARCHAR,
  min_len INTEGER, avg_len DOUBLE, max_len INTEGER,
  top_values VARCHAR, patterns VARCHAR, histogram VARCHAR, flags VARCHAR,
  profiled_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS {META}.relationships (
  from_schema VARCHAR, from_table VARCHAR, from_column VARCHAR,
  to_schema VARCHAR, to_table VARCHAR, to_column VARCHAR,
  name_score DOUBLE, overlap_pct DOUBLE, from_distinct BIGINT, matched_distinct BIGINT,
  confidence DOUBLE, method VARCHAR, found_at TIMESTAMP
);
-- remote sources (Azure Databricks / Unity Catalog): metadata cached here, data stays remote
CREATE TABLE IF NOT EXISTS {META}.remote_sources (
  alias VARCHAR PRIMARY KEY, connection VARCHAR, catalog VARCHAR, schema VARCHAR,
  attached_at TIMESTAMP, synced_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS {META}.remote_tables (
  alias VARCHAR, table_name VARCHAR, table_type VARCHAR, comment VARCHAR,
  row_count BIGINT, size_bytes BIGINT, remote_updated_at TIMESTAMP, synced_at TIMESTAMP,
  dropped BOOLEAN DEFAULT false
);
CREATE TABLE IF NOT EXISTS {META}.remote_columns (
  alias VARCHAR, table_name VARCHAR, column_name VARCHAR, ordinal INTEGER,
  data_type VARCHAR, nullable BOOLEAN, comment VARCHAR
);
CREATE TABLE IF NOT EXISTS {META}.sync_log (
  alias VARCHAR, synced_at TIMESTAMP, change VARCHAR, table_name VARCHAR, column_name VARCHAR,
  old_value VARCHAR, new_value VARCHAR
);
ALTER TABLE {META}.table_profile ADD COLUMN IF NOT EXISTS stale BOOLEAN DEFAULT false;
-- key fingerprints: distinct values of key-like columns of remote tables, so relationship discovery and
-- value search can run locally without the rows (complete = every distinct value is stored)
CREATE TABLE IF NOT EXISTS {META}.key_fingerprint (
  schema_name VARCHAR, table_name VARCHAR, column_name VARCHAR, distinct_count BIGINT, stored BIGINT,
  complete BOOLEAN, captured_at TIMESTAMP
);
-- local cache of remote tables: complete copy, or a random sample of bigger tables
CREATE TABLE IF NOT EXISTS {META}.remote_cache (
  alias VARCHAR, table_name VARCHAR, cached_rows BIGINT, total_rows BIGINT, complete BOOLEAN, cached_at TIMESTAMP
);
ALTER TABLE {META}.remote_sources ADD COLUMN IF NOT EXISTS cache_max_rows BIGINT;
ALTER TABLE {META}.remote_sources ADD COLUMN IF NOT EXISTS mask_pii BOOLEAN;
ALTER TABLE {META}.remote_cache ADD COLUMN IF NOT EXISTS sample_method VARCHAR;
ALTER TABLE {META}.remote_cache ADD COLUMN IF NOT EXISTS masked_columns VARCHAR;
ALTER TABLE {META}.remote_cache ADD COLUMN IF NOT EXISTS source_version BIGINT;
ALTER TABLE {META}.remote_cache ADD COLUMN IF NOT EXISTS latest_version BIGINT;
ALTER TABLE {META}.remote_cache ADD COLUMN IF NOT EXISTS checked_at TIMESTAMP;
CREATE TABLE IF NOT EXISTS {META}.settings (key VARCHAR PRIMARY KEY, value VARCHAR);
CREATE TABLE IF NOT EXISTS {META}.key_values (
  schema_name VARCHAR, table_name VARCHAR, column_name VARCHAR, v VARCHAR
);
-- v0.4 modelling insights: disguised nulls / type hints (profile), cardinality (relationships), grain,
-- time coverage and dependencies (bearings insights)
ALTER TABLE {META}.column_profile ADD COLUMN IF NOT EXISTS placeholder_count BIGINT;
ALTER TABLE {META}.column_profile ADD COLUMN IF NOT EXISTS placeholder_values VARCHAR;
ALTER TABLE {META}.column_profile ADD COLUMN IF NOT EXISTS effective_null_pct DOUBLE;
ALTER TABLE {META}.column_profile ADD COLUMN IF NOT EXISTS type_hint VARCHAR;
ALTER TABLE {META}.column_profile ADD COLUMN IF NOT EXISTS leading_zero_count BIGINT;
ALTER TABLE {META}.relationships ADD COLUMN IF NOT EXISTS cardinality VARCHAR;
ALTER TABLE {META}.relationships ADD COLUMN IF NOT EXISTS child_avg DOUBLE;
ALTER TABLE {META}.relationships ADD COLUMN IF NOT EXISTS child_max BIGINT;
ALTER TABLE {META}.relationships ADD COLUMN IF NOT EXISTS parent_no_child_pct DOUBLE;
ALTER TABLE {META}.relationships ADD COLUMN IF NOT EXISTS fk_null_pct DOUBLE;
ALTER TABLE {META}.relationships ADD COLUMN IF NOT EXISTS orphan_rows BIGINT;
ALTER TABLE {META}.relationships ADD COLUMN IF NOT EXISTS card_on_sample BOOLEAN;
ALTER TABLE {META}.table_profile ADD COLUMN IF NOT EXISTS grain VARCHAR;
ALTER TABLE {META}.table_profile ADD COLUMN IF NOT EXISTS grain_dup_rows BIGINT;
ALTER TABLE {META}.table_profile ADD COLUMN IF NOT EXISTS grain_on_sample BOOLEAN;
ALTER TABLE {META}.table_profile ADD COLUMN IF NOT EXISTS insights_at TIMESTAMP;
ALTER TABLE {META}.column_profile ADD COLUMN IF NOT EXISTS outlier_count BIGINT;
ALTER TABLE {META}.column_profile ADD COLUMN IF NOT EXISTS outlier_low DOUBLE;
ALTER TABLE {META}.column_profile ADD COLUMN IF NOT EXISTS outlier_high DOUBLE;
ALTER TABLE {META}.column_profile ADD COLUMN IF NOT EXISTS outlier_values VARCHAR;
ALTER TABLE {META}.column_profile ADD COLUMN IF NOT EXISTS negative_count BIGINT;
CREATE TABLE IF NOT EXISTS {META}.code_values (
  schema_name VARCHAR, table_name VARCHAR, column_name VARCHAR, value VARCHAR, n BIGINT, on_sample BOOLEAN
);
CREATE TABLE IF NOT EXISTS {META}.conditional_fill (
  schema_name VARCHAR, table_name VARCHAR, column_name VARCHAR, by_column VARCHAR, when_values VARCHAR,
  precision DOUBLE, coverage DOUBLE, filled_rows BIGINT, rows_when BIGINT, found_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS {META}.optional_groups (
  schema_name VARCHAR, table_name VARCHAR, columns VARCHAR, filled_rows BIGINT, row_count BIGINT, similarity DOUBLE,
  found_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS {META}.time_profile (
  schema_name VARCHAR, table_name VARCHAR, column_name VARCHAR, parsed_from_text BOOLEAN,
  first_month DATE, last_month DATE, months_present INTEGER, empty_months INTEGER,
  future_rows BIGINT, sentinel_rows BIGINT, dated_rows BIGINT, kind VARCHAR, is_primary BOOLEAN,
  series VARCHAR, on_sample BOOLEAN, profiled_at TIMESTAMP
);
CREATE TABLE IF NOT EXISTS {META}.dependencies (
  schema_name VARCHAR, table_name VARCHAR, determinant VARCHAR, dependent VARCHAR,
  strength DOUBLE, exceptions BIGINT, rows_checked BIGINT, determinant_distinct BIGINT, kind VARCHAR,
  on_sample BOOLEAN, found_at TIMESTAMP
);
"""


def default_db_path() -> Path:
    """$BEARINGS_DB, else ./data/bearings.duckdb (falls back to a pre-rename ./data/dm.duckdb / $DM_DB)."""
    env = os.environ.get("BEARINGS_DB") or os.environ.get("DM_DB")
    if env:
        return Path(env).resolve()
    new, old = Path("data/bearings.duckdb"), Path("data/dm.duckdb")
    return (old if old.exists() and not new.exists() else new).resolve()


def annotations_path(db_path: Path) -> Path:
    """One annotations file per database (dm.duckdb → dm.annotations.sqlite), kept outside
    DuckDB so rebuilding/reloading the data never loses your tags and CDM mappings."""
    p = Path(db_path)
    return p.with_name(p.stem + ".annotations.sqlite")


def connect(db_path: Path, read_only: bool = False, retries: int = 0) -> duckdb.DuckDBPyConnection:
    db_path = Path(db_path)
    if not read_only:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(retries + 1):
        try:
            con = duckdb.connect(str(db_path), read_only=read_only)
            if not read_only:
                con.execute(META_DDL)
            return con
        except (duckdb.IOException, duckdb.ConnectionException) as e:  # lock held by another process / connection
            last = e
            time.sleep(0.4 * (attempt + 1))
    raise DatabaseBusy(str(last))


class DatabaseBusy(RuntimeError):
    pass


@contextmanager
def ro(db_path: Path):
    """Short-lived read-only connection (lets `bearings load/profile` run while the server is up)."""
    con = connect(db_path, read_only=True, retries=5)
    try:
        yield con
    finally:
        con.close()


def qi(name: str) -> str:
    """Quote an identifier."""
    return '"' + str(name).replace('"', '""') + '"'


def fq(schema: str, table: str) -> str:
    return f"{qi(schema)}.{qi(table)}"


def safe_name(name: str) -> str:
    n = re.sub(r"[^0-9a-zA-Z_]+", "_", name.strip()).strip("_").lower()
    if not n:
        n = "t"
    if n[0].isdigit():
        n = "t_" + n
    return n


def has_meta(con, name: str) -> bool:
    """True if _meta.<name> exists (a read-only connection to an older database won't have the newer tables)."""
    return bool(con.execute("SELECT count(*) FROM duckdb_tables() WHERE schema_name=? AND table_name=? AND database_name=current_database()",
                            [META, name]).fetchone()[0])


def has_meta_column(con, table: str, column: str) -> bool:
    return bool(con.execute("SELECT count(*) FROM duckdb_columns() WHERE schema_name=? AND table_name=? AND column_name=? "
                            "AND database_name=current_database()", [META, table, column]).fetchone()[0])


def remote_aliases(con) -> dict[str, dict]:
    """alias -> {connection, catalog, schema, attached_at, synced_at} for attached remote schemas."""
    if not has_meta(con, "remote_sources"):
        return {}
    cur = con.execute(f"SELECT alias, connection, catalog, schema, attached_at, synced_at FROM {META}.remote_sources ORDER BY alias")
    return {r[0]: dict(zip(["alias", "connection", "catalog", "schema", "attached_at", "synced_at"], r)) for r in cur.fetchall()}


def user_tables(con) -> list[tuple[str, str]]:
    """Local DuckDB tables only (remote tables have no data here)."""
    return con.execute(
        """SELECT table_schema, table_name FROM information_schema.tables
           WHERE table_schema NOT IN ('_meta','information_schema','pg_catalog')
             AND table_catalog = current_database()
           ORDER BY 1,2"""
    ).fetchall()


# ---------- annotations (SQLite, survives DuckDB rebuilds) ----------

ANN_DDL = """
CREATE TABLE IF NOT EXISTS annotations (
  schema_name TEXT NOT NULL, table_name TEXT NOT NULL, column_name TEXT NOT NULL DEFAULT '',
  tags TEXT DEFAULT '', cdm_entity TEXT DEFAULT '', cdm_attribute TEXT DEFAULT '',
  notes TEXT DEFAULT '', updated_at TEXT,
  PRIMARY KEY (schema_name, table_name, column_name)
);
CREATE TABLE IF NOT EXISTS dismissed_insights (
  schema_name TEXT NOT NULL, table_name TEXT NOT NULL, kind TEXT NOT NULL, item TEXT NOT NULL, dismissed_at TEXT,
  PRIMARY KEY (schema_name, table_name, kind, item)
);
"""


def ann_connect(db_path: Path) -> sqlite3.Connection:
    p = annotations_path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    c.executescript(ANN_DDL)
    return c


# ---------- clean-up ----------

def _insight_tables(con) -> tuple[str, ...]:
    return tuple(m for m in ("time_profile", "dependencies", "code_values", "conditional_fill", "optional_groups") if has_meta(con, m))


def drop_table(con, schema: str, table: str) -> None:
    if has_meta(con, "remote_tables") and con.execute(
            f"SELECT count(*) FROM {META}.remote_tables WHERE alias=? AND table_name=? AND NOT dropped", [schema, table]).fetchone()[0]:
        # the local cache of a remote table: drop the rows, keep what describes the remote table (profile, keys, relationships)
        con.execute(f"DROP TABLE IF EXISTS {fq(schema, table)}")
        for m in ("load_log", "comments"):
            con.execute(f"DELETE FROM {META}.{m} WHERE schema_name=? AND table_name=?", [schema, table])
        con.execute(f"DELETE FROM {META}.remote_cache WHERE alias=? AND table_name=?", [schema, table])
        return
    con.execute(f"DROP TABLE IF EXISTS {fq(schema, table)}")
    for m in ("load_log", "comments", "table_profile", "column_profile") + _insight_tables(con) + (("key_fingerprint", "key_values") if has_meta(con, "key_values") else ()):
        con.execute(f"DELETE FROM {META}.{m} WHERE schema_name=? AND table_name=?", [schema, table])
    con.execute(f"DELETE FROM {META}.relationships WHERE (from_schema=? AND from_table=?) OR (to_schema=? AND to_table=?)",
                [schema, table, schema, table])
    if has_meta(con, "remote_cache"):
        con.execute(f"DELETE FROM {META}.remote_cache WHERE alias=? AND table_name=?", [schema, table])


def drop_schema(con, schema: str) -> int:
    n = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema=?", [schema]).fetchone()[0]
    if schema == "main":
        for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall():
            con.execute(f"DROP TABLE IF EXISTS {fq('main', t)}")
    else:
        con.execute(f"DROP SCHEMA IF EXISTS {qi(schema)} CASCADE")
    for m in ("load_log", "comments", "table_profile", "column_profile") + _insight_tables(con) + (("key_fingerprint", "key_values") if has_meta(con, "key_values") else ()):
        con.execute(f"DELETE FROM {META}.{m} WHERE schema_name=?", [schema])
    con.execute(f"DELETE FROM {META}.relationships WHERE from_schema=? OR to_schema=?", [schema, schema])
    if schema in remote_aliases(con):  # an attached Databricks schema: forget its cached metadata too
        for t in ("remote_tables", "remote_columns", "sync_log", "remote_sources") + (("remote_cache",) if has_meta(con, "remote_cache") else ()):
            con.execute(f"DELETE FROM {META}.{t} WHERE alias=?", [schema])
    return n


def delete_annotations(db_path: Path, schema: str | None = None, table: str | None = None) -> int:
    p = annotations_path(db_path)
    if not p.exists():
        return 0
    c = ann_connect(db_path)
    try:
        if schema and table:
            cur = c.execute("DELETE FROM annotations WHERE schema_name=? AND table_name=?", (schema, table))
        elif schema:
            cur = c.execute("DELETE FROM annotations WHERE schema_name=?", (schema,))
        else:
            cur = c.execute("DELETE FROM annotations")
        c.commit()
        return cur.rowcount
    finally:
        c.close()


def compact(db_path: Path) -> tuple[int, int]:
    """DuckDB doesn't shrink files after drops: copy into a fresh file and swap it in."""
    db_path = Path(db_path)
    before = db_path.stat().st_size
    tmp = db_path.with_name(db_path.stem + ".compact.duckdb")
    if tmp.exists():
        tmp.unlink()
    c = duckdb.connect()
    c.execute(f"ATTACH '{db_path}' AS src (READ_ONLY)")
    c.execute(f"ATTACH '{tmp}' AS dst")
    c.execute("COPY FROM DATABASE src TO dst")
    c.close()
    tmp.replace(db_path)
    wal = db_path.with_name(db_path.name + ".wal")
    if wal.exists():
        wal.unlink()
    return before, db_path.stat().st_size
