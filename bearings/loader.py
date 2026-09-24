"""Load local exports (CSV, Parquet, JSON, Excel – see `bearings.loaders`) into DuckDB."""
from __future__ import annotations

import csv
import re
from datetime import datetime
from pathlib import Path

from .db import META, fq, qi, safe_name
from .loaders import LoadItem, LoadOptions, reader_for, readers


def _hidden(p: Path, root: Path) -> bool:
    """Spark / Delta bookkeeping (_SUCCESS, _delta_log/, .crc) and editor lock files (~$book.xlsx)."""
    return any(part.startswith((".", "_", "~$")) for part in p.relative_to(root).parts)


_PART = re.compile(r"^(part|data|chunk|file|run)?[-_]?\d+", re.I)


def looks_like_parts(folder: Path, files: list[Path], reader) -> bool:
    """Is this folder one table split into files (Spark / Databricks export, hive partitions, numbered chunks)
    rather than a folder of different tables (customer.csv, orders.csv)?"""
    if len(files) == 1:
        return True
    if any("=" in part for f in files for part in f.relative_to(folder).parts[:-1]):
        return True                       # hive partitions: year=2026/month=01/…
    stems = [reader.stem(f) for f in files]
    if all(_PART.match(st) for st in stems):
        return True                       # part-00000-….snappy.parquet, 000001.csv
    bases = {re.sub(r"([-_.]?\d+)+$", "", st).lower() for st in stems}
    return len(bases) == 1 and bases != {""}   # reservation_001.csv, reservation_002.csv


def discover(path: Path, opts: LoadOptions | None = None, echo=lambda *_: None) -> list[LoadItem]:
    """Tables found at `path` (a file or a folder).

    In a folder: every supported file is a table (an Excel workbook: one per sheet), and a sub-folder of
    part-files (typical Databricks / Spark export, hive partitions, numbered chunks) is one table named after
    the sub-folder. Any other sub-folder contributes its files one by one (e.g. a folder of workbooks)."""
    path, opts = Path(path), opts or LoadOptions()
    out: list[LoadItem] = []

    def from_file(p: Path):
        r = reader_for(p)
        if r is None:
            return
        if not r.available():
            echo(f"  ✗ {p.name}: the {r.label} reader needs the Python package '{r.needs}'")
            return
        try:
            out.extend(r.items_for_file(p, opts))
        except Exception as e:  # an unreadable file shouldn't stop the others
            echo(f"  ✗ {p.name}: {str(e).splitlines()[0] if str(e) else type(e).__name__}")

    if path.is_file():
        from_file(path)
        return _unique(out)
    for child in sorted(path.iterdir()):
        if child.name.startswith((".", "_", "~$")):
            continue
        if child.is_file():
            from_file(child)
            continue
        if not child.is_dir():
            continue
        files = sorted(p for p in child.rglob("*") if p.is_file() and not _hidden(p, child))
        for r in readers():
            if not r.folder_as_table:
                continue
            parts = [p for p in files if r.matches(p)]
            if parts and looks_like_parts(child, parts, r):
                out.extend(r.items_for_folder(child, parts, opts))
                break
        else:
            for p in sorted(x for x in child.iterdir() if x.is_file() and not x.name.startswith((".", "_", "~$"))):
                from_file(p)
    return _unique(out)


def _unique(items: list[LoadItem]) -> list[LoadItem]:
    """Two sources with the same table name (guest.csv and guest.parquet): the second becomes guest_2."""
    seen: set[str] = set()
    for it in items:
        base, n = it.table, 1
        while it.table in seen:
            n += 1
            it.table = f"{base}_{n}"
        seen.add(it.table)
    return items


def load(con, path: Path, schema: str = "main", mode: str = "replace", all_varchar: bool = False, delim: str | None = None,
         sheets: list[str] | None = None, header_row: int | None = None, items: list[LoadItem] | None = None,
         echo=print) -> list[dict]:
    """Load every table found at `path` (or the given `items`) into `schema`. mode: replace | append."""
    schema = safe_name(schema) if schema != "main" else "main"
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {qi(schema)}")
    opts = LoadOptions(all_varchar=all_varchar, delim=delim, sheets=list(sheets or []), header_row=header_row)
    results = []
    if items is None:
        items = discover(path, opts, echo=echo)
    if not items:
        from .loaders import supported_extensions
        echo(f"No loadable files found in {path} (supported: {', '.join(sorted(set(supported_extensions())))})")
    from .loaders import get as get_reader
    for it in items:
        target = fq(schema, it.table)
        try:
            reader = get_reader(it.format)
            with reader.relation(con, it, opts) as rel:
                exists = con.execute(
                    "SELECT count(*) FROM information_schema.tables WHERE table_schema=? AND table_name=?",
                    [schema, it.table]).fetchone()[0]
                if mode == "append" and exists:
                    con.execute(f"INSERT INTO {target} BY NAME SELECT * FROM {rel}")
                else:
                    con.execute(f"CREATE OR REPLACE TABLE {target} AS SELECT * FROM {rel}")
            rows = con.execute(f"SELECT count(*) FROM {target}").fetchone()[0]
            ncol = len(con.execute(f"DESCRIBE {target}").fetchall())
            con.execute(f"INSERT INTO {META}.load_log VALUES (?,?,?,?,?,?,?)",
                        [schema, it.table, it.source, it.format, rows, ncol, datetime.now()])
            # stale profile rows no longer match the new data
            if mode == "replace":
                for t in ("column_profile", "table_profile"):
                    con.execute(f"DELETE FROM {META}.{t} WHERE schema_name=? AND table_name=?", [schema, it.table])
            echo(f"  ✓ {schema}.{it.table:<40} {rows:>12,} rows  {ncol:>4} cols  ← {it.label}")
            results.append({"schema": schema, "table": it.table, "rows": rows, "columns": ncol, "format": it.format, "source": it.source})
        except Exception as e:  # keep going with the other files
            echo(f"  ✗ {schema}.{it.table}: {str(e).splitlines()[0] if str(e) else type(e).__name__}")
            results.append({"schema": schema, "table": it.table, "error": str(e).splitlines()[0] if str(e) else type(e).__name__,
                            "format": it.format, "source": it.source})
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
