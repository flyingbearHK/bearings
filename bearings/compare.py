"""Compare the attributes of records that are linked across tables (typically two source systems): join on a key
(e.g. crm.customer.PmsGuestCode = pms.guest.guest_code) and, for each pair of columns that hold the same thing,
count how often the values agree, differ, or are only filled on one side. Input for golden-record / survivorship
rules. Pairs are found by name similarity and by how often the values agree on a sample of the joined rows.
"""
from __future__ import annotations

import re

from rapidfuzz import fuzz

from .db import fq, qi
from .profiler import DATE_FORMATS, PLACEHOLDERS, _sql_list, family

SAMPLE = 5000         # joined rows used to find the column pairs
MAX_ROWS = 200_000    # joined rows compared
MAX_COLS = 40


def _nname(c: str) -> str:
    c = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", c).lower()
    for a, b in (("given", "first"), ("forename", "first"), ("family", "last"), ("surname", "last"), ("addr", "address"),
                 ("dob", "birth date"), ("mobile", "phone"), ("residence", "country"), ("nationality", "country"),
                 ("email address", "email"), ("e_mail", "email")):
        c = c.replace(a, b)
    return " ".join(w for w in re.split(r"[_\s]+", c) if w not in ("code", "cd", "txt", "text", "of", "the", "name") or len(c) < 6)


def _norm(q: str, dtype: str, dateish: bool) -> str:
    """Comparable form of a value (SQL expression q): dates parsed from any known format, numbers as numbers,
    text lower-cased with whitespace collapsed; blanks and placeholders become NULL."""
    v = f"trim(CAST({q} AS VARCHAR))"
    empty = f"({v} = '' OR upper({v}) IN ({_sql_list(PLACEHOLDERS)}))"
    if dateish:
        parts = [f"TRY_CAST({v} AS DATE)"] + [f"CAST(TRY_STRPTIME({v}, '{f}') AS DATE)" for f in DATE_FORMATS]
        e = f"CAST(coalesce({', '.join(parts)}) AS VARCHAR)"
    elif family(dtype) == "numeric":
        e = f"CAST(TRY_CAST({v} AS DOUBLE) AS VARCHAR)"
    else:
        e = f"lower(regexp_replace({v}, '\\s+', ' ', 'g'))"
    return f"CASE WHEN {q} IS NULL OR {empty} THEN NULL ELSE {e} END"


def attributes(con, left: tuple[str, str, str], right: tuple[str, str, str], cols_l: dict[str, str], cols_r: dict[str, str],
               hints: dict | None = None, pairs: list[tuple[str, str]] | None = None) -> dict:
    """left/right: (schema, table, key column); cols_*: {column: type}. hints: {(side, column): type_hint} for text dates.
    pairs: compare exactly these (left column, right column); default: found automatically."""
    (ls, lt, lk), (rs, rt, rk) = left, right
    hints = hints or {}
    L, R = fq(ls, lt), fq(rs, rt)
    join = f"FROM {L} l JOIN {R} r ON CAST(l.{qi(lk)} AS VARCHAR) = CAST(r.{qi(rk)} AS VARCHAR)"
    stats = con.execute(f"""SELECT (SELECT count(*) FROM {L}), (SELECT count(*) FROM {R}),
                                   (SELECT count(*) {join}), (SELECT count(DISTINCT CAST(l.{qi(lk)} AS VARCHAR)) {join})""").fetchone()
    cl = {c: t for c, t in cols_l.items() if c != lk and family(t) != "other"}
    cr = {c: t for c, t in cols_r.items() if c != rk and family(t) != "other"}
    cl = dict(list(cl.items())[:MAX_COLS])
    cr = dict(list(cr.items())[:MAX_COLS])

    def dateish(side, c, t):
        return family(t) == "temporal" or ((hints.get((side, c)) or {}).get("type") in ("DATE", "TIMESTAMP"))
    nl = {c: _norm(f"l.{qi(c)}", t, dateish("l", c, t)) for c, t in cl.items()}
    nr = {c: _norm(f"r.{qi(c)}", t, dateish("r", c, t)) for c, t in cr.items()}
    if pairs is None:
        cand = [(a, b) for a in cl for b in cr]
        aggs = [f"count(*) FILTER (WHERE ({nl[a]}) = ({nr[b]}))" for a, b in cand]
        both = [f"count(*) FILTER (WHERE ({nl[a]}) IS NOT NULL AND ({nr[b]}) IS NOT NULL)" for a, b in cand]
        r = con.execute(f"SELECT {', '.join(aggs + both)} {join} USING SAMPLE {SAMPLE} ROWS (reservoir, 7)").fetchone() if cand else []
        scored = []
        for i, (a, b) in enumerate(cand):
            eq, nb = r[i], r[len(cand) + i]
            rate = eq / nb if nb else 0
            ns = fuzz.token_set_ratio(_nname(a), _nname(b)) / 100
            if (rate >= 0.3 and nb >= 5) or ns >= 0.9:
                scored.append((rate + 0.5 * ns, a, b, rate, ns))
        scored.sort(reverse=True)
        used_l, used_r, pairs = set(), set(), []
        for _, a, b, rate, ns in scored:
            if a in used_l or b in used_r:
                continue
            used_l.add(a)
            used_r.add(b)
            pairs.append((a, b))
    out = []
    for a, b in pairs:
        dt = dateish("l", a, cl.get(a, cols_l.get(a, ""))) or dateish("r", b, cr.get(b, cols_r.get(b, "")))
        xa, xb = _norm("__l", cols_l.get(a, ""), dt), _norm("__r", cols_r.get(b, ""), dt)
        eq, eqn, differ, only_l, only_r, neither, n = con.execute(f"""
            SELECT count(*) FILTER (WHERE CAST(__l AS VARCHAR) = CAST(__r AS VARCHAR)),
                   count(*) FILTER (WHERE ({xa}) = ({xb})),
                   count(*) FILTER (WHERE ({xa}) IS NOT NULL AND ({xb}) IS NOT NULL AND ({xa}) <> ({xb})),
                   count(*) FILTER (WHERE ({xa}) IS NOT NULL AND ({xb}) IS NULL),
                   count(*) FILTER (WHERE ({xa}) IS NULL AND ({xb}) IS NOT NULL),
                   count(*) FILTER (WHERE ({xa}) IS NULL AND ({xb}) IS NULL),
                   count(*)
            FROM (SELECT l.{qi(a)} AS __l, r.{qi(b)} AS __r {join} LIMIT {MAX_ROWS}) x""").fetchone()
        both = eqn + differ
        out.append({"left": a, "right": b, "rows": n, "equal": eq, "equal_normalised": eqn, "differ": differ,
                    "only_left": only_l, "only_right": only_r, "neither": neither,
                    "agree_pct": round(100 * eqn / both, 1) if both else None,
                    "left_filled_pct": round(100 * (both + only_l) / n, 1) if n else None,
                    "right_filled_pct": round(100 * (both + only_r) / n, 1) if n else None,
                    "name_score": round(fuzz.token_set_ratio(_nname(a), _nname(b)) / 100, 2)})
    return {"left": ".".join(left), "right": ".".join(right), "left_rows": stats[0], "right_rows": stats[1],
            "joined_rows": stats[2], "joined_keys": stats[3], "pairs": out,
            "unpaired_left": [c for c in cl if c not in {p[0] for p in pairs}],
            "unpaired_right": [c for c in cr if c not in {p[1] for p in pairs}]}


def differences_sql(left: tuple[str, str, str], right: tuple[str, str, str], a: str, b: str, types: tuple[str, str],
                    hints: dict | None = None, limit: int = 100) -> str:
    (ls, lt, lk), (rs, rt, rk) = left, right
    hints = hints or {}
    da = family(types[0]) == "temporal" or (hints.get(("l", a)) or {}).get("type") in ("DATE", "TIMESTAMP")
    db = family(types[1]) == "temporal" or (hints.get(("r", b)) or {}).get("type") in ("DATE", "TIMESTAMP")
    na, nb = _norm(f"l.{qi(a)}", types[0], da or db), _norm(f"r.{qi(b)}", types[1], da or db)
    return (f"SELECT l.{qi(lk)} AS {qi('key_' + lk)}, l.{qi(a)} AS {qi(lt + '.' + a)}, r.{qi(b)} AS {qi(rt + '.' + b)}\n"
            f"FROM {fq(ls, lt)} l JOIN {fq(rs, rt)} r ON CAST(l.{qi(lk)} AS VARCHAR) = CAST(r.{qi(rk)} AS VARCHAR)\n"
            f"WHERE ({na}) IS DISTINCT FROM ({nb})\nLIMIT {int(limit)}")
