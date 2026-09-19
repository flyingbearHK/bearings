"""Discover likely FK → PK relationships using name similarity + value overlap."""
from __future__ import annotations

import re
from datetime import datetime

from rapidfuzz import fuzz

from .db import META, fq, has_meta, qi, user_tables
from .profiler import family

ID_SUFFIX = re.compile(r"(_?(id|key|code|no|num|nbr|number|cd|ref))$", re.I)


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _singular(s: str) -> str:
    return s[:-3] + "y" if s.endswith("ies") else s[:-1] if s.endswith("s") and not s.endswith("ss") else s


def name_score(from_col: str, to_table: str, to_col: str) -> float:
    fc, tt, tc = norm(from_col), norm(_singular(to_table.split("_")[-1])), norm(to_col)
    ttf = norm(_singular(to_table))
    if fc == tc and ID_SUFFIX.search(from_col):
        return 1.0
    # guest_id  →  guest.id / guests.guest_id / dim_guest.id
    if tc in ("id", "key", "code") and fc in (ttf + tc, tt + tc, ttf + "_" + tc):
        return 1.0
    if fc == tc:
        return 0.8
    base_f = ID_SUFFIX.sub("", from_col.lower())
    base_t = ID_SUFFIX.sub("", to_col.lower())
    if norm(base_f) and norm(base_f) in (tt, ttf) and ID_SUFFIX.search(to_col):
        return 0.9
    r = fuzz.ratio(fc, tc) / 100.0
    if ID_SUFFIX.search(from_col) and ID_SUFFIX.search(to_col) and norm(base_f) and norm(base_t):
        r = max(r, fuzz.ratio(norm(base_f), norm(base_t)) / 100.0 * 0.9)
    return round(r, 3)


class NoValues(RuntimeError):
    """A remote (metadata-only) column has no key fingerprint, so its values can't be compared."""


def _values(con, s, t, c, local: set | None = None) -> tuple[str, list, bool]:
    """SQL for the distinct values of a column as VARCHAR, from the table itself when it's local, else
    from its key fingerprint. Returns (sql, params, complete)."""
    if local is None:
        local = set(user_tables(con))
    if (s, t) in local:
        return f"SELECT DISTINCT CAST({qi(c)} AS VARCHAR) v FROM {fq(s, t)} WHERE {qi(c)} IS NOT NULL", [], True
    if has_meta(con, "key_fingerprint"):
        r = con.execute(f"SELECT complete FROM {META}.key_fingerprint WHERE schema_name=? AND table_name=? AND column_name=?",
                        [s, t, c]).fetchone()
        if r:
            return (f"SELECT DISTINCT v FROM {META}.key_values WHERE schema_name=? AND table_name=? AND column_name=?",
                    [s, t, c], bool(r[0]))
    raise NoValues(f"{s}.{t}.{c}")


def overlap(con, fs, ft, fc, ts, tt, tc, local: set | None = None) -> tuple[int, int]:
    """(distinct values in from-column, how many of them exist in to-column). Remote (metadata-only)
    columns are compared through their key fingerprints (`bearings profile` on a remote schema)."""
    a_sql, a_p, _ = _values(con, fs, ft, fc, local)
    b_sql, b_p, _ = _values(con, ts, tt, tc, local)
    q = f"""
      WITH a AS ({a_sql}), b AS ({b_sql})
      SELECT (SELECT count(*) FROM a), (SELECT count(*) FROM a SEMI JOIN b ON a.v = b.v)"""
    a, m = con.execute(q, a_p + b_p).fetchone()
    return int(a or 0), int(m or 0)


def _compatible(t1: str, t2: str) -> bool:
    f1, f2 = family(t1), family(t2)
    if "other" in (f1, f2) or "bool" in (f1, f2):
        return False
    return f1 == f2 or {f1, f2} == {"numeric", "string"}


def discover(con, min_overlap: float = 0.5, name_threshold: float = 0.75, deep: bool = False,
             max_pairs: int = 5000, echo=print, schemas: set[str] | None = None) -> list[dict]:
    """schemas: only consider tables in these schemas (both ends of a relationship)."""
    prof = con.execute(f"""SELECT schema_name, table_name, column_name, data_type, row_count, null_count, distinct_count, flags
                           FROM {META}.column_profile""").fetchall()
    if schemas:
        prof = [r for r in prof if r[0] in schemas]
    if not prof:
        echo("No profile found – run `bearings profile` first (relationships use key detection).")
        return []
    cols = [dict(zip(["s", "t", "c", "type", "rows", "nulls", "dist", "flags"], r)) for r in prof]
    # key-like targets: unique / near-unique, not tiny
    targets = [c for c in cols if c["dist"] and c["rows"] and (c["rows"] - c["nulls"]) > 0
               and c["dist"] / (c["rows"] - c["nulls"]) >= 0.98 and c["dist"] >= 2]
    candidates = []
    for f in cols:
        if not f["dist"] or '"constant"' in (f["flags"] or "") or '"all_null"' in (f["flags"] or ""):
            continue
        for t in targets:
            if (f["s"], f["t"]) == (t["s"], t["t"]):
                continue
            if not _compatible(f["type"], t["type"]) or f["dist"] > t["dist"] * 1.02:
                continue
            ns = name_score(f["c"], t["t"], t["c"])
            f_unique = '"candidate_pk"' in (f["flags"] or "") or '"unique_with_nulls"' in (f["flags"] or "")
            if f_unique and ns < 0.9:
                continue  # PK→PK only when names clearly agree (1:1 extension tables); avoids surrogate-range noise
            if ns >= name_threshold:
                candidates.append((ns, f, t, "name+overlap"))
            elif deep and family(f["type"]) == family(t["type"]) and ID_SUFFIX.search(f["c"] or ""):
                candidates.append((ns, f, t, "overlap"))
    candidates.sort(key=lambda x: -x[0])
    if len(candidates) > max_pairs:
        echo(f"  {len(candidates)} candidate pairs, checking top {max_pairs} (use --max-pairs)")
        candidates = candidates[:max_pairs]
    echo(f"  checking value overlap for {len(candidates)} candidate pairs…")
    found = []
    local = set(user_tables(con))
    no_values = 0
    for ns, f, t, method in candidates:
        try:
            a, m = overlap(con, f["s"], f["t"], f["c"], t["s"], t["t"], t["c"], local=local)
        except NoValues:
            no_values += 1
            continue
        except Exception:
            continue
        if not a:
            continue
        ov = m / a
        if ov >= min_overlap:
            found.append({
                "from_schema": f["s"], "from_table": f["t"], "from_column": f["c"],
                "to_schema": t["s"], "to_table": t["t"], "to_column": t["c"],
                "name_score": ns, "overlap_pct": round(100 * ov, 2), "from_distinct": a, "matched_distinct": m,
                "confidence": round(0.65 * ov + 0.35 * ns, 3), "method": method,
            })
    if no_values:
        echo(f"  {no_values} pair(s) skipped: a remote column has no key fingerprint (bearings profile -s <remote alias>)")
    # keep best target per from-column (plus any others within 0.05 of best)
    best: dict = {}
    for r in found:
        k = (r["from_schema"], r["from_table"], r["from_column"])
        best.setdefault(k, []).append(r)
    out = []
    for rs in best.values():
        rs.sort(key=lambda r: -r["confidence"])
        out += [r for r in rs if r["confidence"] >= rs[0]["confidence"] - 0.05]
    return out


def save(con, rels: list[dict], schemas: set[str] | None = None):
    """Replace discovered relationships (only those inside `schemas` when given)."""
    now = datetime.now()
    if schemas:
        ph = ", ".join("?" for _ in schemas)
        con.execute(f"DELETE FROM {META}.relationships WHERE from_schema IN ({ph}) AND to_schema IN ({ph})", [*schemas, *schemas])
    else:
        con.execute(f"DELETE FROM {META}.relationships")
    keys = ["from_schema", "from_table", "from_column", "to_schema", "to_table", "to_column",
            "name_score", "overlap_pct", "from_distinct", "matched_distinct", "confidence", "method"]
    con.executemany(f"INSERT INTO {META}.relationships VALUES ({', '.join('?' * 13)})",
                    [[r[k] for k in keys] + [now] for r in rels])
