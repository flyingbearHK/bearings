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
        except duckdb.IOException as e:  # lock held by another process
            last = e
            time.sleep(0.4 * (attempt + 1))
    raise DatabaseBusy(str(last))


class DatabaseBusy(RuntimeError):
    pass


@contextmanager
def ro(db_path: Path):
    """Short-lived read-only connection (lets `bearings load/profile` run while the server is up)."""
    con = connect(db_path, read_only=True, retries=3)
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


def user_tables(con) -> list[tuple[str, str]]:
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
"""


def ann_connect(db_path: Path) -> sqlite3.Connection:
    p = annotations_path(db_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(p))
    c.row_factory = sqlite3.Row
    c.execute(ANN_DDL)
    return c


# ---------- clean-up ----------

def drop_table(con, schema: str, table: str) -> None:
    con.execute(f"DROP TABLE IF EXISTS {fq(schema, table)}")
    for m in ("load_log", "comments", "table_profile", "column_profile"):
        con.execute(f"DELETE FROM {META}.{m} WHERE schema_name=? AND table_name=?", [schema, table])
    con.execute(f"DELETE FROM {META}.relationships WHERE (from_schema=? AND from_table=?) OR (to_schema=? AND to_table=?)",
                [schema, table, schema, table])


def drop_schema(con, schema: str) -> int:
    n = con.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema=?", [schema]).fetchone()[0]
    if schema == "main":
        for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall():
            con.execute(f"DROP TABLE IF EXISTS {fq('main', t)}")
    else:
        con.execute(f"DROP SCHEMA IF EXISTS {qi(schema)} CASCADE")
    for m in ("load_log", "comments", "table_profile", "column_profile"):
        con.execute(f"DELETE FROM {META}.{m} WHERE schema_name=?", [schema])
    con.execute(f"DELETE FROM {META}.relationships WHERE from_schema=? OR to_schema=?", [schema, schema])
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
