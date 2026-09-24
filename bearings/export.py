"""Exports: Excel mapping workbook, JSON catalog, Markdown per table."""
from __future__ import annotations

import io
import json
import re

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
                "effective_null_pct": p.get("effective_null_pct"),
                "placeholders": ", ".join(f"{x['v']} ×{x['n']}" for x in (p.get("placeholder_values") or [])),
                "type_hint": hint_text(p.get("type_hint")),
                "flags": ", ".join(p.get("flags") or []),
                "tags": a.get("tags", ""), "cdm_entity": a.get("cdm_entity", ""), "cdm_attribute": a.get("cdm_attribute", ""),
                "notes": a.get("notes", "")})
    return tables, cols


def hint_text(h: dict | None) -> str:
    """{"type": "DATE", "share": 1.0, "formats": {...}} → 'DATE (100% parse; %Y-%m-%d 75%, %d/%m/%Y 25%)'."""
    if not h:
        return ""
    fm = ", ".join(f"{k} {v * 100:.0f}%" for k, v in (h.get("formats") or {}).items())
    return f"{h['type']} ({h['share'] * 100:.1f}% parse{'; ' + fm if fm else ''})"


def grain_text(g: dict | None) -> str:
    if not g or not g.get("combos"):
        return ""
    s = " + ".join(g["combos"][0])
    if g.get("dup_rows"):
        s += f" (except {g['dup_rows']:,} duplicate rows)"
    return s


def insight_rows(con, cat: dict) -> tuple[list[dict], list[dict], list[dict]]:
    """(grain & history per table, candidate entities, dependencies) for the Excel / JSON exports."""
    from . import insights
    from .relationships import with_targets
    if not insights.available(con):
        return [], [], []
    columns = {k: [c["column"] for c in t["columns"]] for k, t in cat["tables"].items()}
    rels = with_targets(con, columns)
    tables, ents, deps = [], [], []
    for (s, t), tb in cat["tables"].items():
        ins = insights.read(con, s, t)
        if not ins.get("computed_at"):
            continue
        prim = next((x for x in ins["time"] if x["is_primary"]), None)
        tables.append({"schema": s, "table": t, "grain": grain_text(ins["grain"]),
                       "primary_date": prim["column_name"] if prim else "",
                       "first_month": str(prim["first_month"])[:7] if prim else "", "last_month": str(prim["last_month"])[:7] if prim else "",
                       "months": prim["months_present"] if prim else None, "empty_months": prim["empty_months"] if prim else None,
                       "future_rows": prim["future_rows"] if prim else None,
                       "date_columns": ", ".join(f"{x['column_name']} ({x['kind']})" for x in ins["time"]),
                       "on_sample": bool((ins["grain"] or {}).get("on_sample")), "computed_at": ins["computed_at"]})
        _, prof = load_profile(con, s, t)
        cdm = {c["column"]: (c.get("annotation") or {}).get("cdm_entity") for c in tb["columns"] if (c.get("annotation") or {}).get("cdm_entity")}
        st = insights.structure(ins["dependencies"], {c: insights._col_info(p) for c, p in prof.items()}, rels, s, t, cdm=cdm)
        for e in st["entities"]:
            ents.append({"schema": s, "table": t, "entity": e["name"], "key": e["columns"][0],
                         "same_attribute_as_key": ", ".join(e["columns"][1:]),
                         "determines": ", ".join(" = ".join(d["columns"]) for d in e["determines"])})
        for d in ins["dependencies"]:
            deps.append({"schema": s, "table": t, "determinant": d["determinant"], "dependent": d["dependent"],
                         "strength_pct": round(100 * d["strength"], 2), "exceptions": d["exceptions"], "kind": d["kind"]})
    return tables, ents, deps


def relationships(con, schemas: set[str] | None = None) -> list[dict]:
    from .relationships import describe
    cur = con.execute(f"SELECT * EXCLUDE (found_at) FROM {META}.relationships ORDER BY confidence DESC")
    names = [d[0] for d in cur.description]
    rs = [dict(zip(names, r)) for r in cur.fetchall()]
    for r in rs:
        r["summary"] = describe(r)
    return [r for r in rs if not schemas or (r["from_schema"] in schemas and r["to_schema"] in schemas)]


def _mmd_id(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z_]", "_", s) or "x"


def _mmd_type(t: str) -> str:
    m = re.match(r"[A-Za-z]+", t or "")
    return (m.group(0) if m else "value").lower()


# crow's-foot ends: Mermaid token and draw.io arrow for each kind of end
ENDS = {"one": ("||", "||", "ERmandOne"), "zero_one": ("|o", "o|", "ERzeroToOne"),
        "one_many": ("}|", "|{", "ERoneToMany"), "zero_many": ("}o", "o{", "ERzeroToMany")}


def erd_model(con, cat: dict, schemas: set[str] | None = None, min_confidence: float = 0.8,
              tables: set[tuple[str, str]] | None = None) -> dict:
    """Entities (key and FK columns) and links (with crow's-foot ends from the measured cardinality and optionality)
    of the discovered relationships in scope. `tables` limits it to those entities (links with both ends among
    them); a selected table without links is still included."""
    rels = [r for r in relationships(con, schemas) if (r.get("confidence") or 0) >= min_confidence]
    if tables is not None:
        rels = [r for r in rels if (r["from_schema"], r["from_table"]) in tables and (r["to_schema"], r["to_table"]) in tables]
    tabs = {(r["from_schema"], r["from_table"]) for r in rels} | {(r["to_schema"], r["to_table"]) for r in rels}
    if tables is not None:
        tabs |= {k for k in tables if k in cat["tables"]}
    tabs = sorted(k for k in tabs if k in cat["tables"])
    names = [t for _, t in tabs]
    ident = {(s_, t): _mmd_id(t if names.count(t) == 1 else f"{s_}_{t}") for s_, t in tabs}
    fks: dict = {}
    for r in rels:
        fks.setdefault((r["from_schema"], r["from_table"]), set()).add(r["from_column"])
    entities = []
    for key in tabs:
        tb = cat["tables"][key]
        types = {c["column"]: c["type"] for c in tb["columns"]}
        pk = [c for c in (tb.get("candidate_keys") or [])[:1] if c in types]
        if not pk:  # no single-column key: the grain found by `bearings insights` (e.g. CustomerId + Channel)
            tp, _ = load_profile(con, *key)
            pk = [c for c in ((tp or {}).get("grain") or [[]])[0] if c in types]
        attrs = [(c, "PK") for c in pk] + [(c, "FK") for c in sorted(fks.get(key, set())) if c not in pk]
        entities.append({"id": ident[key], "schema": key[0], "table": key[1],
                         "attributes": [{"name": c, "type": _mmd_type(types.get(c)), "key": k} for c, k in attrs]})
    links = []
    for r in rels:
        card = r.get("cardinality")
        mandatory = not (r.get("fk_null_pct") or 0)
        some_childless = (r.get("parent_no_child_pct") or 0) > 0
        if card == "N:M":
            parent_end, child_end = "zero_many", "zero_many"
        else:
            parent_end = "one" if mandatory else "zero_one"
            if card == "1:1":
                child_end = "zero_one" if some_childless else "one"
            elif card == "1:N":
                child_end = "zero_many" if some_childless else "one_many"
            else:  # not measured (remote tables without a local copy)
                child_end = "zero_many"
        links.append({"parent": ident[(r["to_schema"], r["to_table"])], "child": ident[(r["from_schema"], r["from_table"])],
                      "label": r["from_column"], "parent_end": parent_end, "child_end": child_end,
                      "parent_arrow": ENDS[parent_end][2], "child_arrow": ENDS[child_end][2], "cardinality": card,
                      "summary": r.get("summary")})
    return {"entities": entities, "links": links}


def erd_mermaid(model: dict) -> str:
    lines = ["erDiagram"]
    for e in model["entities"]:
        lines.append(f"    {e['id']} {{")
        for a in e["attributes"]:
            lines.append(f"        {a['type']} {_mmd_id(a['name'])} {a['key']}")
        lines.append("    }")
    for ln in model["links"]:
        lines.append(f'    {ln["parent"]} {ENDS[ln["parent_end"]][0]}--{ENDS[ln["child_end"]][1]} {ln["child"]} : "{ln["label"]}"')
    return "\n".join(lines) + "\n"


def erd(con, cat: dict, schemas: set[str] | None = None, min_confidence: float = 0.8,
        tables: set[tuple[str, str]] | None = None) -> str:
    """Mermaid `erDiagram` of the discovered relationships in scope (see erd_model)."""
    return erd_mermaid(erd_model(con, cat, schemas, min_confidence, tables))


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
    grain, ents, deps = insight_rows(con, cat)
    if grain:
        _sheet(wb, "Grain & history", grain)
        _sheet(wb, "Candidate entities", ents)
        _sheet(wb, "Dependencies", deps)
    from . import codes, dqrules
    keys = set(cat["tables"])
    cv = [{"schema": c["schema"], "table": c["table"], "column": c["column"], "value": v["value"], "rows": v["n"]}
          for c in codes.lists(con) if (c["schema"], c["table"]) in keys for v in codes.values(con, c["schema"], c["table"], c["column"])]
    if cv:
        _sheet(wb, "Code lists", cv)
    rules = dqrules.all_rules(con, cat, sorted(keys))
    if rules:
        _sheet(wb, "DQ rules", [dqrules.purview_row(r) for r in rules])
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
    grain, ents, deps = insight_rows(con, cat)
    return json.dumps({"tables": list(by.values()), "relationships": relationships(con, schemas),
                       "insights": {"tables": grain, "candidate_entities": ents, "dependencies": deps}}, indent=2, default=str)


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
    from . import insights
    ins = insights.read(con, schema, table)
    if ins.get("grain"):
        lines.append(f"- Grain: one row per {grain_text(ins['grain'])}")
    prim = next((x for x in ins.get("time") or [] if x["is_primary"]), None)
    if prim:
        lines.append(f"- History ({prim['column_name']}): {str(prim['first_month'])[:7]} – {str(prim['last_month'])[:7]}, "
                     f"{prim['months_present']} months, {prim['empty_months']} empty"
                     + (f", {prim['future_rows']:,} future rows" if prim["future_rows"] else ""))
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
            card = f"{r['cardinality']}, " if r.get("cardinality") else ""
            lines.append(f"- `{r['from_table']}.{r['from_column']}` → `{r['to_table']}.{r['to_column']}` "
                         f"({card}overlap {r['overlap_pct']}%, confidence {r['confidence']})" + (f" – {r['summary']}" if r.get("summary") else ""))
    if ins.get("dependencies"):
        from .relationships import with_targets
        columns = {k: [c["column"] for c in t["columns"]] for k, t in cat["tables"].items()}
        cdm = {c["column"]: (c.get("annotation") or {}).get("cdm_entity") for c in tb["columns"] if (c.get("annotation") or {}).get("cdm_entity")}
        st = insights.structure(ins["dependencies"], {c: insights._col_info(p) for c, p in prof.items()},
                                with_targets(con, columns), schema, table, cdm=cdm)
        if st["entities"]:
            lines += ["", "## Candidate entities", "", "_Suggested from column dependencies – review before modelling._", ""]
            for e in st["entities"]:
                det = "; ".join(" = ".join(f"`{c}`" for c in d["columns"]) for d in e["determines"])
                lines.append(f"- **{e['name']}** – {' = '.join(f'`{c}`' for c in e['columns'])}" + (f" → {det}" if det else ""))
        if st["hierarchies"]:
            lines += ["", "## Hierarchies", ""]
            lines += ["- " + " → ".join(lv["name"] for lv in h["levels"]) for h in st["hierarchies"]]
        if st["dirty"] or st["notes"]:
            lines += ["", "## Data-quality and model notes", ""]
            lines += [f"- {d['sentence']}" for d in st["dirty"]] + [f"- {n['sentence']}" for n in st["notes"]]
    return "\n".join(lines) + "\n"
