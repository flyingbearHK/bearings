"""Code lists: low-cardinality columns (status, channel, country, tier…) with all their values, and comparison of
two code lists – typically the same concept in two source systems – for value mapping and reference data.

Values are captured by `bearings insights` into _meta.code_values, so browsing and comparing is instant and works
across local and cached tables.
"""
from __future__ import annotations

from rapidfuzz import fuzz, process

from .db import META, has_meta, qi
from .profiler import family

CODE_MAX = 200          # at most this many distinct values
CODE_MAX_LEN = 40       # average length above this is free text, not a code


def is_code(p: dict) -> bool:
    flags = set(p.get("flags") or [])
    nn = (p.get("row_count") or 0) - (p.get("null_count") or 0)
    d = p.get("distinct_count") or 0
    fam = family(p.get("data_type") or "")
    if fam not in ("string", "numeric") or d < 2 or d > CODE_MAX or not nn or d > 0.5 * nn:
        return False
    if {"candidate_pk", "unique", "unique_with_nulls", "all_null"} & flags or any(f.startswith("pii_") for f in flags):
        return False
    if fam == "numeric" and not str(p.get("data_type", "")).upper().endswith("INT") and "INT" not in str(p.get("data_type", "")).upper():
        return False  # decimals / doubles are measures
    return (p.get("avg_len") or 0) <= CODE_MAX_LEN


def capture(con, src: str, cols: list[dict]) -> dict[str, list[tuple[str, int]]]:
    """{column: [(value, count)]} for the code-list columns of a table (profile dicts)."""
    out = {}
    for p in cols:
        if not is_code(p):
            continue
        q = qi(p["column_name"])
        out[p["column_name"]] = con.execute(f"SELECT CAST({q} AS VARCHAR), count(*) FROM {src} WHERE {q} IS NOT NULL "
                                            "GROUP BY 1 ORDER BY 2 DESC, 1").fetchall()
    return out


def available(con) -> bool:
    return has_meta(con, "code_values")


def lists(con, schemas: set[str] | None = None) -> list[dict]:
    if not available(con):
        return []
    rows = con.execute(f"""SELECT schema_name, table_name, column_name, count(*) AS values, sum(n) AS rows,
                                  list(value ORDER BY n DESC, value)[1:6] AS top, bool_or(on_sample)
                           FROM {META}.code_values GROUP BY 1, 2, 3 ORDER BY 1, 2, 3""").fetchall()
    return [{"schema": s, "table": t, "column": c, "values": v, "rows": n, "top": top, "on_sample": bool(smp)}
            for s, t, c, v, n, top, smp in rows if not schemas or s in schemas]


def values(con, schema: str, table: str, column: str) -> list[dict]:
    if not available(con):
        return []
    return [{"value": v, "n": n} for v, n in con.execute(
        f"SELECT value, n FROM {META}.code_values WHERE schema_name=? AND table_name=? AND column_name=? ORDER BY n DESC, value",
        [schema, table, column]).fetchall()]


def similar(con, schema: str, table: str, column: str, schemas: set[str] | None = None, limit: int = 15) -> list[dict]:
    """Other code lists sharing values with this one (same concept elsewhere): share of the smaller list found in the
    other, ignoring case and spaces. Name similarity breaks ties."""
    if not available(con):
        return []
    rows = con.execute(f"""
        WITH a AS (SELECT DISTINCT upper(trim(value)) v FROM {META}.code_values WHERE schema_name=? AND table_name=? AND column_name=?),
             o AS (SELECT schema_name s, table_name t, column_name c, upper(trim(value)) v FROM {META}.code_values
                   WHERE NOT (schema_name=? AND table_name=? AND column_name=?))
        SELECT s, t, c, count(*) FILTER (WHERE v IN (SELECT v FROM a)) AS matched, count(DISTINCT v) AS total,
               (SELECT count(*) FROM a) AS mine
        FROM o GROUP BY 1, 2, 3 HAVING count(*) FILTER (WHERE v IN (SELECT v FROM a)) >= 2""",
                       [schema, table, column] * 2).fetchall()
    out = []
    for s, t, c, m, tot, mine in rows:
        if schemas and s not in schemas:
            continue
        contain = m / max(1, min(tot, mine))
        if contain < 0.5 or (s, t) == (schema, table):
            continue
        out.append({"schema": s, "table": t, "column": c, "matched": m, "values": tot, "containment": round(contain, 3),
                    "name_score": round(fuzz.token_set_ratio(column.lower().replace("_", " "), c.lower().replace("_", " ")) / 100, 2)})
    out.sort(key=lambda x: (-x["containment"], -x["name_score"], -x["matched"]))
    return out[:limit]


def compare(con, left: tuple[str, str, str], right: tuple[str, str, str]) -> dict:
    """Value-by-value comparison of two code lists: in both, only left, only right (ignoring case and spaces),
    with a suggested match for unmatched values (fuzzy)."""
    a = {v: n for v, n in ((x["value"], x["n"]) for x in values(con, *left))}
    b = {v: n for v, n in ((x["value"], x["n"]) for x in values(con, *right))}
    norm = lambda v: " ".join(str(v).upper().split())
    nb = {}
    for v in b:
        nb.setdefault(norm(v), []).append(v)
    rows, used_b = [], set()
    for v, n in sorted(a.items(), key=lambda x: -x[1]):
        m = nb.get(norm(v))
        if m:
            w = m[0]
            used_b.add(w)
            rows.append({"left": v, "left_n": n, "right": w, "right_n": b[w], "status": "same" if w == v else "case/space"})
        else:
            rows.append({"left": v, "left_n": n, "right": None, "right_n": None, "status": "only left"})
    only_b = [w for w in b if w not in used_b]
    for w in sorted(only_b, key=lambda x: -b[x]):
        rows.append({"left": None, "left_n": None, "right": w, "right_n": b[w], "status": "only right"})
    # suggestions for unmatched values on each side
    left_un = [r["left"] for r in rows if r["status"] == "only left"]
    for r in rows:
        if r["status"] == "only left" and only_b:
            hit = process.extractOne(norm(r["left"]), {w: norm(w) for w in only_b}, scorer=fuzz.WRatio)
            if hit and hit[1] >= 80:
                r["suggestion"] = hit[2]
        elif r["status"] == "only right" and left_un:
            hit = process.extractOne(norm(r["right"]), {v: norm(v) for v in left_un}, scorer=fuzz.WRatio)
            if hit and hit[1] >= 80:
                r["suggestion"] = hit[2]
    same = sum(1 for r in rows if r["status"] in ("same", "case/space"))
    return {"left": ".".join(left), "right": ".".join(right), "rows": rows, "matched": same,
            "left_values": len(a), "right_values": len(b),
            "only_left": sum(1 for r in rows if r["status"] == "only left"),
            "only_right": sum(1 for r in rows if r["status"] == "only right")}
