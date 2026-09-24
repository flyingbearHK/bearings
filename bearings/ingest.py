"""Load → describe → profile → relate in one step (the web app's "Add data", and reusable from scripts).

Each step opens its own short DuckDB write connection, so the app stays usable between tables.
"""
from __future__ import annotations

import csv
import os
import re
import time
from pathlib import Path
from typing import Callable

from . import insights, loader, profiler, relationships
from .db import connect, safe_name
from .loaders import LoadOptions, readers

UPLOAD_ID = re.compile(r"^[A-Za-z0-9_-]{6,64}$")


def uploads_root(db_path: Path) -> Path:
    return Path(db_path).resolve().parent / "uploads"


def upload_dir(db_path: Path, batch: str) -> Path:
    if not UPLOAD_ID.match(batch or ""):
        raise ValueError("Bad upload id")
    return uploads_root(db_path) / batch


def safe_relpath(name: str) -> Path:
    """A browser-supplied file name (possibly `folder/part-0.parquet` from a dropped folder) → a safe relative path."""
    parts = [re.sub(r"[^\w.\- ()\[\]@+=,]", "_", p).strip() for p in re.split(r"[\\/]+", name or "")]
    parts = [p for p in parts if p and p not in (".", "..")]
    if not parts:
        raise ValueError("Empty file name")
    return Path(*parts)


def is_comments_csv(p: Path) -> bool:
    """A CSV of table/column descriptions (table_name, column_name, comment) rather than data."""
    if not p.is_file() or not p.name.lower().endswith((".csv", ".tsv")):
        return False
    try:
        with open(p, newline="", encoding="utf-8-sig") as f:
            head = next(csv.reader(f, delimiter="\t" if p.name.lower().endswith(".tsv") else ","), [])
    except (OSError, UnicodeDecodeError, csv.Error):
        return False
    cols = {h.strip().lower() for h in head}
    return {"table_name", "comment"} <= cols and len(cols) <= 6


def suggest_schema(path: Path, is_upload: bool = False) -> str:
    """A folder's name is usually the source system (exports/opera → opera). Loose dropped files: main."""
    path = Path(path)
    if is_upload and UPLOAD_ID.match(path.name):
        return "main"
    return safe_name(path.name) if path.is_dir() else "main"


def preview(path: Path, opts: LoadOptions | None = None, is_upload: bool = False) -> dict:
    """What `load` would create from `path`, plus description files found next to the data."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Not found: {path}")
    msgs: list[str] = []
    items = loader.discover(path, opts or LoadOptions(), echo=msgs.append)
    comments = [str(p) for p in ([path] if path.is_file() else sorted(path.rglob("*.csv")) + sorted(path.rglob("*.tsv")))
                if is_comments_csv(p)][:20]
    out = []
    for it in items:
        if len(it.paths) == 1 and str(it.paths[0]) in comments:
            continue
        size = sum(p.stat().st_size for p in it.paths if p.exists())
        out.append({"table": it.table, "format": it.format, "source": it.source, "label": it.label,
                    "files": len(it.paths), "bytes": size, "sheet": it.options.get("sheet")})
    return {"path": str(path), "is_dir": path.is_dir(), "suggested_schema": suggest_schema(path, is_upload), "items": out,
            "comments": comments, "messages": [m.strip() for m in msgs]}


def listdir(path: str | None) -> dict:
    """Folders and loadable files in a folder – for the app's folder picker."""
    p = Path(os.path.expanduser(path or "~")).resolve()
    if p.is_file():
        p = p.parent
    if not p.is_dir():
        raise FileNotFoundError(f"Not a folder: {p}")
    dirs, files = [], []
    try:
        entries = sorted(p.iterdir(), key=lambda x: x.name.lower())
    except PermissionError as e:
        raise PermissionError(f"No access to {p}") from e
    for e in entries:
        if e.name.startswith((".", "~$")):
            continue
        try:
            if e.is_dir():
                dirs.append(e.name)
            elif e.is_file():
                r = next((r for r in readers() if r.matches(e)), None)
                if r:
                    files.append({"name": e.name, "bytes": e.stat().st_size, "format": r.name})
        except OSError:
            continue
    return {"path": str(p), "parent": str(p.parent) if p.parent != p else None, "dirs": dirs, "files": files}


def run(db_path: Path, path: Path, schema: str, opts: LoadOptions | None = None, mode: str = "replace",
        tables: list[str] | None = None, comments: list[str] | None = None, profile: bool = True, relate: bool = True,
        analyse: bool = True, progress: Callable[[dict], None] = lambda _: None) -> dict:
    """Load the tables at `path` into `schema` (only `tables` when given), import description files, profile what
    was loaded, look for relationships touching the schema and compute modelling insights (grain, time coverage,
    dependencies). `progress` gets {phase, current, done, total}."""
    opts = opts or LoadOptions()
    t0 = time.time()
    schema = safe_name(schema) if schema and schema != "main" else "main"
    items = loader.discover(path, opts)
    comment_files = {str(c) for c in comments or []}
    items = [it for it in items if not (len(it.paths) == 1 and str(it.paths[0]) in comment_files)]
    if tables is not None:
        want = set(tables)
        items = [it for it in items if it.table in want]
    total = len(items)
    loaded, errors = [], []
    for i, it in enumerate(items):
        progress({"phase": "load", "current": f"{schema}.{it.table}", "done": i, "total": total})
        con = connect(db_path, read_only=False, retries=10)
        try:
            res = loader.load(con, path, schema=schema, mode=mode, items=[it], echo=lambda *_: None, **_load_kw(opts))
        finally:
            con.close()
        for r in res:
            (errors if "error" in r else loaded).append(r)
    n_comments = 0
    for c in sorted(comment_files):
        progress({"phase": "comments", "current": Path(c).name, "done": len(items), "total": total})
        con = connect(db_path, read_only=False, retries=10)
        try:
            n_comments += loader.load_comments(con, Path(c), echo=lambda *_: None)
        except Exception as e:
            errors.append({"table": Path(c).name, "error": str(e).splitlines()[0]})
        finally:
            con.close()
    profiled = []
    if profile:
        for i, r in enumerate(loaded):
            progress({"phase": "profile", "current": f"{r['schema']}.{r['table']}", "done": i, "total": len(loaded)})
            con = connect(db_path, read_only=False, retries=10)
            try:
                tp, cols = profiler.profile_table(con, r["schema"], r["table"])
                profiler.save(con, tp, cols)
                r["candidate_keys"] = tp["candidate_keys"]
                r["flagged"] = sum(1 for c in cols if c["flags"])
                profiled.append(r["table"])
            except Exception as e:
                errors.append({"table": r["table"], "error": f"profile: {str(e).splitlines()[0]}"})
            finally:
                con.close()
    rels = []
    if relate and profiled:
        progress({"phase": "relate", "current": schema, "done": 0, "total": 1})
        con = connect(db_path, read_only=False, retries=10)
        try:
            rels = relationships.discover(con, deep=True, echo=lambda *_: None, touching={schema})
            relationships.save(con, rels, touching={schema})
        except Exception as e:
            errors.append({"table": schema, "error": f"relationships: {str(e).splitlines()[0]}"})
        finally:
            con.close()
    analysed = 0
    if analyse and profiled:
        for i, t in enumerate(profiled):
            progress({"phase": "insights", "current": f"{schema}.{t}", "done": i, "total": len(profiled)})
            con = connect(db_path, read_only=False, retries=10)
            try:
                insights.run(con, schema, t)
                analysed += 1
            except Exception as e:
                errors.append({"table": t, "error": f"insights: {str(e).splitlines()[0]}"})
            finally:
                con.close()
    progress({"phase": "done", "current": None, "done": total, "total": total})
    return {"schema": schema, "loaded": loaded, "errors": errors, "comments": n_comments, "profiled": len(profiled),
            "relationships": len(rels), "analysed": analysed, "seconds": round(time.time() - t0, 1)}


def _load_kw(opts: LoadOptions) -> dict:
    return {"all_varchar": opts.all_varchar, "delim": opts.delim, "sheets": opts.sheets, "header_row": opts.header_row}
