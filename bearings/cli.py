"""`bearings` command line: load, comments, profile, relate, info, report, serve."""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import List, Optional

import typer

from . import loader, profiler, relationships
from .db import (DatabaseBusy, annotations_path, compact as compact_db, connect, default_db_path, delete_annotations,
                 drop_schema, drop_table, user_tables)

app = typer.Typer(add_completion=False, no_args_is_help=True,
                  help="Bearings – get your bearings in unfamiliar source data: load, profile, search and relate exports for data modelling (DuckDB).")

DbOpt = typer.Option(None, "--db", help="DuckDB file (default: $BEARINGS_DB or ./data/bearings.duckdb)")
SchemaOpt = typer.Option(None, "--schema", "-s", help="Limit to this schema (repeatable)")


def _db(db: Optional[Path]) -> Path:
    return Path(db).resolve() if db else default_db_path()


def _rw(db: Path):
    try:
        return connect(db, read_only=False, retries=2)
    except DatabaseBusy:
        typer.secho("The database is locked by another process (another `bearings` command, or a DuckDB client like DBeaver). "
                    "The web server only holds it briefly per request, so retry in a moment.", fg="red")
        raise typer.Exit(1)


@app.command()
def load(path: Path = typer.Argument(..., exists=True, help="A .csv/.parquet file, or a folder of them. A sub-folder of parquet part-files becomes one table."),
         schema: str = typer.Option("main", "--schema", "-s", help="Target schema, e.g. the source system (pms, crm, finance)"),
         append: bool = typer.Option(False, "--append", help="Append to existing tables instead of replacing"),
         all_varchar: bool = typer.Option(False, "--all-varchar", help="Load CSV columns as text (keeps leading zeros / raw formats)"),
         delim: Optional[str] = typer.Option(None, "--delim", help="CSV delimiter if auto-detect fails"),
         db: Optional[Path] = DbOpt):
    """Load CSV / Parquet exports into DuckDB."""
    dbp = _db(db)
    con = _rw(dbp)
    typer.echo(f"Loading {path} → {dbp} (schema {schema})")
    t0 = time.time()
    res = loader.load(con, path, schema=schema, mode="append" if append else "replace", all_varchar=all_varchar, delim=delim, echo=typer.echo)
    con.close()
    typer.secho(f"Done: {len(res)} tables in {time.time() - t0:.1f}s. Next: bearings profile", fg="green")


@app.command()
def comments(file: Path = typer.Argument(..., exists=True, help="CSV with table_name, column_name, comment [, table_schema]"),
             schema: Optional[str] = typer.Option(None, "--schema", "-s", help="Apply to this schema only"),
             db: Optional[Path] = DbOpt):
    """Import table/column descriptions (e.g. Databricks information_schema.columns export) – they become searchable."""
    con = _rw(_db(db))
    loader.load_comments(con, file, schema=schema, echo=typer.echo)
    con.close()


@app.command()
def profile(table: Optional[List[str]] = typer.Option(None, "--table", "-t", help="schema.table (repeatable). Default: all tables"),
            only_new: bool = typer.Option(False, "--only-new", help="Skip tables that already have a profile"),
            sample_rows: Optional[int] = typer.Option(None, "--sample-rows", help="Profile a random sample of N rows for big tables"),
            approx: bool = typer.Option(False, "--approx", help="Approximate distinct counts (faster on very large tables)"),
            top: int = typer.Option(10, "--top", help="Top-N values to keep per column"),
            schema: Optional[List[str]] = SchemaOpt,
            db: Optional[Path] = DbOpt):
    """Run the standard profile and store it in _meta (shown in the web app)."""
    con = _rw(_db(db))
    tables = user_tables(con)
    if schema:
        tables = [(s_, t) for s_, t in tables if s_ in schema]
    if table:
        want = {t.lower() for t in table}
        tables = [(s, t) for s, t in tables if f"{s}.{t}".lower() in want or t.lower() in want]
    if only_new:
        done = set(con.execute("SELECT schema_name, table_name FROM _meta.table_profile").fetchall())
        tables = [x for x in tables if x not in done]
    if not tables:
        typer.echo("Nothing to profile.")
    for s, t in tables:
        t0 = time.time()
        try:
            tp, cols = profiler.profile_table(con, s, t, sample_rows=sample_rows, approx=approx, top_n=top)
            profiler.save(con, tp, cols)
            flags = sum(1 for c in cols if c["flags"])
            typer.echo(f"  ✓ {s}.{t:<40} {tp['row_count']:>12,} rows  {len(cols):>4} cols  "
                       f"PK: {', '.join(tp['candidate_keys'][:3]) or '—':<24} {flags:>3} flagged  {time.time() - t0:.1f}s")
        except Exception as e:
            typer.secho(f"  ✗ {s}.{t}: {e}", fg="red")
    con.close()


@app.command()
def relate(min_overlap: float = typer.Option(0.5, help="Minimum share of FK values found in the key column (0-1)"),
           name_threshold: float = typer.Option(0.75, help="Name similarity needed to test a pair (0-1)"),
           deep: bool = typer.Option(False, "--deep", help="Also test *_id/_code columns whose names don't match"),
           max_pairs: int = typer.Option(5000, help="Cap on pairs to test"),
           schema: Optional[List[str]] = typer.Option(None, "--schema", "-s", help="Only within these schemas (repeatable; give 2 to find cross-system links)"),
           db: Optional[Path] = DbOpt):
    """Discover likely FK → PK relationships (needs `bearings profile` first)."""
    con = _rw(_db(db))
    t0 = time.time()
    sc = set(schema) if schema else None
    rels = relationships.discover(con, min_overlap=min_overlap, name_threshold=name_threshold, deep=deep,
                                  max_pairs=max_pairs, echo=typer.echo, schemas=sc)
    relationships.save(con, rels, schemas=sc)
    for r in sorted(rels, key=lambda r: -r["confidence"])[:40]:
        typer.echo(f"  {r['from_table']}.{r['from_column']:<28} → {r['to_table']}.{r['to_column']:<24} "
                   f"overlap {r['overlap_pct']:>6}%  conf {r['confidence']}")
    typer.secho(f"Done: {len(rels)} relationships in {time.time() - t0:.1f}s", fg="green")
    con.close()


@app.command()
def info(schema: Optional[List[str]] = SchemaOpt, db: Optional[Path] = DbOpt):
    """List loaded tables and whether they're profiled."""
    dbp = _db(db)
    if not dbp.exists():
        typer.echo(f"No database at {dbp}. Start with: bearings load <folder>")
        raise typer.Exit()
    con = connect(dbp, read_only=True, retries=2)
    rows = con.execute("""
      SELECT t.table_schema, t.table_name, p.row_count, p.profiled_at
      FROM information_schema.tables t
      LEFT JOIN _meta.table_profile p ON p.schema_name = t.table_schema AND p.table_name = t.table_name
      WHERE t.table_schema NOT IN ('_meta','information_schema','pg_catalog') ORDER BY 1,2""").fetchall()
    typer.echo(f"{dbp}\n")
    if schema:
        rows = [r for r in rows if r[0] in schema]
    for s, t, n, at in rows:
        typer.echo(f"  {s + '.' + t:<50} {('' if n is None else f'{n:,}'):>12}  {'profiled ' + str(at)[:16] if at else 'not profiled'}")
    rel = con.execute("SELECT count(*) FROM _meta.relationships").fetchone()[0]
    typer.echo(f"\n{len(rows)} tables, {rel} relationships")


@app.command()
def report(out: Path = typer.Option(Path("dm_catalog.xlsx"), "--out", "-o", help=".xlsx or .json"),
           schema: Optional[List[str]] = SchemaOpt,
           db: Optional[Path] = DbOpt):
    """Export catalog + profile + annotations + relationships to Excel or JSON."""
    from . import catalog, export
    dbp = _db(db)
    con = connect(dbp, read_only=True, retries=2)
    sc = set(schema) if schema else None
    cat = catalog.scoped(catalog.build(con, dbp), sc)
    if out.suffix.lower() == ".json":
        out.write_text(export.as_json(con, cat, sc), encoding="utf-8")
    else:
        out.write_bytes(export.excel(con, cat, sc))
    typer.secho(f"Wrote {out}", fg="green")


@app.command()
def drop(target: str = typer.Argument(..., help="schema.table, or a schema name to drop the whole schema"),
         annotations: bool = typer.Option(False, "--annotations", help="Also delete the annotations (tags / CDM mappings) of what you drop"),
         yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask for confirmation"),
         db: Optional[Path] = DbOpt):
    """Remove a table or a whole schema (data + profile + relationships). Annotations are kept unless --annotations."""
    dbp = _db(db)
    con = _rw(dbp)
    schemas = {s_ for s_, _ in user_tables(con)}
    if "." in target:
        s_, t = target.split(".", 1)
        if (s_, t) not in set(user_tables(con)):
            typer.secho(f"No table {target}", fg="red"); raise typer.Exit(1)
        what = f"table {target}"
    elif target in schemas:
        s_, t = target, None
        what = f"schema {target} ({sum(1 for x, _ in user_tables(con) if x == target)} tables)"
    else:
        typer.secho(f"No table or schema called {target}. Schemas: {', '.join(sorted(schemas)) or '—'}", fg="red"); raise typer.Exit(1)
    if not yes and not typer.confirm(f"Drop {what}{' and its annotations' if annotations else ''}?"):
        raise typer.Exit()
    if t:
        drop_table(con, s_, t)
    else:
        drop_schema(con, s_)
    con.execute("CHECKPOINT")
    con.close()
    n = delete_annotations(dbp, s_, t) if annotations else 0
    typer.secho(f"Dropped {what}" + (f", {n} annotations deleted" if annotations else " (annotations kept)") +
                ". Run `bearings compact` to shrink the file.", fg="green")


@app.command()
def reset(schema: Optional[List[str]] = typer.Option(None, "--schema", "-s", help="Only reset these schema(s) (repeatable); default: everything"),
          annotations: bool = typer.Option(False, "--annotations", help="Also delete annotations (tags / CDM mappings / notes)"),
          yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask for confirmation"),
          db: Optional[Path] = DbOpt):
    """Start fresh: delete the database (or only some schemas). Annotations are kept unless --annotations."""
    dbp = _db(db)
    if not dbp.exists():
        typer.echo(f"Nothing to reset – {dbp} doesn't exist.")
        if annotations and annotations_path(dbp).exists() and (yes or typer.confirm("Delete the annotations file?")):
            annotations_path(dbp).unlink(); typer.echo("Annotations deleted.")
        raise typer.Exit()
    if schema:
        what = f"schema(s) {', '.join(schema)} in {dbp.name}"
    else:
        what = f"the whole database {dbp}"
    if not yes and not typer.confirm(f"Reset {what}{' including annotations' if annotations else ' (annotations kept)'}?"):
        raise typer.Exit()
    if schema:
        con = _rw(dbp)
        for s_ in schema:
            n = drop_schema(con, s_)
            typer.echo(f"  ✓ dropped schema {s_} ({n} tables)")
            if annotations:
                typer.echo(f"    {delete_annotations(dbp, s_)} annotations deleted")
        con.execute("CHECKPOINT")
        con.close()
        before, after = compact_db(dbp)
        typer.echo(f"  ✓ compacted {before / 1e6:.1f} MB → {after / 1e6:.1f} MB")
    else:
        _rw(dbp).close()  # fails cleanly if another process holds the file
        for f in (dbp, dbp.with_name(dbp.name + ".wal")):
            if f.exists():
                f.unlink()
        typer.echo(f"  ✓ deleted {dbp.name}")
        if annotations and annotations_path(dbp).exists():
            annotations_path(dbp).unlink()
            typer.echo(f"  ✓ deleted {annotations_path(dbp).name}")
    typer.secho("Done. Reload with: uv run bearings load <folder> --schema <name>", fg="green")


@app.command()
def compact(db: Optional[Path] = DbOpt):
    """Shrink the database file after dropping tables (DuckDB doesn't give space back by itself)."""
    dbp = _db(db)
    _rw(dbp).close()
    before, after = compact_db(dbp)
    typer.secho(f"{dbp.name}: {before / 1e6:.1f} MB → {after / 1e6:.1f} MB", fg="green")


@app.command()
def demo(out: Path = typer.Option(Path("demo"), "--out", "-o", help="Folder for the generated export files"),
         scale: float = typer.Option(1.0, "--scale", help="Data volume multiplier (1 = ~30k reservations, 90k charges)"),
         files_only: bool = typer.Option(False, "--files-only", help="Only write the files; don't load/profile"),
         db: Optional[Path] = typer.Option(Path("data/demo.duckdb"), "--db", help="Demo database (kept apart from your real one)")):
    """Generate a fictional hotel dataset (PMS + CRM) and load, profile and relate it – ready to explore."""
    from . import demo as demo_mod
    typer.echo(f"Generating demo data (scale {scale})…")
    counts = demo_mod.generate(out, scale=scale, echo=typer.echo)
    typer.echo("  " + ", ".join(f"{k} {v:,}" for k, v in counts.items()))
    if files_only:
        typer.secho(f"Done. Load it with: uv run bearings load {out}/exports/pms -s pms && uv run bearings load {out}/exports/crm -s crm", fg="green")
        return
    dbp = Path(db).resolve()
    if dbp.exists():
        dbp.unlink()
    con = _rw(dbp)
    for src in ("pms", "crm"):
        loader.load(con, out / "exports" / src, schema=src, echo=typer.echo)
    loader.load_comments(con, out / "comments.csv", echo=typer.echo)
    for s, t in user_tables(con):
        tp, cols = profiler.profile_table(con, s, t)
        profiler.save(con, tp, cols)
    typer.echo(f"  ✓ profiled {len(user_tables(con))} tables")
    rels = relationships.discover(con, deep=True, echo=lambda *_: None)
    relationships.save(con, rels)
    typer.echo(f"  ✓ {len(rels)} relationships found")
    con.close()
    typer.secho(f"\nReady. Start the app on the demo database:\n  uv run bearings serve --db {db}\n", fg="green")


@app.command()
def serve(port: int = typer.Option(8765, "--port", "-p"), host: str = typer.Option("127.0.0.1", "--host"),
          reload: bool = typer.Option(False, "--reload", help="Auto-reload on code changes (dev)"),
          schema: Optional[List[str]] = typer.Option(None, "--schema", "-s", help="Open the app scoped to these schema(s); can be changed in the UI"),
          db: Optional[Path] = DbOpt):
    """Start the web app at http://127.0.0.1:8765"""
    import uvicorn
    os.environ["BEARINGS_DB"] = str(_db(db))
    os.environ["BEARINGS_SCHEMAS"] = ",".join(schema or [])
    typer.secho(f"Bearings → http://{host}:{port}   (db: {os.environ['BEARINGS_DB']})", fg="green")
    uvicorn.run("bearings.api:app", host=host, port=port, reload=reload, log_level="warning")


if __name__ == "__main__":
    app()
