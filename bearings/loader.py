"""Load CSV / Parquet exports (e.g. from Databricks) into DuckDB."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .db import META, fq, qi, safe_name

CSV_EXT = (".csv", ".csv.gz", ".tsv", ".txt")
PQ_EXT = (".parquet", ".pq")


def _is_csv(p: Path) -> bool:
    return p.name.lower().endswith(CSV_EXT)


def _is_pq(p: Path) -> bool:
    return p.name.lower().endswith(PQ_EXT)


def _stem(p: Path) -> str:
    n = p.name
    for ext in sorted(CSV_EXT + PQ_EXT, key=len, reverse=True):
        if n.lower().endswith(ext):
            return n[: -len(ext)]
    return p.stem


def discover(path: Path) -> list[tuple[str, str, str]]:
    """Return (table_name, source_expr, format). A directory holding parquet
    part files (typical Databricks / Spark export) becomes one table."""
    path = Path(path)
    out: list[tuple[str, str, str]] = []
    if path.is_file():
        if _is_pq(path):
            out.append((safe_name(_stem(path)), str(path), "parquet"))
        elif _is_csv(path):
            out.append((safe_name(_stem(path)), str(path), "csv"))
        return out
    for child in sorted(path.iterdir()):
        if child.name.startswith((".", "_")):
            continue
        if child.is_dir():
            parts = [p for p in child.rglob("*") if p.is_file() and _is_pq(p)]
            csvs = [p for p in child.rglob("*") if p.is_file() and _is_csv(p)]
            if parts:
                out.append((safe_name(child.name), str(child / "**" / "*.parquet"), "parquet"))
            elif csvs:
                out.append((safe_name(child.name), str(child / "**" / "*.csv*"), "csv"))
        elif _is_pq(child):
            out.append((safe_name(_stem(child)), str(child), "parquet"))
        elif _is_csv(child):
            out.append((safe_name(_stem(child)), str(child), "csv"))
    return out


def _reader(src: str, fmt: str, all_varchar: bool, delim: str | None) -> str:
    s = src.replace("'", "''")
    if fmt == "parquet":
        return f"read_parquet('{s}', union_by_name=true, hive_partitioning=true)"
    opts = ["header=true", "sample_size=-1" if not all_varchar else "all_varchar=true", "union_by_name=true"]
    if delim:
        opts.append(f"delim='{delim}'")
    return f"read_csv('{s}', {', '.join(opts)})"


def load(con, path: Path, schema: str = "main", mode: str = "replace",
         all_varchar: bool = False, delim: str | None = None, echo=print) -> list[dict]:
    schema = safe_name(schema) if schema != "main" else "main"
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {qi(schema)}")
    results = []
    items = discover(path)
    if not items:
        echo(f"No .csv/.parquet files found in {path}")
    for table, src, fmt in items:
        reader = _reader(src, fmt, all_varchar, delim)
        target = fq(schema, table)
        try:
            exists = con.execute(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema=? AND table_name=?",
                [schema, table]).fetchone()[0]
            if mode == "append" and exists:
                con.execute(f"INSERT INTO {target} BY NAME SELECT * FROM {reader}")
            else:
                con.execute(f"CREATE OR REPLACE TABLE {target} AS SELECT * FROM {reader}")
            rows = con.execute(f"SELECT count(*) FROM {target}").fetchone()[0]
            ncol = len(con.execute(f"DESCRIBE {target}").fetchall())
            con.execute(f"INSERT INTO {META}.load_log VALUES (?,?,?,?,?,?,?)",
                        [schema, table, src, fmt, rows, ncol, datetime.now()])
            # stale profile rows no longer match the new data
            if mode == "replace":
                for t in ("column_profile", "table_profile"):
                    con.execute(f"DELETE FROM {META}.{t} WHERE schema_name=? AND table_name=?", [schema, table])
            echo(f"  ✓ {schema}.{table:<40} {rows:>12,} rows  {ncol:>4} cols  ← {Path(src).name if '*' not in src else src}")
            results.append({"schema": schema, "table": table, "rows": rows, "columns": ncol})
        except Exception as e:  # keep going with the other files
            echo(f"  ✗ {schema}.{table}: {e}")
    return results


def load_comments(con, file: Path, schema: str | None = None, echo=print) -> int:
    """Import column/table comments from a CSV, e.g. an export of Databricks
    `information_schema.columns` (needs table_name, column_name, comment).
    Rows with an empty column_name are treated as table comments."""
    with open(file, newline="", encoding="utf-8-sig") as f:
        rdr = csv.DictReader(f)
        cols = {c.lower(): c for c in (rdr.fieldnames or [])}
        need = {"table_name", "comment"}
        if not need.issubset(cols):
            raise ValueError(f"comments file needs columns {need}, found {list(cols)}")
        rows = []
        for r in rdr:
            t = safe_name(r[cols["table_name"]] or "")
            c = (r.get(cols.get("column_name", ""), "") or "").strip()
            cm = (r[cols["comment"]] or "").strip()
            if not cm:
                continue
            s = schema or safe_name(r.get(cols.get("table_schema", ""), "") or "") or None
            rows.append((s, t, c, cm))
    # match to loaded tables case-insensitively; schema optional
    loaded = con.execute(
        "SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('_meta','information_schema','pg_catalog')"
    ).fetchall()
    by_table: dict[str, list[str]] = {}
    for s, t in loaded:
        by_table.setdefault(t.lower(), []).append(s)
    n = 0
    for s, t, c, cm in rows:
        schemas = [s] if s and s in by_table.get(t, []) else by_table.get(t, [])
        for sch in schemas:
            con.execute(f"DELETE FROM {META}.comments WHERE schema_name=? AND table_name=? AND lower(column_name)=lower(?)", [sch, t, c])
            con.execute(f"INSERT INTO {META}.comments VALUES (?,?,?,?)", [sch, t, c, cm])
            n += 1
    echo(f"  ✓ {n} comments imported ({len(rows)} in file)")
    return n
