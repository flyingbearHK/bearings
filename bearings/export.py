"""Exports: Excel mapping workbook, JSON catalog, Markdown per table."""
from __future__ import annotations

import io
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .db import META
from .profiler import load_profile


def catalog_rows(con, cat: dict) -> tuple[list[dict], list[dict]]:
    tables, cols = [], []
    for tb in cat["tables"].values():
        ta = tb.get("annotation") or {}
        tables.append({"schema": tb["schema"], "table": tb["table"], "row_count": tb["row_count"],
                       "column_count": len(tb["columns"]), "candidate_keys": ", ".join(tb["candidate_keys"] or []),
                       "comment": tb.get("comment") or "", "tags": ta.get("tags", ""), "cdm_entity": ta.get("cdm_entity", ""),
                       "notes": ta.get("notes", ""), "source": tb.get("source") or "", "profiled_at": tb.get("profiled_at") or ""})
        _, prof = load_profile(con, tb["schema"], tb["table"])
        for c in tb["columns"]:
            p = prof.get(c["column"], {})
            a = c.get("annotation") or {}
            cols.append({
                "schema": tb["schema"], "table": tb["table"], "column": c["column"], "ordinal": c["ordinal"], "type": c["type"],
                "comment": c.get("comment") or "", "null_pct": p.get("null_pct"), "distinct_count": p.get("distinct_count"),
                "distinct_pct": p.get("distinct_pct"), "min": p.get("min_val"), "max": p.get("max_val"),
                "top_values": "; ".join(f"{t['v']} ({t['n']})" for t in (p.get("top_values") or [])[:5]),
                "top_pattern": (p.get("patterns") or [{}])[0].get("p", "") if p.get("patterns") else "",
                "flags": ", ".join(p.get("flags") or []),
                "tags": a.get("tags", ""), "cdm_entity": a.get("cdm_entity", ""), "cdm_attribute": a.get("cdm_attribute", ""),
                "notes": a.get("notes", "")})
    return tables, cols


def relationships(con, schemas: set[str] | None = None) -> list[dict]:
    cur = con.execute(f"SELECT * EXCLUDE (found_at) FROM {META}.relationships ORDER BY confidence DESC")
    names = [d[0] for d in cur.description]
    rs = [dict(zip(names, r)) for r in cur.fetchall()]
    return [r for r in rs if not schemas or (r["from_schema"] in schemas and r["to_schema"] in schemas)]


def _sheet(wb, title, rows):
    ws = wb.create_sheet(title)
    if not rows:
        ws.append(["(empty)"])
        return
    head = list(rows[0].keys())
    ws.append(head)
    for r in rows:
        ws.append([r[h] for h in head])
    fill = PatternFill("solid", fgColor="1F3A5F")
    for i, h in enumerate(head, 1):
        cell = ws.cell(row=1, column=i)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(vertical="center")
        width = max([len(str(h))] + [min(len(str(r[h] if r[h] is not None else "")), 60) for r in rows[:500]])
        ws.column_dimensions[get_column_letter(i)].width = max(8, min(width + 2, 60))
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions


def excel(con, cat: dict, schemas: set[str] | None = None) -> bytes:
    tables, cols = catalog_rows(con, cat)
    wb = Workbook()
    wb.remove(wb.active)
    _sheet(wb, "Tables", tables)
    _sheet(wb, "Columns", cols)
    _sheet(wb, "Relationships", relationships(con, schemas))
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def as_json(con, cat: dict, schemas: set[str] | None = None) -> str:
    tables, cols = catalog_rows(con, cat)
    by = {}
    for t in tables:
        by[(t["schema"], t["table"])] = {**t, "columns": []}
    for c in cols:
        by[(c["schema"], c["table"])]["columns"].append({k: v for k, v in c.items() if k not in ("schema", "table")})
    return json.dumps({"tables": list(by.values()), "relationships": relationships(con, schemas)}, indent=2, default=str)


def markdown(con, cat: dict, schema: str, table: str) -> str:
    tb = cat["tables"][(schema, table)]
    _, prof = load_profile(con, schema, table)
    rels = [r for r in relationships(con) if (r["from_schema"], r["from_table"]) == (schema, table) or (r["to_schema"], r["to_table"]) == (schema, table)]
    ta = tb.get("annotation") or {}
    lines = [f"# {schema}.{table}", ""]
    if tb.get("comment"):
        lines += [tb["comment"], ""]
    lines += [f"- Rows: {tb['row_count']:,}" if tb["row_count"] is not None else "- Rows: n/a",
              f"- Columns: {len(tb['columns'])}",
              f"- Candidate keys: {', '.join(tb['candidate_keys']) or '—'}"]
    if ta.get("cdm_entity"):
        lines.append(f"- CDM entity: {ta['cdm_entity']}")
    if ta.get("notes"):
        lines.append(f"- Notes: {ta['notes']}")
    lines += ["", "| # | Column | Type | Null % | Distinct | Flags | Tags | CDM attribute | Comment |", "|---|---|---|---|---|---|---|---|---|"]
    for c in tb["columns"]:
        p = prof.get(c["column"], {})
        a = c.get("annotation") or {}
        cdm = ".".join(x for x in (a.get("cdm_entity"), a.get("cdm_attribute")) if x)
        cell = lambda v: "" if v is None else str(v).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {c['ordinal']} | `{c['column']}` | {c['type']} | {cell(p.get('null_pct'))} | {cell(p.get('distinct_count'))} | "
                     f"{cell(', '.join(p.get('flags') or []))} | {cell(a.get('tags'))} | {cell(cdm)} | {cell(c.get('comment'))} |")
    if rels:
        lines += ["", "## Relationships", ""]
        for r in rels:
            lines.append(f"- `{r['from_table']}.{r['from_column']}` → `{r['to_table']}.{r['to_column']}` "
                         f"(overlap {r['overlap_pct']}%, confidence {r['confidence']})")
    return "\n".join(lines) + "\n"
