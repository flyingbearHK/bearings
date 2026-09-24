"""Near-duplicate records: the same customer, guest or supplier captured twice with small differences.

Columns are given roles from their names and profile flags (email, phone, date of birth, first / last / full name,
postcode). Candidate pairs come from "blocks" – rows sharing a normalised email, phone, name, or birth date + start of
the last name – so the whole table is never compared with itself. Each pair is scored on every role both rows have
(exact match for email / phone / date, Jaro-Winkler similarity for names), and pairs scoring at least the threshold
are grouped into clusters. On demand only (it reads rows), never stored.
"""
from __future__ import annotations

import re

from .db import fq, qi
from .profiler import DATE_FORMATS, PLACEHOLDERS, _sql_list, family, load_profile

ROLES = [  # (role, name pattern) – first match wins
    ("email", re.compile(r"e_?mail", re.I)),
    ("phone", re.compile(r"phone|mobile|cell|tel(ephone)?\b|fax", re.I)),
    ("dob", re.compile(r"birth|\bdob\b|_dob|dob_", re.I)),
    ("first_name", re.compile(r"first_?name|given_?name|fore_?name", re.I)),
    ("last_name", re.compile(r"last_?name|family_?name|sur_?name", re.I)),
    ("postcode", re.compile(r"post_?code|zip", re.I)),
    ("name", re.compile(r"(^|_)(full_?|company_?|customer_?|guest_?|supplier_?|vendor_?|account_?)?name$|Name$", re.I)),
]
WEIGHT = {"email": 3.0, "phone": 2.0, "dob": 2.0, "first_name": 1.0, "last_name": 1.5, "name": 2.0, "postcode": 1.0}
MAX_BLOCK = 50        # skip blocks with more rows than this (a shared default value, not a person)
MAX_PAIRS = 200_000


def roles(con, schema: str, table: str) -> dict[str, str]:
    """{role: column} guessed from column names and profile flags."""
    _, prof = load_profile(con, schema, table)
    out: dict[str, str] = {}
    for c, p in prof.items():
        flags = set(p.get("flags") or [])
        if {"all_null", "constant"} & flags:
            continue
        if "pii_email" in flags and "email" not in out:
            out["email"] = c
            continue
        if "pii_phone" in flags and "phone" not in out:
            out["phone"] = c
            continue
        for role, rx in ROLES:
            if rx.search(c) and role not in out and not re.search(r"(_id|_code|_type|_flag|_date_?txt)$", c, re.I):
                if role == "dob" and family(p["data_type"]) not in ("temporal", "string"):
                    continue
                if role in ("first_name", "last_name", "name", "email", "phone", "postcode") and family(p["data_type"]) != "string":
                    continue
                out[role] = c
                break
    if "name" in out and ("first_name" in out or "last_name" in out):
        out.pop("name")
    return out


def _norm(role: str, col: str) -> str:
    q = qi(col)
    v = f"trim(CAST({q} AS VARCHAR))"
    empty = f"({v} = '' OR upper({v}) IN ({_sql_list(PLACEHOLDERS)}))"
    if role == "email":
        e = f"lower({v})"
    elif role == "phone":
        e = f"right(regexp_replace({v}, '[^0-9]', '', 'g'), 8)"
    elif role == "dob":
        parts = [f"TRY_CAST({v} AS DATE)"] + [f"CAST(TRY_STRPTIME({v}, '{f}') AS DATE)" for f in DATE_FORMATS]
        e = f"CAST(coalesce({', '.join(parts)}) AS VARCHAR)"
    elif role == "postcode":
        e = f"upper(regexp_replace({v}, '[^0-9A-Za-z]', '', 'g'))"
    else:
        e = f"trim(regexp_replace(lower(strip_accents({v})), '[^a-z ]', '', 'g'))"
    return f"CASE WHEN {q} IS NULL OR {empty} THEN NULL ELSE nullif({e}, '') END"


def find(con, schema: str, table: str, columns: dict[str, str] | None = None, threshold: float = 0.9,
         limit: int = 50) -> dict:
    """Near-duplicate pairs and clusters in a local table. columns: {role: column} (default: guessed)."""
    cols = columns or roles(con, schema, table)
    if len(cols) < 2:
        return {"columns": cols, "error": "Need at least two identifying columns (e.g. name + birth date, or email + name). "
                                          "Pick them by role.", "pairs": 0, "groups": [], "examples": []}
    tp, _ = load_profile(con, schema, table)
    key = ((tp or {}).get("candidate_keys") or [None])[0]
    src = fq(schema, table)
    norm = ", ".join(f"{_norm(r, c)} AS {qi('n_' + r)}" for r, c in cols.items())
    keys = []
    for r in ("email", "phone"):
        if r in cols:
            keys.append(f"n_{r}")
    if "first_name" in cols and "last_name" in cols:
        keys.append("n_first_name || '|' || n_last_name")
    elif "name" in cols:
        keys.append("n_name")
    last = "n_last_name" if "last_name" in cols else "n_name" if "name" in cols else "n_first_name" if "first_name" in cols else None
    if "dob" in cols and last:
        keys.append(f"n_dob || '|' || left({last}, 3)")
    if "postcode" in cols and last:
        keys.append(f"n_postcode || '|' || left({last}, 3)")
    if not keys:
        return {"columns": cols, "error": "No way to group candidate rows: add an email, phone, name or birth date column.",
                "pairs": 0, "groups": [], "examples": []}
    blocks = " UNION ALL ".join(f"SELECT rid, ({k}) AS bk, {i} AS b FROM n WHERE ({k}) IS NOT NULL" for i, k in enumerate(keys))
    sims = []
    for r in cols:
        a, b = f"a.{qi('n_' + r)}", f"b.{qi('n_' + r)}"
        s = (f"jaro_winkler_similarity({a}, {b})" if r in ("first_name", "last_name", "name")
             else f"CASE WHEN {a} = {b} THEN 1.0 ELSE 0.0 END")
        sims.append((r, f"CASE WHEN {a} IS NULL OR {b} IS NULL THEN NULL ELSE {s} END"))
    wsum = " + ".join(f"coalesce({s} * {WEIGHT[r]}, 0)" for r, s in sims)
    wden = " + ".join(f"CASE WHEN {s} IS NULL THEN 0 ELSE {WEIGHT[r]} END" for r, s in sims)
    ncmp = " + ".join(f"CASE WHEN {s} IS NULL THEN 0 ELSE 1 END" for r, s in sims)
    show = [key] if key else []
    show += [c for c in cols.values() if c not in show]
    sel_a = ", ".join(f"ta.{qi(c)} AS {qi('a_' + c)}" for c in show)
    sel_b = ", ".join(f"tb.{qi(c)} AS {qi('b_' + c)}" for c in show)
    con.execute(f"""CREATE OR REPLACE TEMP TABLE __bearings_dup_pairs AS
        WITH n AS (SELECT rowid AS rid, {norm} FROM {src}),
             bl AS ({blocks}),
             sized AS (SELECT *, count(*) OVER (PARTITION BY b, bk) AS bn FROM bl),
             cand AS (SELECT DISTINCT x.rid AS ra, y.rid AS rb FROM sized x JOIN sized y
                        ON x.b = y.b AND x.bk = y.bk AND x.rid < y.rid WHERE x.bn <= {MAX_BLOCK} LIMIT {MAX_PAIRS}),
             sc AS (SELECT c.ra, c.rb, ({wsum}) / nullif({wden}, 0) AS score, {ncmp} AS compared
                    FROM cand c JOIN n a ON a.rid = c.ra JOIN n b ON b.rid = c.rb)
        SELECT * FROM sc WHERE compared >= 2 AND score >= {float(threshold)}""")
    try:
        pairs = con.execute("SELECT ra, rb, score FROM __bearings_dup_pairs").fetchall()
        examples = con.execute(f"""SELECT round(p.score, 3), {sel_a}, {sel_b}
            FROM __bearings_dup_pairs p JOIN {src} ta ON ta.rowid = p.ra JOIN {src} tb ON tb.rowid = p.rb
            ORDER BY p.score DESC, p.ra LIMIT {int(limit)}""")
        ex_cols = [d[0] for d in examples.description]
        ex_rows = examples.fetchall()
    finally:
        con.execute("DROP TABLE IF EXISTS __bearings_dup_pairs")
    # clusters (connected components)
    parent: dict = {}

    def root(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for a, b, _ in pairs:
        ra, rb = root(a), root(b)
        if ra != rb:
            parent[rb] = ra
    groups: dict = {}
    for x in list(parent):
        groups.setdefault(root(x), []).append(x)
    sizes = sorted((len(g) for g in groups.values()), reverse=True)
    total = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
    return {"columns": cols, "key": key, "shown_columns": show, "threshold": threshold, "pairs": len(pairs),
            "groups": len(sizes), "rows_in_groups": sum(sizes), "largest_group": sizes[0] if sizes else 0,
            "rows": total, "example_columns": ex_cols, "examples": [list(r) for r in ex_rows],
            "blocking": keys}
