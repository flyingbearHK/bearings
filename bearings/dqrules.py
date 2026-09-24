"""Data-quality rule suggestions from what profiling and insights found, exported for the tools that run them:

- Databricks DQX (YAML checks: criticality / check.function / check.arguments, optional filter)
- Great Expectations 1.x (expectation suite JSON: name / expectations[type, kwargs, severity])
- Microsoft Purview Data Quality (a CSV / Excel sheet with the Purview rule type and settings to key in – Purview has
  no rule import file)

Each rule says why it was suggested and how many rows pass today. Rules that pass on all rows are `error`; rules
that describe a problem found (orphans, outliers, a second date format) are `warn`.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile

from . import codes, insights
from .db import qi
from .profiler import DATEISH_NAME, KEYISH_NAME, family, load_profile

IN_LIST_MAX = 50
AMOUNT_WORDS = {"amount", "amt", "revenue", "price", "cost", "qty", "quantity", "balance", "points", "rate", "fee", "total",
                "nights", "count", "size", "sqm", "occupancy", "adults", "children", "value", "tax", "discount"}


class _Words:
    """Matches a column name whose words (snake_case or CamelCase) include an amount-like word."""
    def search(self, name: str) -> bool:
        words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name).lower().split("_")
        return bool(AMOUNT_WORDS & set(words))


AMOUNT_NAME = _Words()
NOT_FUTURE_NAME = re.compile(r"birth|dob|created|modified|updated|posted|posting|insert|load|enrol|consent|opening|cancel", re.I)
PURVIEW = {"not_null": "Empty/blank fields", "not_empty": "Empty/blank fields", "unique": "Unique values",
           "unique_combo": "Duplicate rows", "in_list": "Custom (SQL expression)", "regex": "String format match",
           "non_negative": "Custom (SQL expression)", "range": "Custom (SQL expression)",
           "not_in_future": "Custom (SQL expression)", "valid_date": "Data type match", "foreign_key": "Table lookup",
           "filled_when": "Custom (SQL expression)"}


def spark_format(fmt: str) -> str:
    for a, b in (("%Y", "yyyy"), ("%m", "MM"), ("%d", "dd"), ("%b", "MMM"), ("%H", "HH"), ("%M", "mm"), ("%S", "ss")):
        fmt = fmt.replace(a, b)
    return fmt


def pattern_regex(p: str) -> str:
    """Profile value shape (A = upper, a = lower, 9 = digit) → anchored regex, e.g. 'AA99999' → ^[A-Z]{2}[0-9]{5}$."""
    out = []
    for m in re.finditer(r"(A+|a+|9+|.)", p):
        run = m.group(0)
        cls = {"A": "[A-Z]", "a": "[a-z]", "9": "[0-9]"}.get(run[0])
        if cls:
            out.append(cls + (f"{{{len(run)}}}" if len(run) > 1 else ""))
        else:
            out.append(re.escape(run))
    return "^" + "".join(out) + "$"


def _sql_str(v) -> str:
    return "'" + str(v).replace("'", "''") + "'"


def table_rules(con, cat: dict, schema: str, table: str, rels: list[dict] | None = None) -> list[dict]:
    tb = cat["tables"].get((schema, table))
    tp, prof = load_profile(con, schema, table)
    if not tb or not prof:
        return []
    ins = insights.read(con, schema, table)
    opt = insights.optional_view(con, schema, table)
    full = (tb.get("remote") or {}).get("full_name") or f"{schema}.{table}"
    rows = (tp or {}).get("row_count") or 0
    out: list[dict] = []

    def add(rule, cols, crit, args, reason, passing=None, flt=None):
        out.append({"id": f"{schema}.{table}:{rule}:{'+'.join(cols)}", "schema": schema, "table": table, "dataset": full,
                    "rule": rule, "columns": cols, "criticality": crit, "args": args, "reason": reason,
                    "passing_pct": None if passing is None else round(passing, 2), "filter": flt,
                    "purview_rule_type": PURVIEW[rule]})

    code_vals = {}
    if codes.available(con):
        for c in prof:
            v = codes.values(con, schema, table, c)
            if v:
                code_vals[c] = v
    times = {x["column_name"]: x for x in ins.get("time") or []}
    for c, p in prof.items():
        flags = set(p.get("flags") or [])
        fam = family(p["data_type"])
        if "all_null" in flags:
            continue
        nn = (p["row_count"] or 0) - (p["null_count"] or 0)
        # completeness
        if not p["null_count"]:
            if fam == "string" and not p.get("blank_count"):
                add("not_empty", [c], "error", {"trim_strings": True}, "never empty today")
            else:
                add("not_null", [c], "error", {}, "never null today")
        # allowed values
        vals = code_vals.get(c)
        if vals and len(vals) <= IN_LIST_MAX and not any(f.startswith("pii_") for f in flags) and "placeholders" not in flags:
            add("in_list", [c], "error", {"allowed": [x["value"] for x in vals], "nulls_allowed": bool(p["null_count"])},
                f"a code list of {len(vals)} values")
        # format
        pats = p.get("patterns") or []
        if (fam == "string" and pats and not vals and (p.get("distinct_count") or 0) >= 20 and (p.get("max_len") or 0) <= 40
                and nn and pats[0]["n"] / nn >= 0.99 and "type_hint" not in flags):
            share = 100 * pats[0]["n"] / nn
            add("regex", [c], "error" if share >= 100 else "warn", {"regex": pattern_regex(pats[0]["p"])},
                f"{share:.1f}% of values have the shape {pats[0]['p']}", share)
        # text dates
        h = p.get("type_hint") or {}
        if fam == "string" and h.get("type") in ("DATE", "TIMESTAMP") and h.get("formats"):
            fmt, share = next(iter(h["formats"].items()))
            add("valid_date", [c], "error" if share >= 1 else "warn", {"date_format": spark_format(fmt), "strftime": fmt},
                f"a date stored as text; {share * 100:.0f}% use {fmt}" + (f" (other formats: {', '.join(list(h['formats'])[1:])})" if len(h["formats"]) > 1 else ""),
                share * 100 * h["share"])
        # numbers
        if fam == "numeric" and not KEYISH_NAME.search(c) and nn:
            neg = p.get("negative_count") or 0
            if neg == 0 and AMOUNT_NAME.search(c):
                add("non_negative", [c], "error", {"limit": 0}, "never negative today")
            elif 0 < neg <= 0.05 * nn and AMOUNT_NAME.search(c):
                add("non_negative", [c], "warn", {"limit": 0}, f"{neg:,} negative values (refunds, reversals or errors?)", 100 * (1 - neg / nn))
            if p.get("outlier_count"):
                lo, hi = p["outlier_low"], p["outlier_high"]
                if neg == 0 and lo is not None:
                    lo = max(lo, 0)
                add("range", [c], "warn", {"min_limit": round(lo, 2), "max_limit": round(hi, 2)},
                    f"{p['outlier_count']:,} far-out values (beyond 3 × IQR)", 100 * (1 - p["outlier_count"] / nn))
        # dates in the future
        t = times.get(c)
        if t and not t["future_rows"] and (t["kind"] != "event" or NOT_FUTURE_NAME.search(c)) and NOT_FUTURE_NAME.search(c):
            add("not_in_future", [c], "error", {"offset": 0}, "no future dates today")
    # keys
    g = ins.get("grain") or {}
    if g.get("combos"):
        cols = g["combos"][0]
        dup = g.get("dup_rows") or 0
        add("unique" if len(cols) == 1 else "unique_combo", cols, "error" if not dup else "warn", {},
            "the grain of the table" + (f" – {dup:,} duplicate rows today" if dup else ""),
            100 * (1 - dup / rows) if rows else None)
    # references
    for r in rels or []:
        if (r["from_schema"], r["from_table"]) != (schema, table) or (r.get("confidence") or 0) < 0.8 or (r.get("overlap_pct") or 0) < 95:
            continue
        ref = cat["tables"].get((r["to_schema"], r["to_table"]))
        ref_name = ((ref or {}).get("remote") or {}).get("full_name") or f"{r['to_schema']}.{r['to_table']}"
        orphans = r.get("orphan_rows")
        clean = (orphans == 0) if orphans is not None else r["overlap_pct"] >= 99.99
        add("foreign_key", [r["from_column"]], "error" if clean else "warn",
            {"ref_table": ref_name, "ref_columns": [r["to_column"]]},
            f"references {r['to_table']}.{r['to_column']}" + (f" – {orphans:,} orphan rows today" if orphans else ""),
            100 * (1 - (orphans or 0) / rows) if rows and orphans is not None else r["overlap_pct"])
    # conditional completeness
    for rl in opt.get("rules") or []:
        if rl["coverage"] < 0.95 or any(v is None for v in rl["when_values"]):
            continue
        flt = f"{qi(rl['by_column'])} IN ({', '.join(_sql_str(v) for v in rl['when_values'])})"
        add("filled_when", [rl["column_name"]], "warn", {}, rl["sentence"], 100 * rl["coverage"], flt)
    return out


def all_rules(con, cat: dict, tables: list[tuple[str, str]]) -> list[dict]:
    from .export import relationships
    rels = relationships(con)
    out = []
    for s, t in tables:
        out += table_rules(con, cat, s, t, rels)
    return out


# ------------------------------------------------------------------ renderers
def _y(v) -> str:
    return json.dumps(v, ensure_ascii=False)   # JSON scalars and flow lists are valid YAML


def dqx_check(r: dict) -> dict | None:
    c = r["columns"]
    a = r["args"]
    fn = {"not_null": ("is_not_null", {"column": c[0]}),
          "not_empty": ("is_not_null_and_not_empty", {"column": c[0], "trim_strings": True}),
          "unique": ("is_unique", {"columns": c}), "unique_combo": ("is_unique", {"columns": c}),
          "in_list": ("is_in_list" if a.get("nulls_allowed") else "is_not_null_and_is_in_list", {"column": c[0], "allowed": a.get("allowed")}),
          "regex": ("regex_match", {"column": c[0], "regex": a.get("regex")}),
          "non_negative": ("is_not_less_than", {"column": c[0], "limit": 0}),
          "range": ("is_in_range", {"column": c[0], "min_limit": a.get("min_limit"), "max_limit": a.get("max_limit")}),
          "not_in_future": ("is_not_in_future", {"column": c[0], "offset": 0}),
          "valid_date": ("is_valid_date", {"column": c[0], "date_format": a.get("date_format")}),
          "foreign_key": ("foreign_key", {"columns": c, "ref_columns": a.get("ref_columns"), "ref_table": a.get("ref_table")}),
          "filled_when": ("is_not_null_and_not_empty", {"column": c[0]}),
          }.get(r["rule"])
    if not fn:
        return None
    d = {"criticality": r["criticality"], "name": f"{r['rule']}_{'_'.join(c)}".lower()[:120],
         "check": {"function": fn[0], "arguments": fn[1]}}
    if r.get("filter"):
        d["filter"] = r["filter"].replace('"', "`")
    return d


def to_dqx_yaml(rules: list[dict], dataset: str = "") -> str:
    lines = [f"# DQX checks{' for ' + dataset if dataset else ''} – suggested by Bearings from the profile; review before use",
             "# Load with: DQEngine(...).apply_checks_by_metadata(df, yaml.safe_load(open(path)))"]
    for r in rules:
        d = dqx_check(r)
        if not d:
            continue
        lines.append(f"# {r['reason']}")
        lines.append(f"- criticality: {d['criticality']}")
        lines.append(f"  name: {_y(d['name'])}")
        if d.get("filter"):
            lines.append(f"  filter: {_y(d['filter'])}")
        lines.append("  check:")
        lines.append(f"    function: {d['check']['function']}")
        lines.append("    arguments:")
        for k, v in d["check"]["arguments"].items():
            lines.append(f"      {k}: {_y(v)}")
    return "\n".join(lines) + "\n"


def gx_expectations(r: dict) -> list[dict]:
    c, a = r["columns"], r["args"]
    sev = "critical" if r["criticality"] == "error" else "warning"
    e = {"not_null": [("expect_column_values_to_not_be_null", {"column": c[0]})],
         "not_empty": [("expect_column_values_to_not_be_null", {"column": c[0]}),
                       ("expect_column_value_lengths_to_be_between", {"column": c[0], "min_value": 1})],
         "unique": [("expect_column_values_to_be_unique", {"column": c[0]})],
         "unique_combo": [("expect_compound_columns_to_be_unique", {"column_list": c})],
         "in_list": [("expect_column_values_to_be_in_set", {"column": c[0], "value_set": a.get("allowed")})],
         "regex": [("expect_column_values_to_match_regex", {"column": c[0], "regex": a.get("regex")})],
         "non_negative": [("expect_column_values_to_be_between", {"column": c[0], "min_value": 0})],
         "range": [("expect_column_values_to_be_between", {"column": c[0], "min_value": a.get("min_limit"), "max_value": a.get("max_limit")})],
         "valid_date": [("expect_column_values_to_match_strftime_format", {"column": c[0], "strftime_format": a.get("strftime")})],
         "filled_when": [("expect_column_values_to_not_be_null", {"column": c[0], "row_condition": (r.get("filter") or "").replace('"', "`"),
                                                                   "condition_parser": "spark"})],
         }.get(r["rule"], [])
    return [{"type": t, "kwargs": kw, "meta": {"reason": r["reason"], "suggested_by": "bearings"}, "severity": sev} for t, kw in e]


def to_gx_suite(rules: list[dict], name: str) -> dict:
    exps = [x for r in rules for x in gx_expectations(r)]
    skipped = sorted({r["rule"] for r in rules if not gx_expectations(r)})
    return {"name": name, "expectations": exps,
            "meta": {"suggested_by": "bearings", "note": "review before use" + (f"; not expressible in GX: {', '.join(skipped)}" if skipped else "")}}


def purview_row(r: dict) -> dict:
    c, a = r["columns"], r["args"]
    col = c[0]
    setting = {
        "not_null": "column must not be empty", "not_empty": "column must not be empty or blank",
        "unique": "values must be unique", "unique_combo": f"no duplicate rows on {', '.join(c)}",
        "in_list": f"{col} IN ({', '.join(_sql_str(v) for v in a.get('allowed') or [])})",
        "regex": a.get("regex"), "non_negative": f"{col} >= 0",
        "range": f"{col} BETWEEN {a.get('min_limit')} AND {a.get('max_limit')}",
        "not_in_future": f"{col} <= current_date()", "valid_date": f"date format {a.get('date_format')}",
        "foreign_key": f"{col} found in {a.get('ref_table')}.{(a.get('ref_columns') or [''])[0]}",
        "filled_when": f"{col} IS NOT NULL when {r.get('filter')}",
    }[r["rule"]]
    return {"table": r["dataset"], "columns": ", ".join(c), "rule": r["rule"], "purview_rule_type": r["purview_rule_type"],
            "setting_or_expression": setting, "criticality": r["criticality"], "passing_pct_today": r["passing_pct"],
            "reason": r["reason"]}


def to_csv(rules: list[dict]) -> str:
    rows = [purview_row(r) for r in rules]
    bio = io.StringIO()
    if rows:
        w = csv.DictWriter(bio, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return bio.getvalue()


def bundle(rules: list[dict]) -> bytes:
    """zip: dqx/<table>.yml, gx/<table>.json, purview_rules.csv, README.txt"""
    by: dict = {}
    for r in rules:
        by.setdefault((r["schema"], r["table"], r["dataset"]), []).append(r)
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for (s, t, ds), rs in by.items():
            z.writestr(f"dqx/{s}.{t}.yml", to_dqx_yaml(rs, ds))
            z.writestr(f"gx/{s}.{t}.json", json.dumps(to_gx_suite(rs, f"{s}.{t}"), indent=2, ensure_ascii=False))
        z.writestr("purview_rules.csv", to_csv(rules))
        z.writestr("README.txt", README)
    return bio.getvalue()


README = """Data-quality rules suggested by Bearings from the profile, insights and relationships.
Review them before use: they describe the data as it is today.

dqx/            Databricks DQX checks (YAML), one file per table: apply_checks_by_metadata(df, checks)
gx/             Great Expectations 1.x expectation suites (JSON), one per table: gx.ExpectationSuite(**json.load(f))
purview_rules.csv  Microsoft Purview Data Quality: one row per rule with the Purview rule type and the setting or SQL
                   expression to enter (Purview has no rule import file)

criticality error = passes on every row today; warn = describes a problem found (orphans, outliers, extra formats…).
"""
