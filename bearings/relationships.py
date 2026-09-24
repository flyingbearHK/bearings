"""Discover likely FK → PK relationships using name similarity + value overlap."""
from __future__ import annotations

import re
from datetime import datetime

from rapidfuzz import fuzz

from .db import META, fq, has_meta, has_meta_column, qi, user_tables
from .profiler import family

ID_SUFFIX = re.compile(r"(_?(id|key|code|no|num|nbr|number|cd|ref))$", re.I)
MEASURE = re.compile(r"^(FLOAT|DOUBLE|REAL|DECIMAL|NUMERIC)", re.I)


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


CARD_KEYS = ["cardinality", "child_avg", "child_max", "parent_no_child_pct", "fk_null_pct", "orphan_rows", "card_on_sample"]


def sampled_tables(con) -> set[tuple[str, str]]:
    """Local copies of remote tables that hold only a sample of the rows."""
    if not has_meta(con, "remote_cache"):
        return set()
    return {(a, t) for a, t in con.execute(f"SELECT alias, table_name FROM {META}.remote_cache WHERE NOT complete").fetchall()}


def cardinality(con, fs, ft, fc, ts, tt, tc, local: set | None = None, sampled: set | None = None) -> dict:
    """How a FK → key link behaves: 1:1 / 1:N / N:M, children per parent, parents without children, FK nulls and
    orphan rows. Needs the rows of both tables (local or cached); returns {} otherwise."""
    if local is None:
        local = set(user_tables(con))
    if (fs, ft) not in local or (ts, tt) not in local:
        return {}
    child, parent, fk, pk = fq(fs, ft), fq(ts, tt), qi(fc), qi(tc)
    parent_max, child_max, child_avg, no_child, fk_null, orphans = con.execute(f"""
        WITH ch AS (SELECT CAST({fk} AS VARCHAR) k, count(*) n FROM {child} WHERE {fk} IS NOT NULL GROUP BY 1),
             pa AS (SELECT CAST({pk} AS VARCHAR) k, count(*) n FROM {parent} WHERE {pk} IS NOT NULL GROUP BY 1)
        SELECT (SELECT max(n) FROM pa),
               (SELECT max(ch.n) FROM ch SEMI JOIN pa USING (k)),
               (SELECT avg(ch.n) FROM ch SEMI JOIN pa USING (k)),
               (SELECT 100.0 * count(*) FILTER (WHERE ch.k IS NULL) / nullif(count(*), 0) FROM pa LEFT JOIN ch USING (k)),
               (SELECT 100.0 * count(*) FILTER (WHERE {fk} IS NULL) / nullif(count(*), 0) FROM {child}),
               (SELECT coalesce(sum(ch.n), 0) FROM ch ANTI JOIN pa USING (k))""").fetchone()
    if (parent_max or 0) > 1:
        card = "N:M"
    elif (child_max or 0) <= 1:
        card = "1:1"
    else:
        card = "1:N"
    sampled = sampled if sampled is not None else sampled_tables(con)
    return {"cardinality": card, "child_avg": round(float(child_avg), 2) if child_avg is not None else None,
            "child_max": int(child_max or 0), "parent_no_child_pct": round(float(no_child or 0), 2),
            "fk_null_pct": round(float(fk_null or 0), 2), "orphan_rows": int(orphans or 0),
            "card_on_sample": (fs, ft) in sampled or (ts, tt) in sampled}


def describe(r: dict) -> str:
    """One plain-language sentence for a relationship with cardinality, e.g. for workshop screens and exports."""
    if not r.get("cardinality"):
        return ""
    ch, pa = r["from_table"], r["to_table"]
    if r["cardinality"] == "N:M":
        s = f"{pa}.{r['to_column']} is not unique, so this is many-to-many (or the wrong target column)"
    else:
        lo = "0" if (r.get("parent_no_child_pct") or 0) > 0 else "1"
        if r["cardinality"] == "1:1":
            s = f"each {pa} has {'at most one' if lo == '0' else 'exactly one'} {ch}"
        else:
            avg = f" ({r['child_avg']:g} on average)" if r.get("child_avg") is not None else ""
            s = f"each {pa} has {lo}–{r.get('child_max'):,} {ch}{avg}"
    opt = (f"{r['fk_null_pct']:g}% of {ch} rows have no {r['from_column']} (optional)" if (r.get("fk_null_pct") or 0) > 0
           else f"{r['from_column']} is always filled (mandatory)")
    orph = f"; {r['orphan_rows']:,} {ch} rows point to a {pa} that doesn't exist" if r.get("orphan_rows") else ""
    return f"{s[0].upper()}{s[1:]}; {opt}{orph}."


def _compatible(t1: str, t2: str) -> bool:
    f1, f2 = family(t1), family(t2)
    if "other" in (f1, f2) or "bool" in (f1, f2):
        return False
    return f1 == f2 or {f1, f2} == {"numeric", "string"}


def discover(con, min_overlap: float = 0.5, name_threshold: float = 0.75, deep: bool = False,
             max_pairs: int = 5000, echo=print, schemas: set[str] | None = None, touching: set[str] | None = None) -> list[dict]:
    """schemas: only consider tables in these schemas (both ends of a relationship).
    touching: only pairs with at least one end in these schemas (e.g. a schema that was just loaded)."""
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
        if MEASURE.match(f["type"]) and not ID_SUFFIX.search(f["c"]):
            continue  # amounts and rates aren't foreign keys, even when a copy of the table shares their values
        for t in targets:
            if (f["s"], f["t"]) == (t["s"], t["t"]):
                continue
            if touching and f["s"] not in touching and t["s"] not in touching:
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
    # cardinality and optionality (needs the rows of both tables: local or cached)
    sampled = sampled_tables(con)
    for r in out:
        try:
            r.update(cardinality(con, r["from_schema"], r["from_table"], r["from_column"],
                                 r["to_schema"], r["to_table"], r["to_column"], local=local, sampled=sampled))
        except Exception:
            pass
    return out


def save(con, rels: list[dict], schemas: set[str] | None = None, touching: set[str] | None = None):
    """Replace discovered relationships (only those inside `schemas`, or with an end in `touching`, when given)."""
    now = datetime.now()
    if touching:
        ph = ", ".join("?" for _ in touching)
        con.execute(f"DELETE FROM {META}.relationships WHERE from_schema IN ({ph}) OR to_schema IN ({ph})", [*touching, *touching])
    elif schemas:
        ph = ", ".join("?" for _ in schemas)
        con.execute(f"DELETE FROM {META}.relationships WHERE from_schema IN ({ph}) AND to_schema IN ({ph})", [*schemas, *schemas])
    else:
        con.execute(f"DELETE FROM {META}.relationships")
    keys = ["from_schema", "from_table", "from_column", "to_schema", "to_table", "to_column",
            "name_score", "overlap_pct", "from_distinct", "matched_distinct", "confidence", "method"]
    if has_meta_column(con, "relationships", "cardinality"):
        keys += CARD_KEYS
    con.executemany(f"INSERT INTO {META}.relationships ({', '.join(keys)}, found_at) VALUES ({', '.join('?' * (len(keys) + 1))})",
                    [[r.get(k) for k in keys] + [now] for r in rels])


def refresh_cardinality(con, schemas: set[str] | None = None) -> int:
    """Re-measure cardinality of stored relationships (e.g. after remote tables were cached locally)."""
    if not has_meta_column(con, "relationships", "cardinality"):
        return 0
    rows = con.execute(f"SELECT from_schema, from_table, from_column, to_schema, to_table, to_column FROM {META}.relationships").fetchall()
    local, sampled, n = set(user_tables(con)), sampled_tables(con), 0
    for fs, ft, fc, ts, tt, tc in rows:
        if schemas and not ({fs, ts} & schemas):
            continue
        try:
            c = cardinality(con, fs, ft, fc, ts, tt, tc, local=local, sampled=sampled)
        except Exception:
            continue
        if not c:
            continue
        con.execute(f"UPDATE {META}.relationships SET {', '.join(k + '=?' for k in CARD_KEYS)} "
                    "WHERE from_schema=? AND from_table=? AND from_column=? AND to_schema=? AND to_table=? AND to_column=?",
                    [c[k] for k in CARD_KEYS] + [fs, ft, fc, ts, tt, tc])
        n += 1
    return n


def with_targets(con, columns: dict[tuple[str, str], list[str]]) -> list[dict]:
    """Stored relationships, each with the column names of its target table (for "denormalised copy" notes)."""
    cur = con.execute(f"SELECT * EXCLUDE (found_at) FROM {META}.relationships")
    names = [d[0] for d in cur.description]
    out = []
    for r in cur.fetchall():
        d = dict(zip(names, r))
        d["target_columns"] = columns.get((d["to_schema"], d["to_table"]), [])
        out.append(d)
    return out
