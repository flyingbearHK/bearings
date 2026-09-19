"""Annotations whose column (or remote table) no longer exists – e.g. after a remote re-sync renamed a column.

Annotations are manual work, so they're never deleted automatically: they're listed with remap suggestions.
Annotations on *local* tables you dropped are not orphans (reloading the same table brings them back).
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from rapidfuzz import fuzz

from .catalog import norm
from .db import ann_connect


def _has_content(a: dict) -> bool:
    return any((a.get(k) or "").strip() for k in ("tags", "cdm_entity", "cdm_attribute", "notes"))


def _suggest(col: str, candidates: list[str], n: int = 3) -> list[dict]:
    scored = [{"column": c, "score": round(max(fuzz.ratio(norm(col), norm(c)), fuzz.partial_ratio(norm(col), norm(c)) - 5), 1)}
              for c in candidates]
    return [s for s in sorted(scored, key=lambda s: -s["score"]) if s["score"] >= 60][:n]


def find(cat: dict, ann: dict, remote_aliases: set[str], schemas: set[str] | None = None) -> list[dict]:
    known_cols: dict[tuple[str, str], set[str]] = {k: {c["column"] for c in tb["columns"]} for k, tb in cat["tables"].items()}
    annotated = {(s, t, c) for (s, t, c) in ann}
    out = []
    for (s, t, c), a in sorted(ann.items()):
        if schemas and s not in schemas:
            continue
        if not _has_content(a):
            continue
        cols = known_cols.get((s, t))
        if cols is None:
            if s in remote_aliases:
                out.append({"schema": s, "table": t, "column": c, "reason": "table no longer in the remote schema",
                            "annotation": a, "suggestions": []})
            continue
        if c and c not in cols:
            free = [x for x in cols if (s, t, x) not in annotated]
            out.append({"schema": s, "table": t, "column": c, "reason": "column no longer exists",
                        "annotation": a, "suggestions": _suggest(c, free)})
    return out


def remap(db_path: Path, schema: str, table: str, column: str, new_column: str, new_table: str | None = None) -> dict:
    """Move one annotation to another column (and optionally table). Refuses to overwrite an existing annotation."""
    new_table = new_table or table
    c = ann_connect(db_path)
    try:
        row = c.execute("SELECT * FROM annotations WHERE schema_name=? AND table_name=? AND column_name=?", (schema, table, column)).fetchone()
        if not row:
            raise KeyError(f"No annotation on {schema}.{table}.{column}")
        if c.execute("SELECT 1 FROM annotations WHERE schema_name=? AND table_name=? AND column_name=?", (schema, new_table, new_column)).fetchone():
            raise ValueError(f"{schema}.{new_table}.{new_column} already has an annotation – edit that one instead")
        c.execute("UPDATE annotations SET table_name=?, column_name=?, updated_at=? WHERE schema_name=? AND table_name=? AND column_name=?",
                  (new_table, new_column, dt.datetime.now().isoformat(timespec="seconds"), schema, table, column))
        c.commit()
        return {"schema": schema, "from": f"{table}.{column}", "to": f"{new_table}.{new_column}"}
    finally:
        c.close()
