"""`bearings` command line: load, comments, profile, relate, info, report, serve – plus remote (Databricks) sources."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import List, Optional

import typer

from . import insights, loader, profiler, relationships
from .db import (DatabaseBusy, annotations_path, compact as compact_db, connect, default_db_path, delete_annotations,
                 drop_schema, drop_table, remote_aliases, user_tables)

connect_db = connect

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
def load(path: Path = typer.Argument(..., exists=True, help="A file (.csv .tsv .parquet .json .jsonl .xlsx …) or a folder of them. "
                                                           "A sub-folder of part-files becomes one table; an Excel workbook one table per sheet."),
         schema: str = typer.Option("main", "--schema", "-s", help="Target schema, e.g. the source system (pms, crm, finance)"),
         append: bool = typer.Option(False, "--append", help="Append to existing tables instead of replacing"),
         all_varchar: bool = typer.Option(False, "--all-varchar", help="Load CSV / Excel columns as text (keeps leading zeros / raw formats)"),
         delim: Optional[str] = typer.Option(None, "--delim", help="CSV delimiter if auto-detect fails"),
         sheet: Optional[List[str]] = typer.Option(None, "--sheet", help="Excel: only this sheet (repeatable). Default: every non-empty sheet"),
         header_row: Optional[int] = typer.Option(None, "--header-row", help="Excel: row number of the header (default: first non-empty row)"),
         dry_run: bool = typer.Option(False, "--dry-run", help="Only list the tables that would be loaded"),
         db: Optional[Path] = DbOpt):
    """Load local exports (CSV / TSV, Parquet, JSON / NDJSON, Excel) into DuckDB."""
    if dry_run:
        from .loaders import LoadOptions
        items = loader.discover(path, LoadOptions(sheets=list(sheet or []), header_row=header_row), echo=typer.echo)
        for it in items:
            typer.echo(f"  {schema}.{it.table:<40} {it.format:<8} ← {it.label}")
        typer.echo(f"{len(items)} table(s) would be loaded.")
        return
    dbp = _db(db)
    con = _rw(dbp)
    typer.echo(f"Loading {path} → {dbp} (schema {schema})")
    t0 = time.time()
    res = loader.load(con, path, schema=schema, mode="append" if append else "replace", all_varchar=all_varchar, delim=delim,
                      sheets=sheet, header_row=header_row, echo=typer.echo)
    con.close()
    ok = [r for r in res if "error" not in r]
    failed = len(res) - len(ok)
    typer.secho(f"Done: {len(ok)} tables in {time.time() - t0:.1f}s{f', {failed} failed' if failed else ''}. Next: bearings profile",
                fg="yellow" if failed else "green")


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
            only_stale: bool = typer.Option(False, "--only-stale", help="Remote tables: only those never profiled or changed since (after a sync)"),
            sample_rows: Optional[int] = typer.Option(None, "--sample-rows", help="Profile a random sample of N rows for big tables (remote default 200,000)"),
            approx: bool = typer.Option(False, "--approx", help="Approximate distinct counts (faster on very large tables)"),
            top: int = typer.Option(10, "--top", help="Top-N values to keep per column"),
            remote: bool = typer.Option(False, "--remote", help="Also profile every attached remote table (runs on the SQL warehouse)"),
            no_fingerprints: bool = typer.Option(False, "--no-fingerprints", help="Remote: don't store key values locally (no remote relationships / value search)"),
            schema: Optional[List[str]] = SchemaOpt,
            db: Optional[Path] = DbOpt):
    """Run the standard profile and store it in _meta (shown in the web app).

    Remote (Databricks) tables are profiled on the SQL warehouse when you name them with -s <alias> / -t <alias>.<table>
    (or --remote for all): exact counts over the whole table, a sample for top values and patterns, and key
    fingerprints for relationship discovery."""
    dbp = _db(db)
    con = _rw(dbp)
    tables = user_tables(con)
    aliases = set(remote_aliases(con))
    if schema:
        tables = [(s_, t) for s_, t in tables if s_ in schema]
    if table:
        want = {t.lower() for t in table}
        tables = [(s, t) for s, t in tables if f"{s}.{t}".lower() in want or t.lower() in want]
    if only_new:
        done = set(con.execute("SELECT schema_name, table_name FROM _meta.table_profile").fetchall())
        tables = [x for x in tables if x not in done]
    for s, t in tables:
        t0 = time.time()
        try:
            tp, cols = profiler.profile_table(con, s, t, sample_rows=sample_rows, approx=approx, top_n=top)
            profiler.save(con, tp, cols)
            flags = sum(1 for c in cols if c["flags"])
            typer.echo(f"  ✓ {s}.{t:<40} {tp['row_count']:>12,} rows  {len(cols):>4} cols  "
                       f"PK: {', '.join(tp['candidate_keys'][:3]) or '—':<24} {flags:>3} flagged  {time.time() - t0:.1f}s")
            for err in tp.get("errors", [])[:5]:
                typer.secho(f"      ⚠ {err}", fg="yellow")
        except Exception as e:
            typer.secho(f"  ✗ {s}.{t}: {e}", fg="red")
    con.close()

    # remote tables: only when asked for (they run on the warehouse)
    rtargets = []
    if aliases:
        from .remote import profile as rprofile
        want_alias = [a for a in (schema or []) if a in aliases]
        want_tables = [x for x in (table or []) if x.split(".", 1)[0] in aliases]
        if remote or want_alias or want_tables:
            rtargets = rprofile.targets(dbp, aliases=want_alias or None, tables=want_tables or None,
                                        only_new=only_new, only_stale=only_stale)
        elif not tables:
            typer.echo(f"Remote tables are profiled on the SQL warehouse only when named: bearings profile -s {sorted(aliases)[0]} (or --remote)")
    if not tables and not rtargets:
        typer.echo("Nothing to profile.")
    if rtargets:
        from .remote import profile as rprofile
        typer.echo(f"Profiling {len(rtargets)} remote table(s) on Databricks (exact counts + a sample of "
                   f"{(sample_rows or rprofile.DEFAULT_SAMPLE):,} rows for big tables)…")
    fails = 0
    if rtargets:
        ok, fails = rprofile.profile_many(dbp, rtargets, sample_rows=sample_rows or rprofile.DEFAULT_SAMPLE, top_n=top,
                                          fingerprints=not no_fingerprints, echo=typer.echo)
    if rtargets:
        typer.secho(f"Remote profiling done ({len(rtargets) - fails}/{len(rtargets)}). Next: bearings relate -s {rtargets[0][0]}", fg="green")


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
        card = r.get("cardinality") or ""
        extra = ""
        if card:
            extra = f"  {card:<3} {'optional' if r.get('fk_null_pct') else 'mandatory':<9}"
            if r.get("orphan_rows"):
                extra += f" {r['orphan_rows']:,} orphan rows"
        typer.echo(f"  {r['from_table']}.{r['from_column']:<28} → {r['to_table']}.{r['to_column']:<24} "
                   f"overlap {r['overlap_pct']:>6}%  conf {r['confidence']:<5}{extra}")
    typer.secho(f"Done: {len(rels)} relationships in {time.time() - t0:.1f}s. Next: bearings insights", fg="green")
    con.close()


@app.command("insights")
def insights_cmd(table: Optional[List[str]] = typer.Option(None, "--table", "-t", help="schema.table (repeatable). Default: all profiled local / cached tables"),
                 only: Optional[str] = typer.Option(None, "--only", help="Comma-separated subset: grain,time,deps,codes,optional"),
                 sample_rows: int = typer.Option(insights.DEFAULT_SAMPLE, "--sample-rows", help="Scan a random sample of N rows of bigger tables"),
                 show: bool = typer.Option(False, "--show", help="Print candidate entities, hierarchies and dirty dependencies"),
                 schema: Optional[List[str]] = SchemaOpt,
                 db: Optional[Path] = DbOpt):
    """Modelling insights: the grain of each table, time coverage of its date columns, and dependencies between columns
    (candidate entities, hierarchies, code ↔ description pairs). Needs `bearings profile` first; runs on local and
    cached tables."""
    kinds = {k.strip() for k in only.split(",")} if only else None
    if kinds and kinds - set(insights.KINDS):
        typer.secho(f"--only takes {', '.join(insights.KINDS)}", fg="red")
        raise typer.Exit(1)
    dbp = _db(db)
    con = _rw(dbp)
    tabs = insights.targets(con, set(schema) if schema else None, table)
    if not tabs:
        typer.echo("Nothing to analyse (profile the tables first: bearings profile).")
        con.close()
        return
    t0 = time.time()
    done, errors = insights.run_many(con, tabs, sample_rows=sample_rows, only=kinds, echo=typer.echo)
    if show:
        rels = relationships.with_targets(con, catalog_columns(con))
        for r in done:
            _print_structure(con, r["schema"], r["table"], rels)
    con.close()
    typer.secho(f"Done: {len(done)} table(s) in {time.time() - t0:.1f}s" + (f", {len(errors)} failed" if errors else ""), fg="green")


@app.command("dq-rules")
def dq_rules_cmd(out: Path = typer.Option(Path("dq_rules.zip"), "--out", "-o",
                                          help=".zip (DQX + Great Expectations + Purview CSV), .yml (DQX), .json (Great Expectations) or .csv (Purview)"),
                 table: Optional[List[str]] = typer.Option(None, "--table", "-t", help="schema.table (repeatable)"),
                 errors_only: bool = typer.Option(False, "--errors-only", help="Only rules that pass on every row today"),
                 schema: Optional[List[str]] = SchemaOpt, db: Optional[Path] = DbOpt):
    """Suggest data-quality rules from the profile, insights and relationships, and export them for Databricks DQX,
    Great Expectations or Microsoft Purview."""
    from . import catalog as cat_mod, dqrules
    dbp = _db(db)
    con = connect_db(dbp, read_only=True)
    cat = cat_mod.build(con, dbp)
    tabs = [k for k in cat["tables"] if (not schema or k[0] in schema)
            and (not table or f"{k[0]}.{k[1]}".lower() in {t.lower() for t in table} or k[1].lower() in {t.lower() for t in table})]
    rules = dqrules.all_rules(con, cat, tabs)
    con.close()
    if errors_only:
        rules = [r for r in rules if r["criticality"] == "error"]
    if not rules:
        typer.echo("No rules (profile and analyse the tables first: bearings profile && bearings insights).")
        raise typer.Exit(1)
    suf = out.suffix.lower()
    if suf in (".yml", ".yaml"):
        out.write_text(dqrules.to_dqx_yaml(rules), encoding="utf-8")
    elif suf == ".json":
        out.write_text(json.dumps(dqrules.to_gx_suite(rules, out.stem), indent=2, ensure_ascii=False), encoding="utf-8")
    elif suf == ".csv":
        out.write_text(dqrules.to_csv(rules), encoding="utf-8")
    else:
        out.write_bytes(dqrules.bundle(rules))
    by = {}
    for r in rules:
        by[r["criticality"]] = by.get(r["criticality"], 0) + 1
    typer.secho(f"{len(rules)} rules for {len({(r['schema'], r['table']) for r in rules})} table(s) "
                f"({by.get('error', 0)} error, {by.get('warn', 0)} warn) → {out}", fg="green")


@app.command("duplicates")
def duplicates_cmd(table: str = typer.Argument(..., help="schema.table"),
                   threshold: float = typer.Option(0.9, help="Minimum similarity (0-1)"),
                   column: Optional[List[str]] = typer.Option(None, "--column", "-c", help="role=column, e.g. email=EmailAddr (repeatable; default: guessed)"),
                   limit: int = typer.Option(20, help="Example pairs to print"),
                   db: Optional[Path] = DbOpt):
    """Find near-duplicate records (same person captured twice): blocks on email / phone / name / birth date, scores
    pairs with exact and Jaro-Winkler comparisons."""
    from . import duplicates
    if "." not in table:
        typer.secho("Use schema.table", fg="red")
        raise typer.Exit(1)
    s_, t = table.split(".", 1)
    cols = dict(x.split("=", 1) for x in column or [] if "=" in x) or None
    con = connect_db(_db(db), read_only=True)
    res = duplicates.find(con, s_, t, cols, threshold=threshold, limit=limit)
    con.close()
    typer.echo(f"Columns: {', '.join(f'{r}={c}' for r, c in res['columns'].items())}")
    if res.get("error"):
        typer.secho(res["error"], fg="yellow")
        raise typer.Exit(1)
    typer.secho(f"{res['pairs']:,} likely duplicate pairs in {res['groups']:,} groups ({res['rows_in_groups']:,} of {res['rows']:,} rows)",
                fg="green")
    half = (len(res["example_columns"]) - 1) // 2
    for row in res["examples"]:
        typer.echo(f"  {row[0]:.3f}  " + " | ".join(str(x) for x in row[1:1 + half]) + "   ≈   " + " | ".join(str(x) for x in row[1 + half:]))


def catalog_columns(con) -> dict:
    cols: dict = {}
    for s_, t, c in con.execute("SELECT table_schema, table_name, column_name FROM information_schema.columns "
                                "WHERE table_schema <> '_meta' AND table_catalog = current_database()").fetchall():
        cols.setdefault((s_, t), []).append(c)
    return cols


def _print_structure(con, s_: str, t: str, rels: list[dict]):
    _, prof = profiler.load_profile(con, s_, t)
    st = insights.structure(insights.read(con, s_, t)["dependencies"], {c: insights._col_info(p) for c, p in prof.items()},
                            rels, s_, t)
    if not (st["entities"] or st["dirty"] or st["notes"]):
        return
    typer.secho(f"  {s_}.{t}", bold=True)
    for e in st["entities"]:
        det = ", ".join(" = ".join(d["columns"]) for d in e["determines"])
        typer.echo(f"    ▸ {e['name']:<16} {' = '.join(e['columns'])}" + (f"  →  {det}" if det else ""))
    for h in st["hierarchies"]:
        typer.echo("    ⤷ hierarchy: " + " → ".join(lv["name"] for lv in h["levels"]))
    for d in st["dirty"]:
        typer.secho(f"    ⚠ {d['sentence']}", fg="yellow")
    for n in st["notes"]:
        typer.echo(f"    ℹ {n['sentence']}")


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
    srcs = {a: s_ for a, s_ in remote_aliases(con).items() if not schema or a in schema}
    for s, t, n, at in rows:
        typer.echo(f"  {s + '.' + t:<50} {('' if n is None else f'{n:,}'):>12}  {'profiled ' + str(at)[:16] if at else 'not profiled'}"
                   + ("  (pulled from Databricks)" if s in srcs else ""))
    rel = con.execute("SELECT count(*) FROM _meta.relationships WHERE ? OR (list_contains(?, from_schema) AND list_contains(?, to_schema))",
                      [not schema, list(schema or []), list(schema or [])]).fetchone()[0]
    nremote = 0
    if srcs:
        local = {(s_, t) for s_, t, _, _ in rows}
        typer.echo("\nRemote (Databricks, metadata only – `bearings pull` copies rows):")
        for a, src in srcs.items():
            typer.echo(f"  {a}  ←  {src['connection']}:{src['catalog']}.{src['schema']}   synced {str(src['synced_at'])[:16] if src['synced_at'] else 'never'}")
            for (t, n, at, stale) in con.execute(
                    """SELECT r.table_name, coalesce(p.row_count, r.row_count), p.profiled_at, coalesce(p.stale, false)
                       FROM _meta.remote_tables r LEFT JOIN _meta.table_profile p ON p.schema_name = r.alias AND p.table_name = r.table_name
                       WHERE r.alias=? AND NOT r.dropped ORDER BY 1""", [a]).fetchall():
                if (a, t) in local:
                    continue
                nremote += 1
                st = ("profiled " + str(at)[:16] + (" (stale)" if stale else "")) if at else "not profiled"
                typer.echo(f"    {a + '.' + t:<48} {('' if n is None else f'{n:,}'):>12}  remote · {st}")
    pl = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"  # noqa: E731
    typer.echo(f"\n{pl(len(rows), 'local table')}" + (f", {pl(nremote, 'remote table')}" if srcs else "") + f", {pl(rel, 'relationship')}")


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
    schemas = {s_ for s_, _ in user_tables(con)} | set(remote_aliases(con))
    if "." in target:
        s_, t = target.split(".", 1)
        if (s_, t) not in set(user_tables(con)):
            typer.secho(f"No table {target}", fg="red"); raise typer.Exit(1)
        what = f"table {target}"
    elif target in schemas:
        s_, t = target, None
        what = f"schema {target} ({sum(1 for x, _ in user_tables(con) if x == target)} local tables)"
        if target in remote_aliases(con):
            what += " and its cached Databricks metadata (Databricks itself is not touched)"
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
    """Generate a fictional hotel dataset (PMS + CRM + a flat DWH extract) and load, profile, relate and analyse it – ready to explore."""
    from . import demo as demo_mod
    typer.echo(f"Generating demo data (scale {scale})…")
    counts = demo_mod.generate(out, scale=scale, echo=typer.echo)
    typer.echo("  " + ", ".join(f"{k} {v:,}" for k, v in counts.items()))
    if files_only:
        typer.secho(f"Done. Load it with: uv run bearings load {out}/exports/pms -s pms && uv run bearings load {out}/exports/crm -s crm"
                    f" && uv run bearings load {out}/exports/dwh -s dwh", fg="green")
        return
    dbp = Path(db).resolve()
    if dbp.exists():
        dbp.unlink()
    con = _rw(dbp)
    for src in ("pms", "crm", "dwh"):
        loader.load(con, out / "exports" / src, schema=src, echo=typer.echo)
    loader.load_comments(con, out / "comments.csv", echo=typer.echo)
    for s, t in user_tables(con):
        tp, cols = profiler.profile_table(con, s, t)
        profiler.save(con, tp, cols)
    typer.echo(f"  ✓ profiled {len(user_tables(con))} tables")
    rels = relationships.discover(con, deep=True, echo=lambda *_: None)
    relationships.save(con, rels)
    typer.echo(f"  ✓ {len(rels)} relationships found")
    done, _ = insights.run_many(con, insights.targets(con))
    typer.echo(f"  ✓ modelling insights for {len(done)} tables (grain, time coverage, dependencies)")
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


# ============================================================== remote sources (connectors: Azure Databricks, …)
remote_app = typer.Typer(no_args_is_help=True, help="Remote connection profiles (~/.bearings/connections.toml, no secrets). Built-in type: databricks.")
app.add_typer(remote_app, name="remote")


def _remote(fn, *a, **k):
    """Run a remote operation, turning RemoteError into a clean message."""
    from .remote import RemoteError
    try:
        return fn(*a, **k)
    except RemoteError as e:
        typer.secho(str(e), fg="red")
        raise typer.Exit(1)


def _print_changes(res: dict, limit: int = 40):
    ch = res["changes"]
    head = f"{res['alias']} ← {res['catalog']}.{res['schema']}: {res['tables']} table{'s' if res['tables'] != 1 else ''}"
    if res.get("first_sync"):
        typer.secho(f"  ✓ {head} (first sync)", fg="green")
        return
    if not ch:
        typer.secho(f"  ✓ {head}, no changes", fg="green")
        return
    typer.secho(f"  ✓ {head}, {len(ch)} change(s): " + ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in res["summary"].items()), fg="yellow")
    for c in ch[:limit]:
        where = c["table_name"] + (f".{c['column_name']}" if c["column_name"] else "")
        detail = ""
        if c["change"] in ("type_changed", "comment_changed", "table_comment_changed"):
            detail = f"  {c['old_value']!s:.40} → {c['new_value']!s:.40}"
        elif c["new_value"] or c["old_value"]:
            detail = f"  {c['new_value'] or c['old_value']}"
        typer.echo(f"      {c['change']:<22} {where}{detail}")
    if len(ch) > limit:
        typer.echo(f"      … {len(ch) - limit} more (see the app, or GET /api/remote/changes)")


def _settings(pairs: list[str] | None) -> dict:
    out = {}
    for p in pairs or []:
        if "=" not in p:
            typer.secho(f"--set needs key=value, got {p!r}", fg="red")
            raise typer.Exit(1)
        k, v = p.split("=", 1)
        out[k.strip()] = v.strip()
    return out


@remote_app.command("add")
def remote_add(name: str = typer.Argument(..., help="Profile name, e.g. dev"),
               type_: Optional[str] = typer.Option(None, "--type", help="Connector type (default: databricks, or the profile's current type)"),
               host: Optional[str] = typer.Option(None, "--host", help="Databricks: workspace URL, e.g. https://adb-123.12.azuredatabricks.net"),
               warehouse: Optional[str] = typer.Option(None, "--warehouse", "-w", help="Databricks: SQL warehouse id (needed for pull / remote queries)"),
               profile: Optional[str] = typer.Option(None, "--profile", help="Databricks: reuse a Databricks CLI profile from ~/.databrickscfg instead"),
               auth_type: Optional[str] = typer.Option(None, "--auth-type", help="Databricks: default external-browser (Entra ID sign-in)"),
               set_: Optional[List[str]] = typer.Option(None, "--set", help="Any connector setting as key=value (repeatable)")):
    """Add or update a connection profile."""
    from .remote import connections as cx
    fields = {"host": host, "warehouse_id": warehouse, "profile": profile, "auth_type": auth_type, **_settings(set_)}
    c = _remote(cx.upsert, name, type=type_, **fields)
    typer.secho(f"Saved '{c.name}' ({c.connector.label}) in {cx.config_path()}. Next: bearings remote login {c.name}", fg="green")


@remote_app.command("types")
def remote_types():
    """List the connector types this installation knows."""
    from .remote import connectors
    for t, cls in connectors.types().items():
        state = "installed" if cls.installed() else f"needs: uv sync --extra {cls.extra}"
        typer.echo(f"  {t:<14} {cls.label:<14} {state}")
        for f in cls.fields:
            typer.echo(f"      {f.key:<16} {f.help}")


@remote_app.command("list")
def remote_list():
    """List connection profiles."""
    from .remote import connections as cx
    conns = cx.load_all()
    if not conns:
        typer.echo("No connections yet. Add one: bearings remote add <name> --host https://adb-….azuredatabricks.net --warehouse <id>")
    for c in conns.values():
        try:
            typer.echo(f"  {c.name:<16} {c.type:<11} {c.connector.describe()}")
        except Exception as e:  # an unknown type in the file shouldn't hide the others
            typer.echo(f"  {c.name:<16} {c.type:<11} ({e})")


@remote_app.command("remove")
def remote_remove(name: str):
    """Delete a connection profile (attached schemas keep their cached metadata)."""
    from .remote import connections as cx
    typer.echo("Removed." if cx.remove(name) else f"No connection called {name}")


@remote_app.command("login")
def remote_login(name: str):
    """Sign in (Databricks: opens the browser for Entra ID the first time; the SDK caches the token)."""
    from .remote import connections as cx
    c = _remote(cx.get, name)
    typer.echo(f"Signing in to {c.connector.label} ({c.connector.describe()}) … (a browser window may open)")
    try:
        who = _remote(c.connector.whoami)
    except typer.Exit:
        raise
    except Exception as e:
        typer.secho(f"Sign-in failed: {str(e).splitlines()[0]}", fg="red")
        raise typer.Exit(1)
    typer.secho(f"Signed in as {who}", fg="green")


@remote_app.command("test")
def remote_test(name: str, catalog: Optional[str] = typer.Option(None, "--catalog", help="Also list this catalog's schemas")):
    """Check sign-in, catalog access and the SQL engine (Databricks: Unity Catalog + SQL warehouse), step by step."""
    from .remote import connections as cx
    c = _remote(cx.get, name)
    k = c.connector
    ok = True

    def step(label, fn):
        nonlocal ok
        t0 = time.time()
        try:
            res = fn()
            typer.secho(f"  ✓ {label}: {res}  ({time.time() - t0:.1f}s)", fg="green")
        except Exception as e:
            ok = False
            typer.secho(f"  ✗ {label}: {str(e).splitlines()[0] if str(e) else type(e).__name__}", fg="red")

    step("sign-in", k.whoami)
    step("catalogs", lambda: ", ".join(k.list_catalogs()[:10]) or "(no catalogs visible)")
    if catalog:
        step(f"schemas in {catalog}", lambda: ", ".join(s["schema"] for s in k.list_schemas(catalog)[:15]))
    if k.can_query():
        def q():
            con = k.sql_connect()
            try:
                cur = con.cursor()
                cur.execute("SELECT 1")
                return f"{k.compute_label} answered {cur.fetchone()[0]}"
            finally:
                con.close()
        step(k.compute_label, q)
    else:
        typer.echo(f"  – no {k.compute_label} configured (only needed for profiling, pull and live queries). "
                   f"Find one with: bearings remote warehouses {name}")
    raise typer.Exit(0 if ok else 1)


@remote_app.command("warehouses")
def remote_warehouses(name: str):
    """List the SQL warehouses (compute) you can see, with their ids (the id is what --warehouse needs)."""
    from .remote import connections as cx
    c = _remote(cx.get, name)
    whs = _remote(c.connector.list_compute)
    if not whs:
        typer.echo(f"No {c.connector.compute_label} visible to you. Ask a workspace admin for CAN USE on one (serverless starts fastest).")
        raise typer.Exit()
    typer.echo(f"  {'id':<18} {'name':<34} {'state':<9} {'type':<10} size")
    for w in whs:
        mark = "  ← current" if w["id"] == c.get("warehouse_id") else ""
        typer.echo(f"  {w['id']:<18} {w['name'][:34]:<34} {w['state']:<9} {w['kind']:<10} {w['size']}{mark}")
    typer.echo(f"\nUse one with:  bearings remote add {name} --warehouse <id>")


@remote_app.command("schemas")
def remote_schemas(name: str, catalog: str = typer.Option(..., "--catalog", "-c"), db: Optional[Path] = DbOpt):
    """List the schemas in a catalog (and which are attached)."""
    from .remote import connections as cx
    c = _remote(cx.get, name)
    rows = _remote(c.connector.list_schemas, catalog)
    dbp = _db(db)
    attached = {}
    if dbp.exists():
        con = connect(dbp, read_only=True, retries=2)
        attached = {(s_["catalog"], s_["schema"]): a for a, s_ in remote_aliases(con).items() if s_["connection"] == name}
        con.close()
    for r in rows:
        a = attached.get((catalog, r["schema"]))
        typer.echo(f"  {r['schema']:<40} {'attached as ' + a if a else ''}")


def _choose(items: list[str], label: str, multi: bool = False, default: str | None = None, notes: dict | None = None) -> list[str]:
    """Numbered picker. Accepts numbers or names; with multi=True a comma-separated list (or 'all')."""
    notes = notes or {}
    for i, it in enumerate(items, 1):
        typer.echo(f"   {i:>3}. {it}{('   ' + notes[it]) if it in notes else ''}")
    while True:
        ans = typer.prompt(f"  {label}" + (" (numbers or names, comma-separated, or 'all')" if multi else ""),
                           default=default or "", show_default=bool(default)).strip()
        if multi and ans.lower() == "all":
            return items
        picked, bad = [], []
        for tok in [t.strip() for t in ans.split(",") if t.strip()] or ([] if not default else [default]):
            if tok.isdigit() and 1 <= int(tok) <= len(items):
                picked.append(items[int(tok) - 1])
            elif tok in items:
                picked.append(tok)
            else:
                bad.append(tok)
        if picked and not bad and (multi or len(picked) == 1):
            return list(dict.fromkeys(picked))
        typer.secho(f"  Not understood: {', '.join(bad) or ans or '(empty)'}", fg="yellow")


@app.command("connect")
def connect_cmd(host: Optional[str] = typer.Option(None, "--host", help="Workspace URL, e.g. adb-123.12.azuredatabricks.net"),
            name: Optional[str] = typer.Option(None, "--name", help="Connection profile name (default: an existing one, or 'databricks')"),
            warehouse: Optional[str] = typer.Option(None, "--warehouse", "-w", help="SQL warehouse id (default: pick from a list)"),
            catalog: Optional[str] = typer.Option(None, "--catalog", "-c", help="Unity Catalog catalog"),
            schema: Optional[List[str]] = typer.Option(None, "--schema", "-s", help="Schema(s) to attach (repeatable)"),
            prefix: Optional[str] = typer.Option(None, "--prefix", help="Local alias prefix, e.g. dev_ → dev_raw_pms"),
            profile: Optional[bool] = typer.Option(None, "--profile/--no-profile", help="Profile the attached tables on the warehouse"),
            pull_max_rows: Optional[int] = typer.Option(None, "--cache-max-rows", "--pull-max-rows",
                                                        help="Local cache: tables up to N rows whole, an N-row sample of bigger ones (0 = no cache; default 300,000)"),
            mask_pii: Optional[bool] = typer.Option(None, "--mask-pii/--no-mask-pii", help="Hash personal data in the local cache and profile (default: on)"),
            yes: bool = typer.Option(False, "--yes", "-y", help="Don't ask; use the options and defaults"),
            db: Optional[Path] = DbOpt):
    """Guided setup: sign in, pick a warehouse, catalog and schemas, attach, profile and relate – in one go.

    Run it with no options and answer the questions, or script it:
      bearings connect --host adb-….azuredatabricks.net -c dev_catalog -s raw_pms -s gold_pms --prefix dev_ --profile -y"""
    from .remote import connections as cx
    from .remote import profile as rprofile
    from .remote import pull as rpull
    from .remote import sync as rsync
    from .db import safe_name
    dbp = _db(db)
    conns = cx.load_all()

    # 1. connection profile
    typer.secho("1/5  Workspace", bold=True)
    if not host and not name and len(conns) == 1 and (yes or typer.confirm(f"  Use connection '{next(iter(conns))}' ({next(iter(conns.values())).host})?", default=True)):
        name = next(iter(conns))
    if name and name in conns and not host:
        c = conns[name]
    else:
        host = host or typer.prompt("  Workspace URL (e.g. adb-1234567890.12.azuredatabricks.net)")
        host = host.strip().rstrip("/")
        host = host if host.startswith("http") else "https://" + host
        name = name or next((n for n, x in conns.items() if x.host.rstrip("/") == host), None) or \
            (typer.prompt("  Name for this connection", default="databricks") if not yes else "databricks")
        c = _remote(cx.upsert, name, host=host)
    typer.echo(f"  Signing in to {c.host} … (a browser window may open)")
    k = c.connector
    try:
        typer.secho(f"  ✓ signed in as {_remote(k.whoami)}", fg="green")
    except typer.Exit:
        raise
    except Exception as e:
        typer.secho(f"  Sign-in failed: {str(e).splitlines()[0]}", fg="red")
        raise typer.Exit(1)

    # 2. warehouse
    typer.secho("2/5  SQL warehouse (for profiling and live queries)", bold=True)
    if warehouse:
        c = _remote(cx.upsert, name, warehouse_id=warehouse)
    elif not c.warehouse_id:
        whs = _remote(k.list_compute)
        if not whs:
            typer.secho("  No SQL warehouse visible to you – attach still works; ask an admin for CAN USE on one for live queries.", fg="yellow")
        else:
            label = {f"{w['name']} ({w['id']})": w for w in whs}
            notes = {n: ("serverless" if w.get("serverless") else "classic") + f", {w['state']}" for n, w in label.items()}
            default = next((n for n, w in label.items() if w.get("serverless")), next(iter(label)))
            pick = default if (yes or len(whs) == 1) else _choose(list(label), "Warehouse", default=default, notes=notes)[0]
            c = _remote(cx.upsert, name, warehouse_id=label[pick]["id"])
            typer.echo(f"  using {pick}")
    else:
        typer.echo(f"  using warehouse {c.warehouse_id}")

    # 3. catalog + schemas
    typer.secho("3/5  What to attach", bold=True)
    if not catalog:
        cats = _remote(rsync.list_catalogs, k)
        if yes:
            typer.secho("  --catalog is required with --yes", fg="red")
            raise typer.Exit(1)
        catalog = _choose(cats, "Catalog")[0]
    if not schema:
        avail = [x["schema"] for x in _remote(rsync.list_schemas, k, catalog)]
        if yes:
            typer.secho("  --schema is required with --yes", fg="red")
            raise typer.Exit(1)
        schema = _choose(avail, f"Schemas in {catalog}", multi=True)
    if prefix is None:
        prefix = "" if yes else typer.prompt("  Local name prefix (e.g. dev_, blank for none)", default="", show_default=False)
    attached = {}
    if dbp.exists():
        con = connect_db(dbp)
        attached = {(v["connection"], v["catalog"], v["schema"]): a for a, v in remote_aliases(con).items()}
        con.close()
    aliases = []
    for sch in schema:
        if (name, catalog, sch) in attached:
            a = attached[(name, catalog, sch)]
            typer.echo(f"  {catalog}.{sch} is already attached as {a} – re-syncing")
            _print_changes(_remote(rsync.sync, dbp, a, echo=lambda *_: None))
        else:
            a = safe_name(f"{prefix}{sch}")
            _print_changes(_remote(rsync.attach, dbp, name, catalog, sch, a, echo=lambda *_: None))
        aliases.append(a)

    if mask_pii is None:
        mask_pii = True if yes else typer.confirm("  Mask personal data (e-mail, phone, names…) in what's stored on this laptop?", default=True)
    if mask_pii:
        from .remote import pii
        con = _rw(dbp)
        for a in aliases:
            pii.set_enabled(con, a, True)
        con.close()

    # 4. profile + relationships
    typer.secho("4/5  Profile (on the warehouse: stats, keys, relationships)", bold=True)
    do_profile = profile if profile is not None else (True if yes else typer.confirm("  Profile the new tables now? (a few minutes for ~100 tables)", default=True))
    if do_profile and c.warehouse_id:
        targets = rprofile.targets(dbp, aliases=aliases, only_new=True)
        typer.echo(f"  profiling {len(targets)} table(s), 3 at a time…")
        _, fails = rprofile.profile_many(dbp, targets, echo=typer.echo)
        con = _rw(dbp)
        rels = relationships.discover(con, deep=True, echo=lambda *_: None, schemas=set(aliases))
        relationships.save(con, rels, schemas=set(aliases))
        con.close()
        typer.secho(f"  ✓ {len(targets) - fails} profiled, {len(rels)} relationships found", fg="green")
    elif do_profile:
        typer.secho("  skipped: no SQL warehouse configured", fg="yellow")

    # 5. local cache: everything runs locally by default, Remote on demand
    typer.secho("5/5  Local cache (queries run locally; tick Remote in the app to run on Databricks)", bold=True)
    if pull_max_rows is None:
        if yes:
            pull_max_rows = rpull.DEFAULT_CACHE_ROWS
        elif typer.confirm(f"  Cache the tables on this laptop (whole up to N rows, an N-row sample of bigger ones)?", default=True):
            pull_max_rows = typer.prompt("  N", default=rpull.DEFAULT_CACHE_ROWS, type=int)
        else:
            pull_max_rows = 0
    if pull_max_rows and c.warehouse_id:
        for a in aliases:
            rpull.set_cache_limit(dbp, a, pull_max_rows)
        res = rpull.cache(dbp, aliases=aliases, max_rows=pull_max_rows, echo=typer.echo)
        ok = [r for r in res if "error" not in r]
        typer.echo(f"  {sum(1 for r in ok if r.get('complete'))} cached whole, {sum(1 for r in ok if not r.get('complete'))} as a sample")
        con = _rw(dbp)
        relationships.refresh_cardinality(con, set(aliases))
        done, _ = insights.run_many(con, insights.targets(con, set(aliases)))
        con.close()
        typer.echo(f"  ✓ modelling insights for {len(done)} cached table(s): bearings insights -s {aliases[0]} --show")
    else:
        typer.echo("  skipped – cache later with: bearings cache -s " + " -s ".join(aliases) + " --max-rows 300000")
    typer.secho(f"\nReady. Start the app with:  uv run bearings serve\nKeep it current later with:  uv run bearings refresh", fg="green")


@app.command()
def refresh(schema: Optional[List[str]] = typer.Option(None, "--schema", "-s", help="Remote alias(es) (default: all attached)"),
            recache_all: bool = typer.Option(False, "--recache", help="Re-cache every table (default: only cached tables whose source changed)"),
            db: Optional[Path] = DbOpt):
    """Bring remote schemas up to date in one step: re-sync metadata, re-profile what changed, re-find relationships."""
    from .remote import profile as rprofile
    from .remote import pull as rpull
    from .remote import sync as rsync
    dbp = _db(db)
    aliases = _remote(rsync.aliases_for, dbp, schema)
    if not aliases:
        typer.echo("No attached remote schemas. Start with: bearings connect")
        raise typer.Exit()
    typer.secho("Sync", bold=True)
    changed = []
    for a in aliases:
        r = _remote(rsync.sync, dbp, a)
        _print_changes(r)
        changed += [(a, t) for t in {c["table_name"] for c in r["changes"]}]
    _print_orphans(dbp, set(aliases))
    typer.secho("Data changes (Delta versions of cached tables)", bold=True)
    moved = rpull.check_freshness(dbp, aliases, echo=typer.echo)
    if not moved:
        typer.echo("  no data changes since caching")
    con = connect_db(dbp, read_only=True)
    cached = {(s_, t) for s_, t in user_tables(con) if s_ in aliases}
    stale_cached = [f"{s_}.{t}" for s_, t in con.execute(
        "SELECT schema_name, table_name FROM _meta.table_profile WHERE coalesce(stale, false)").fetchall() if (s_, t) in cached]
    con.close()
    typer.secho("Profile what changed (on the warehouse)", bold=True)
    targets = rprofile.targets(dbp, aliases=aliases, only_stale=True)
    rprofile.profile_many(dbp, targets, echo=typer.echo)
    if not targets:
        typer.echo("  nothing to re-profile")
    if stale_cached or recache_all:
        typer.secho("Re-cache", bold=True)
        rpull.cache(dbp, aliases=aliases, tables=None if recache_all else stale_cached, refresh=True, echo=typer.echo)
    typer.secho("Relationships", bold=True)
    con = _rw(dbp)
    rels = relationships.discover(con, deep=True, echo=lambda *_: None, schemas=set(aliases))
    relationships.save(con, rels, schemas=set(aliases))
    typer.secho("Modelling insights (cached tables)", bold=True)
    insights.run_many(con, insights.targets(con, set(aliases)))
    con.close()
    typer.secho(f"Done: {len(changed)} schema change(s), {len(moved)} table(s) with new data, {len(targets)} re-profiled, "
                f"{len(stale_cached)} re-cached, {len(rels)} relationships.", fg="green")


@app.command()
def attach(connection: str = typer.Argument(..., help="Connection profile name"),
           target: str = typer.Argument(..., help="catalog.schema in Unity Catalog"),
           alias: Optional[str] = typer.Option(None, "--as", help="Local schema name (default <schema>_dbx)"),
           db: Optional[Path] = DbOpt):
    """Attach a Databricks schema: sync its tables, columns and comments (metadata only)."""
    from .remote import sync as rsync
    if target.count(".") != 1:
        typer.secho("Use catalog.schema, e.g. lakehouse.bronze_opera", fg="red")
        raise typer.Exit(1)
    cat_, sch = target.split(".")
    res = _remote(rsync.attach, _db(db), connection, cat_, sch, alias, echo=typer.echo)
    _print_changes(res)
    typer.secho(f"Attached as '{res['alias']}'. Search it in the app now; copy rows with: bearings pull {res['alias']}.<table> --rows 100000", fg="green")


@app.command()
def sync(schema: Optional[List[str]] = typer.Option(None, "--schema", "-s", help="Attached alias(es) to sync (default: all)"),
         catalog: Optional[str] = typer.Option(None, "--catalog", help="Only aliases from this Unity Catalog catalog"),
         connection: Optional[str] = typer.Option(None, "--connection", help="Only aliases on this connection"),
         dry_run: bool = typer.Option(False, "--dry-run", help="Show what changed without storing it"),
         db: Optional[Path] = DbOpt):
    """Re-sync remote metadata and show what changed (added/dropped tables and columns, type and comment changes)."""
    from .remote import sync as rsync
    dbp = _db(db)
    aliases = _remote(rsync.aliases_for, dbp, schema, catalog, connection)
    if not aliases:
        typer.echo("No attached remote schemas. Attach one: bearings attach <connection> <catalog>.<schema>")
        raise typer.Exit()
    for a in aliases:
        _print_changes(_remote(rsync.sync, dbp, a, dry_run=dry_run, echo=typer.echo))
    if dry_run:
        typer.echo("(dry run – nothing stored)")
    else:
        _print_orphans(dbp, set(aliases))


def _print_orphans(dbp: Path, schemas: set[str] | None = None) -> int:
    from . import catalog as catalog_mod
    from . import orphans
    con = connect(dbp, read_only=True, retries=2)
    try:
        found = orphans.find(catalog_mod.build(con, dbp), catalog_mod.annotations(dbp), set(remote_aliases(con)), schemas)
    finally:
        con.close()
    if found:
        typer.secho(f"\n  {len(found)} annotation(s) now point at something that no longer exists (kept, not deleted):", fg="yellow")
        for o in found[:30]:
            sug = ", ".join(f"{x['column']} ({x['score']:.0f})" for x in o["suggestions"])
            typer.echo(f"      {o['schema']}.{o['table']}{'.' + o['column'] if o['column'] else ''}  – {o['reason']}" + (f"; maybe {sug}" if sug else ""))
        typer.echo("    Move one with: bearings remap <schema>.<table>.<old_column> <new_column>")
    return len(found)


@app.command()
def orphans(schema: Optional[List[str]] = SchemaOpt, db: Optional[Path] = DbOpt):
    """List annotations whose column (or remote table) no longer exists, with remap suggestions."""
    if not _print_orphans(_db(db), set(schema) if schema else None):
        typer.secho("No orphaned annotations.", fg="green")


@app.command()
def remap(ref: str = typer.Argument(..., help="schema.table.old_column"),
          new_column: str = typer.Argument(..., help="Column (or table.column) to move the annotation to"),
          db: Optional[Path] = DbOpt):
    """Move an annotation (tags, CDM mapping, notes) to another column, e.g. after a rename."""
    from . import orphans as orphans_mod
    parts = ref.split(".")
    if len(parts) != 3:
        typer.secho("Use schema.table.old_column", fg="red")
        raise typer.Exit(1)
    nt, nc = new_column.split(".", 1) if "." in new_column else (None, new_column)
    try:
        r = orphans_mod.remap(_db(db), parts[0], parts[1], parts[2], nc, nt)
    except (KeyError, ValueError) as e:
        typer.secho(str(e).strip("'\""), fg="red")
        raise typer.Exit(1)
    typer.secho(f"Moved {r['schema']}.{r['from']} → {r['schema']}.{r['to']}", fg="green")


@app.command()
def pull(ref: Optional[str] = typer.Argument(None, help="<alias>.<table> of an attached remote schema (or use -s for many)"),
         rows: Optional[int] = typer.Option(None, "--rows", "-n", help="Random sample of about N rows (TABLESAMPLE). Default: the whole table"),
         where: Optional[str] = typer.Option(None, "--where", help="Filter pushed down to Databricks, e.g. \"arrival_date >= '2026-01-01'\""),
         first: bool = typer.Option(False, "--first", help="With --rows: take the first N rows instead of a random sample"),
         target: Optional[str] = typer.Option(None, "--as", help="Local schema (or schema.table) for the copy. Default: same as the remote alias"),
         schema: Optional[List[str]] = typer.Option(None, "--schema", "-s", help="Pull the tables of these remote schemas"),
         max_rows: Optional[int] = typer.Option(None, "--max-rows", help="With -s: copy tables up to N rows whole; bigger ones stay remote"),
         sample_rows: Optional[int] = typer.Option(None, "--sample-rows", help="With -s --max-rows: copy a random N-row sample of the bigger tables instead"),
         refresh: bool = typer.Option(False, "--refresh", help="With -s: re-pull tables that were already copied"),
         no_profile: bool = typer.Option(False, "--no-profile", help="Don't profile the local copy right away"),
         db: Optional[Path] = DbOpt):
    """Copy remote tables (or samples) into DuckDB, so everything on them runs at local speed.

    One table:  bearings pull dev_raw_pms.reservation --rows 500000
    Many:       bearings pull -s dev_raw_pms --max-rows 300000   (small tables whole, big ones stay live)"""
    from .remote import pull as rpull
    dbp = _db(db)
    if schema and not ref:
        typer.echo(f"Pulling tables of {', '.join(schema)}" + (f" up to {max_rows:,} rows" if max_rows else "") + "…")
        res = _remote(rpull.pull_many, dbp, aliases=list(schema), max_rows=max_rows, sample_rows=sample_rows, refresh=refresh,
                      echo=typer.echo)
        ok = [r for r in res if "error" not in r]
        typer.secho(f"Done: {len(ok)} table(s) copied, {len(res) - len(ok)} failed. They now run at local speed; "
                    f"the rest stay live on Databricks.", fg="green")
        return
    if not ref:
        typer.secho("Give <alias>.<table>, or -s <alias> [--max-rows N] for many tables", fg="red")
        raise typer.Exit(1)
    ts, tt = (target.split(".", 1) if target and "." in target else (target, None))
    if rows is None and not where:
        typer.secho("No --rows or --where: pulling the whole table. Big tables are better sampled (--rows 1000000).", fg="yellow")
    res = _remote(rpull.pull, dbp, ref, rows=rows, where=where, target_schema=ts, target_table=tt, first=first,
                  profile=not no_profile, echo=typer.echo)
    typer.secho(f"Pulled {res['rows']:,} rows × {res['columns']} columns into {res['schema']}.{res['table']} in {res['seconds']}s"
                + ("" if no_profile else " (profiled)") + ".", fg="green")


@app.command()
def cache(schema: Optional[List[str]] = typer.Option(None, "--schema", "-s", help="Remote alias(es) (default: all attached)"),
          table: Optional[List[str]] = typer.Option(None, "--table", "-t", help="Only these alias.table (repeatable)"),
          max_rows: Optional[int] = typer.Option(None, "--max-rows", help="Cache tables up to N rows whole and an N-row sample of bigger ones; "
                                                                        "remembered for the schema (default 300,000)"),
          refresh: bool = typer.Option(False, "--refresh", help="Re-cache tables that are already cached"),
          changed: bool = typer.Option(False, "--changed", help="Re-cache only tables whose source changed since (after a sync)"),
          drop: bool = typer.Option(False, "--drop", help="Remove the local cache instead (tables go back to live on Databricks)"),
          mask_pii: Optional[bool] = typer.Option(None, "--mask-pii/--no-mask-pii",
                                                  help="Hash personal data (e-mail, phone, names…) in the cache and stored profile; remembered per schema"),
          db: Optional[Path] = DbOpt):
    """Keep a local copy of remote tables so queries run at local speed (Remote on demand in the app).

    Tables up to N rows are copied whole ("cached"); bigger ones as a random N-row sample ("cached sample"),
    while their profile stays the exact whole-table one from Databricks."""
    from .remote import pull as rpull
    from .remote import sync as rsync
    dbp = _db(db)
    aliases = _remote(rsync.aliases_for, dbp, schema)
    if not aliases:
        typer.echo("No attached remote schemas. Start with: bearings connect")
        raise typer.Exit()
    if drop:
        con = _rw(dbp)
        n = 0
        for s_, t in user_tables(con):
            if s_ in aliases and (not table or f"{s_}.{t}" in table):
                drop_table(con, s_, t)
                n += 1
        con.execute("CHECKPOINT")
        con.close()
        typer.secho(f"Removed {n} cached table(s); they run live on Databricks again. `bearings compact` shrinks the file.", fg="green")
        return
    if mask_pii is not None:
        from .remote import pii
        for a in aliases:
            if mask_pii:
                done = pii.apply_schema(dbp, a)
                typer.secho(f"  {a}: PII masking on – {sum(len(v) for v in done.values())} column(s) in {len(done)} table(s) masked "
                            f"in the cache and stored profile", fg="green")
            else:
                con = _rw(dbp)
                pii.set_enabled(con, a, False)
                con.close()
                typer.secho(f"  {a}: PII masking off – re-cache (--refresh) and re-profile to bring real values back", fg="yellow")
        if not (max_rows or refresh or changed or table):
            return
    if max_rows:
        for a in aliases:
            rpull.set_cache_limit(dbp, a, max_rows)
    if changed:
        typer.echo("Checking Delta versions of cached tables…")
        rpull.check_freshness(dbp, aliases, echo=typer.echo)
    res = _remote(rpull.cache, dbp, aliases=aliases, tables=list(table or []) or None, max_rows=max_rows, refresh=refresh,
                  only_changed=changed, echo=typer.echo)
    ok = [r for r in res if "error" not in r]
    whole = sum(1 for r in ok if r.get("complete"))
    typer.secho(f"Done: {whole} cached whole, {len(ok) - whole} cached as a sample, {len(res) - len(ok)} failed. "
                f"Queries now run locally; tick Remote in the app to run one on Databricks.", fg="green")


@app.command()
def pii(schema: Optional[List[str]] = typer.Option(None, "--schema", "-s", help="Remote alias(es) (default: all attached)"),
        keep: Optional[List[str]] = typer.Option(None, "--keep", help="alias.table.column to keep readable (tags it no-pii)"),
        mask: Optional[List[str]] = typer.Option(None, "--mask", help="alias.table.column to always mask (tags it pii)"),
        db: Optional[Path] = DbOpt):
    """Show which columns are masked in the local cache, and why. --keep / --mask adjust it (as annotation tags);
    re-cache afterwards (bearings cache -s <alias> --refresh) to apply."""
    import datetime as _dt

    from .db import ann_connect
    from .remote import pii as pii_mod
    from .remote import sync as rsync
    dbp = _db(db)
    for ref, tag in [(r, "no-pii") for r in (keep or [])] + [(r, "pii") for r in (mask or [])]:
        parts = ref.split(".")
        if len(parts) != 3:
            typer.secho(f"Use alias.table.column: {ref}", fg="red")
            raise typer.Exit(1)
        c = ann_connect(dbp)
        row = c.execute("SELECT tags FROM annotations WHERE schema_name=? AND table_name=? AND column_name=?", parts).fetchone()
        tags = [t.strip() for t in ((row[0] if row else "") or "").split(",") if t.strip() and t.strip().lower() not in ("pii", "no-pii")]
        tags.append(tag)
        c.execute("""INSERT INTO annotations (schema_name, table_name, column_name, tags, updated_at) VALUES (?,?,?,?,?)
                     ON CONFLICT(schema_name, table_name, column_name) DO UPDATE SET tags=excluded.tags, updated_at=excluded.updated_at""",
                  (*parts, ", ".join(tags), _dt.datetime.now().isoformat(timespec="seconds")))
        c.commit()
        c.close()
        typer.echo(f"  tagged {ref} {tag}")
    aliases = _remote(rsync.aliases_for, dbp, schema)
    con = connect_db(dbp, read_only=True)
    try:
        total = 0
        for a in aliases:
            on = pii_mod.enabled(con, a)
            typer.secho(f"{a}: masking {'ON' if on else 'off (bearings cache -s ' + a + ' --mask-pii)'}", bold=True)
            cached = {t: json.loads(m) if m else [] for t, m in con.execute(
                "SELECT table_name, masked_columns FROM _meta.remote_cache WHERE alias=?", [a]).fetchall()}
            biz = [t for (t,) in con.execute("SELECT table_name FROM _meta.remote_tables WHERE alias=? AND NOT dropped ORDER BY 1",
                                             [a]).fetchall() if pii_mod.BUSINESS_TABLE.search(t)]
            if biz:
                typer.echo(f"  (business tables, not masked: {', '.join(biz)} – bearings pii --mask <alias.table.column> to mask a column anyway)")
            for (t,) in con.execute("SELECT table_name FROM _meta.remote_tables WHERE alias=? AND NOT dropped ORDER BY 1", [a]).fetchall():
                cols = [r[0] for r in con.execute("SELECT column_name FROM _meta.remote_columns WHERE alias=? AND table_name=? ORDER BY ordinal",
                                                  [a, t]).fetchall()]
                plan = pii_mod.pii_columns(con, dbp, a, t, cols, explain=True)
                now_masked = set(cached.get(t) or [])
                if not plan and not now_masked:
                    continue
                typer.echo(f"  {t}")
                for c_, why in plan.items():
                    total += 1
                    typer.echo(f"      {c_:<36} {why}" + ("" if c_ in now_masked or t not in cached else "   (re-cache to apply)"))
                for c_ in sorted(now_masked - set(plan)):
                    typer.secho(f"      {c_:<36} masked in the cache, no longer matches – re-cache to restore", fg="yellow")
        typer.echo(f"\n{total} column(s) to mask. Keep one readable: bearings pii --keep <alias.table.column>; "
                   f"apply changes: bearings cache -s <alias> --refresh")
    finally:
        con.close()


@app.command()
def detach(alias: str = typer.Argument(..., help="Attached remote schema alias"),
           annotations: bool = typer.Option(False, "--annotations", help="Also delete its annotations"),
           yes: bool = typer.Option(False, "--yes", "-y"),
           db: Optional[Path] = DbOpt):
    """Forget an attached remote schema: its cached metadata and any pulled copies. Databricks is not touched."""
    dbp = _db(db)
    con = _rw(dbp)
    if alias not in remote_aliases(con):
        typer.secho(f"'{alias}' is not attached. Attached: {', '.join(remote_aliases(con)) or 'none'}", fg="red")
        raise typer.Exit(1)
    if not yes and not typer.confirm(f"Detach {alias}{' and delete its annotations' if annotations else ' (annotations kept)'}?"):
        raise typer.Exit()
    n = drop_schema(con, alias)
    con.execute("CHECKPOINT")
    con.close()
    k = delete_annotations(dbp, alias) if annotations else 0
    typer.secho(f"Detached {alias}" + (f" and dropped {n} pulled table(s)" if n else "") +
                (f", {k} annotations deleted" if annotations else " (annotations kept – attach it again to see them)"), fg="green")


if __name__ == "__main__":
    app()
