"""Modelling insights: what a data modeller asks after the column profile.

- grain (F3): the smallest set of columns that makes a row unique ("one row per CustomerId + Channel")
- time coverage (F4): per date column – first/last month, rows per month, gaps, future rows, sentinel dates
- dependencies (F5): X → Y (Y is determined by X), grouped into candidate entities, hierarchies and
  code ↔ description pairs; dependencies that hold for ≥ 98 % of rows are kept with their exception count

Everything is SQL over the local table (or its cached copy). Results are stored in _meta.table_profile (grain),
_meta.time_profile and _meta.dependencies; candidate entities are derived from the stored dependencies when they
are read, so they follow annotations and dismissals. Needs the column profile (`bearings profile`) first.
"""
from __future__ import annotations

import itertools
import json
import re
import time
from datetime import date, datetime

from .db import META, fq, has_meta, has_meta_column, qi, user_tables
from . import codes
from .profiler import DATEISH_NAME, KEYISH_NAME, PLACEHOLDERS, _sql_list, family, load_profile

DEFAULT_SAMPLE = 1_000_000      # rows scanned per table; bigger tables are sampled (reservoir, fixed seed)
FD_MIN_STRENGTH = 0.98          # share of rows that must agree with their group's majority value
GRAIN_MAX_COLS = 8              # candidate columns for the grain search (pairs, then triples)
NEAR_GRAIN = 0.999              # report a "grain with duplicates" when no combination is fully unique
MAX_DETERMINANTS, MAX_DEPENDENTS = 30, 40
KINDS = ("grain", "time", "deps", "codes", "optional")
COND_MAX_VALUES = 20            # a column that explains when another is filled has at most this many values
GROUP_SIMILARITY = 0.95         # columns filled on (almost) the same rows form an optional group
SAMPLE_TABLE = "__bearings_insights_sample"

MEASURE_TYPE = re.compile(r"^(FLOAT|DOUBLE|REAL|DECIMAL|NUMERIC)", re.I)
PRIMARY_DATE = ["business_date", "posting", "arrival", "transaction", "txn", "order", "booking", "stay", "sale",
                "invoice", "event", "created", "date"]


class NoProfile(RuntimeError):
    pass


# ------------------------------------------------------------------ helpers
def _col_info(p: dict) -> dict:
    rows = p.get("row_count") or 0
    nn = rows - (p.get("null_count") or 0)
    top = (p.get("top_values") or [{}])[0].get("n") if p.get("top_values") else None
    d = p.get("distinct_count") or 0
    return {"c": p["column_name"], "type": p["data_type"], "fam": family(p["data_type"]), "rows": rows, "nn": nn, "d": d,
            "flags": set(p.get("flags") or []), "avg_len": p.get("avg_len"), "ordinal": p.get("ordinal") or 0,
            "top_share": (top / nn) if top and nn else (1.0 / d if d else 1.0), "hint": p.get("type_hint")}


def _keyish(name: str) -> bool:
    return bool(KEYISH_NAME.search(name))


def _is_measure(c: dict) -> bool:
    if c["fam"] == "numeric" and MEASURE_TYPE.match(c["type"]):
        return True
    return bool(c["nn"]) and c["d"] / c["nn"] > 0.5 and not _keyish(c["c"]) and c["fam"] != "temporal"


def _long_text(c: dict) -> bool:
    return c["fam"] == "string" and (c["avg_len"] or 0) > 60


NAME_SUFFIX = re.compile(r"(_?(id|key|code|no|num|nbr|number|cd|ref|name|nm|desc|description|label))$", re.I)


def entity_name(col: str) -> str:
    """property_code → Property, room_type_id → Room type, CustomerId → Customer, region_name → Region."""
    base = NAME_SUFFIX.sub("", col) or col
    base = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", base).replace("_", " ").strip()
    return (base[:1].upper() + base[1:].lower()) if base else col


# ------------------------------------------------------------------ F3 grain
def find_grain(con, src: str, n: int, cols: list[dict], full_src: str | None = None) -> dict:
    """Smallest unique column combination. Single-column keys come from the profile; otherwise pairs, then triples of
    up to GRAIN_MAX_COLS candidates are tested, skipping combinations that can't be unique (product of distinct
    counts below the row count) and supersets of combinations already found."""
    keys = [c["c"] for c in cols if "candidate_pk" in c["flags"]]
    if keys:
        return {"combos": [[k] for k in keys], "dup_rows": 0, "near": False, "tested": 0}
    cand = [c for c in cols if c["nn"] == c["rows"] and c["d"] > 1 and c["fam"] != "other" and "constant" not in c["flags"]
            and not (c["fam"] == "numeric" and MEASURE_TYPE.match(c["type"])) and not _long_text(c)]
    cand.sort(key=lambda c: (not (_keyish(c["c"]) or DATEISH_NAME.search(c["c"]) or re.search(r"type|channel|kind|seq|line", c["c"], re.I)), -c["d"]))
    cand = cand[:GRAIN_MAX_COLS]
    found: list[list[str]] = []
    best = (0.0, None, 0)
    tested = 0
    for k in (2, 3):
        for combo in itertools.combinations(cand, k):
            names = [c["c"] for c in combo]
            if any(set(f) <= set(names) for f in found):
                continue
            prod = 1
            for c in combo:
                prod *= max(c["d"], 1)
            if prod < n:
                continue
            tested += 1
            d = con.execute(f"SELECT count(*) FROM (SELECT DISTINCT {', '.join(qi(x) for x in names)} FROM {src})").fetchone()[0]
            if d >= n:
                found.append(names)
            elif d / n > best[0]:
                best = (d / n, names, n - d)
            if len(found) >= 3:
                break
        if found:
            break
    dup_rows, near = 0, False
    if not found and best[1] and best[0] >= NEAR_GRAIN:
        found, dup_rows, near = [best[1]], best[2], True
    if found and full_src and full_src != src:  # found on a sample: confirm on the whole table, keep what holds
        checked = []
        for combo in found:
            tot, d = con.execute(f"SELECT count(*), (SELECT count(*) FROM (SELECT DISTINCT {', '.join(qi(x) for x in combo)} "
                                 f"FROM {full_src})) FROM {full_src}").fetchone()
            checked.append((tot - d, combo))
        ok = [c for dups, c in checked if dups == 0]
        if ok:
            found, dup_rows = ok, 0
        else:
            checked.sort(key=lambda x: x[0])
            dup_rows, found, near = checked[0][0], [checked[0][1]], True
    return {"combos": found, "dup_rows": dup_rows, "near": near, "tested": tested}


# ------------------------------------------------------------------ F4 time coverage
def _date_expr(c: dict) -> str | None:
    q = qi(c["c"])
    if c["fam"] == "temporal":
        return f"CAST({q} AS TIMESTAMP)"
    h = c.get("hint") or {}
    if c["fam"] == "string" and h.get("type") in ("DATE", "TIMESTAMP"):
        parts = [f"TRY_STRPTIME(trim({q}), '{f}')" for f in (h.get("formats") or {})]
        return f"coalesce({', '.join(parts + [f'TRY_CAST(trim({q}) AS TIMESTAMP)'])})"
    return None


def time_coverage(con, src: str, cols: list[dict]) -> list[dict]:
    out = []
    for c in cols:
        expr = _date_expr(c)
        if not expr or not c["nn"]:
            continue
        sentinel, dated, future, series = con.execute(f"""
            WITH d AS (SELECT {expr} AS d FROM {src} WHERE {qi(c['c'])} IS NOT NULL),
                 v AS (SELECT d FROM d WHERE d IS NOT NULL AND year(d) > 1900 AND year(d) < 9999),
                 m AS (SELECT date_trunc('month', d)::DATE mo, count(*) n FROM v GROUP BY 1)
            SELECT (SELECT count(*) FROM d WHERE d IS NOT NULL AND (year(d) <= 1900 OR year(d) >= 9999)),
                   (SELECT count(*) FROM v),
                   (SELECT count(*) FROM v WHERE CAST(d AS DATE) > current_date),
                   (SELECT list([strftime(mo, '%Y-%m'), CAST(n AS VARCHAR)] ORDER BY mo) FROM m)""").fetchone()
        if not dated:
            continue
        pts = [(m, int(n)) for m, n in series]
        first, last = date.fromisoformat(pts[0][0] + "-01"), date.fromisoformat(pts[-1][0] + "-01")
        span = (last.year - first.year) * 12 + last.month - first.month + 1
        counts = sorted(n for _, n in pts)
        median = counts[len(counts) // 2]
        if len(pts) <= 2 and dated >= 100 and c["type"].upper().startswith("TIMESTAMP"):
            kind = "stamp"          # load / change timestamp, not a business date
        elif c["d"] >= 24 and median >= 10:
            kind = "event"
        else:
            kind = "attribute"
        if len(pts) > 240:          # long spans (dates of birth, …): yearly points for the sparkline
            yearly: dict = {}
            for m, n in pts:
                yearly[m[:4]] = yearly.get(m[:4], 0) + n
            series_out = {"grain": "year", "points": list(yearly.items())}
        else:
            series_out = {"grain": "month", "points": pts}
        out.append({"column_name": c["c"], "parsed_from_text": c["fam"] == "string", "first_month": first, "last_month": last,
                    "months_present": len(pts), "empty_months": span - len(pts), "future_rows": int(future),
                    "sentinel_rows": int(sentinel), "dated_rows": int(dated), "kind": kind, "series": series_out})
    events = [x for x in out if x["kind"] == "event"]
    if events:
        def score(x):
            name = x["column_name"].lower()
            hit = next((len(PRIMARY_DATE) - i for i, k in enumerate(PRIMARY_DATE) if k in name), 0)
            return (hit, x["months_present"], x["dated_rows"])
        max(events, key=score)["is_primary"] = True
    for x in out:
        x.setdefault("is_primary", False)
    return out


# ------------------------------------------------------------------ F5 dependencies
def dependencies(con, src: str, cols: list[dict], min_strength: float = FD_MIN_STRENGTH) -> list[dict]:
    """X → Y with row-based strength: the share of rows whose Y equals the most common Y for their X. One
    GROUPING SETS query per determinant scores all its candidate dependents."""
    usable = [c for c in cols if c["fam"] != "other" and not {"all_null", "constant"} & c["flags"] and not _long_text(c)]
    dets = [c for c in usable if 2 <= c["d"] <= c["nn"] / 2 and c["fam"] not in ("temporal", "bool") and not _is_measure(c)]
    dets.sort(key=lambda c: (not _keyish(c["c"]), -c["d"]))
    out = []
    for x in dets[:MAX_DETERMINANTS]:
        ys = [y for y in usable if y is not x and y["d"] > 1 and not _is_measure(y) and y["top_share"] < 0.95
              and y["d"] <= max(2 * x["d"], x["d"] + 20)]
        ys.sort(key=lambda y: (not _keyish(y["c"]), y["d"]))
        ys = ys[:MAX_DEPENDENTS]
        if not ys:
            continue
        xq = qi(x["c"])
        sets = ", ".join(f"({xq}, {qi(y['c'])})" for y in ys)
        grp = ", ".join(qi(y["c"]) for y in ys)
        rows = con.execute(f"""
            WITH g AS (SELECT {xq}, {grp}, count(*) n, grouping({grp}) gid FROM {src} WHERE {xq} IS NOT NULL
                       GROUP BY GROUPING SETS ({sets})),
                 m AS (SELECT gid, {xq}, max(n) top, sum(n) tot FROM g GROUP BY gid, {xq})
            SELECT gid, sum(top), sum(tot) FROM m GROUP BY gid""").fetchall()
        k = len(ys)
        for gid, top, tot in rows:
            present = [i for i in range(k) if not (int(gid) >> (k - 1 - i)) & 1]
            if len(present) != 1 or not tot:
                continue
            y = ys[present[0]]
            strength = float(top) / float(tot)
            if strength >= min_strength:
                out.append({"determinant": x["c"], "dependent": y["c"], "strength": round(strength, 5),
                            "exceptions": int(tot - top), "rows_checked": int(tot), "determinant_distinct": x["d"],
                            "kind": "exact" if tot == top else "approx"})
    return out


def structure(edges: list[dict], cols: dict[str, dict] | None = None, rels: list[dict] | None = None,
              schema: str = "", table: str = "", cdm: dict[str, str] | None = None, dismissed: set[str] | None = None) -> dict:
    """Stored dependencies → candidate entities, hierarchies, dirty dependencies and model notes.

    - X → Y and Y → X: one attribute with several spellings (code = description), merged into one class
    - transitive reduction on the classes, so hierarchies read as chains
    - a class that determines others, or has several spellings, is a candidate entity
    """
    cols = cols or {}
    dismissed = dismissed or set()
    edges = [e for e in edges if f"{e['determinant']}->{e['dependent']}" not in dismissed]
    found = {(e["determinant"], e["dependent"]): e for e in edges}
    names = sorted({a for a, _ in found} | {b for _, b in found})
    parent = {n: n for n in names}

    def root(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a
    for a, b in found:
        if (b, a) in found and root(a) != root(b):
            parent[root(b)] = root(a)
    classes: dict[str, list[str]] = {}
    for n in names:
        classes.setdefault(root(n), []).append(n)

    def order(members):
        return sorted(members, key=lambda m: (not _keyish(m), (cols.get(m) or {}).get("ordinal", 0)))
    classes = {r: order(m) for r, m in classes.items()}
    cid = {r: m[0] for r, m in classes.items()}        # a class is named after its key-like member
    by_member = {m: cid[r] for r, ms in classes.items() for m in ms}
    members = {cid[r]: ms for r, ms in classes.items()}

    cedges: dict[tuple[str, str], dict] = {}
    for (a, b), e in found.items():
        ca, cb = by_member[a], by_member[b]
        if ca == cb:
            continue
        cur = cedges.get((ca, cb))
        if not cur or e["strength"] < cur["strength"]:
            cedges[(ca, cb)] = e
    # a dismissed dependency hides the whole link between the two classes (every spelling of it)
    gone = {(by_member.get(a), by_member.get(b)) for a, b in (x.split("->", 1) for x in dismissed if "->" in x)}
    cedges = {k: e for k, e in cedges.items() if k not in gone}
    nodes = set(members)
    reduced = {(a, c): e for (a, c), e in cedges.items()
               if not any((a, b) in cedges and (b, c) in cedges for b in nodes if b not in (a, c))}

    entities = []
    for k, ms in members.items():
        outs = [(c, e) for (a, c), e in reduced.items() if a == k]
        if not outs and len(ms) < 2:
            continue
        key = ms[0]
        name = (cdm or {}).get(key) or entity_name(key)
        entities.append({
            "id": k, "name": name, "suggested": not (cdm or {}).get(key), "columns": ms,
            "determines": [{"id": c, "columns": members[c], "strength": e["strength"], "exceptions": e["exceptions"],
                            "kind": e["kind"], "is_entity": any(a == c for a, _ in reduced) or len(members[c]) > 1}
                           for c, e in sorted(outs, key=lambda x: -(cols.get(x[0]) or {}).get("d", 0))],
            "distinct": (cols.get(key) or {}).get("d"),
        })
    entities.sort(key=lambda x: (-len(x["determines"]) - len(x["columns"]), -(x["distinct"] or 0)))
    seen: set[str] = set()
    for e in entities:  # two classes can suggest the same name (room_type_id / room_type_code): spell the later one out
        if e["name"] in seen and e["suggested"]:
            e["name"] = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", e["id"]).replace("_", " ").capitalize()
        seen.add(e["name"])
    ename = {e["id"]: e["name"] for e in entities}
    for e in entities:
        for d in e["determines"]:
            d["name"] = ename.get(d["id"]) or (cdm or {}).get(d["id"]) or entity_name(d["id"])

    # hierarchies: maximal paths of ≥ 3 classes in the reduced graph
    succ: dict[str, list[str]] = {}
    for a, c in reduced:
        succ.setdefault(a, []).append(c)
    has_pred = {c for _, c in reduced}
    paths = []

    def walk(path):
        nxt = [c for c in succ.get(path[-1], []) if c not in path]
        if not nxt:
            if len(path) >= 3:
                paths.append(path)
            return
        for c in nxt:
            walk(path + [c])
    for start in sorted(nodes - has_pred):
        walk([start])
    hierarchies = [{"levels": [{"id": p, "columns": members[p], "name": ename.get(p) or (cdm or {}).get(p) or entity_name(p)} for p in path]}
                   for path in paths[:20]]

    # dependencies that hold for most but not all rows: one per (determinant class, dependent), stated from the class key
    dirty, seen_d = [], set()
    for e in sorted(edges, key=lambda e: (e["determinant_distinct"] or 0, e["determinant"] != by_member[e["determinant"]], e["strength"])):
        k = e["dependent"]  # the closest determinant (fewest distinct values) explains it; the others follow from it
        if e["kind"] != "approx" or k in seen_d:
            continue
        seen_d.add(k)
        dirty.append(dict(e, sentence=f"{e['dependent']} depends on {e['determinant']} for {100 * e['strength']:.1f}% of rows "
                                      f"({e['exceptions']:,} exception rows)"))
    dirty.sort(key=lambda e: e["strength"])

    # notes from the discovered relationships of this table
    notes = []
    fks = {r["from_column"]: r for r in (rels or []) if (r["from_schema"], r["from_table"]) == (schema, table)}
    for (a, c), e in reduced.items():
        a_fk = next((m for m in members[a] if m in fks), None)
        c_fk = next((m for m in members[c] if m in fks), None)
        if a_fk and c_fk:
            notes.append({"kind": "redundant_fk", "columns": [a_fk, c_fk],
                          "sentence": f"{c_fk} can be derived through {a_fk} ({fks[a_fk]['to_table']} already implies "
                                      f"{fks[c_fk]['to_table']}) – a redundant foreign key"})
    redundant = {c for n in notes for c in n["columns"][1:]}
    for ent in entities:
        fk = next((m for m in ent["columns"] if m in fks), None)
        if not fk:
            continue
        r = fks[fk]
        target_cols = {re.sub(r"[^a-z0-9]", "", c.lower()) for c in (r.get("target_columns") or [])}
        copied = [m for d in ent["determines"] for m in d["columns"] if re.sub(r"[^a-z0-9]", "", m.lower()) in target_cols]
        copied += [m for m in ent["columns"][1:] if re.sub(r"[^a-z0-9]", "", m.lower()) in target_cols]
        copied = [m for m in copied if m not in redundant and m not in fks]
        if copied:
            notes.append({"kind": "denormalised", "columns": [fk] + copied,
                          "sentence": f"{', '.join(copied)} {'is a copy' if len(copied) == 1 else 'are copies'} of "
                                      f"{r['to_table']}'s attributes (through {fk}) – keep them on {r['to_table']}"})
    return {"entities": entities, "hierarchies": hierarchies, "dirty": dirty, "notes": notes,
            "dependency_count": len(edges)}


# ------------------------------------------------------------------ optional attributes: when is a column filled?
def filled_expr(column: str, dtype: str) -> str:
    """SQL that is true when the column has a real value (not null, blank or a placeholder)."""
    q, f = qi(column), family(dtype)
    if f == "string":
        return (f"({q} IS NOT NULL AND trim({q}) <> '' AND upper(trim({q})) NOT IN "
                f"({_sql_list(PLACEHOLDERS + (('0', '-1') if KEYISH_NAME.search(column) else ()))}))")
    if f == "temporal":
        return f"({q} IS NOT NULL AND year({q}) > 1900 AND year({q}) < 9999)"
    if f == "numeric" and KEYISH_NAME.search(column):
        return f"({q} IS NOT NULL AND CAST({q} AS DOUBLE) NOT IN (0, -1))"
    return f"({q} IS NOT NULL)"


def _optional_candidates(prof: dict) -> list[dict]:
    out = []
    for p in prof.values():
        empty = p.get("effective_null_pct") if p.get("effective_null_pct") is not None else p.get("null_pct")
        if empty is None or not 2 <= empty <= 98 or {"all_null", "constant"} & set(p.get("flags") or []):
            continue
        if family(p["data_type"]) == "other":
            continue
        out.append(p)
    return sorted(out, key=lambda p: p.get("ordinal") or 0)[:40]


def optional_attributes(con, src: str, prof: dict) -> tuple[list[dict], list[dict]]:
    """(conditional fill rules, optional groups).

    - rule: X is filled only when Y ∈ S – almost every filled X row (≥ 98 %) has Y in S, S is a minority of the
      rows, and within S X is usually filled. Y is a code list of ≤ 20 values.
    - group: columns filled on (almost) the same rows (Jaccard ≥ 0.95) – optional attributes of the same subtype.
    """
    cand = _optional_candidates(prof)
    if not cand:
        return [], []
    fx = {p["column_name"]: filled_expr(p["column_name"], p["data_type"]) for p in cand}
    names = list(fx)
    # --- groups: pairwise overlap of the filled rows
    groups = []
    if len(names) >= 2:
        pairs = [(a, b) for i, a in enumerate(names) for b in names[i + 1:]][:780]
        aggs = [f"count(*) FILTER (WHERE {fx[c]})" for c in names] + [f"count(*) FILTER (WHERE {fx[a]} AND {fx[b]})" for a, b in pairs]
        r = con.execute(f"SELECT count(*), {', '.join(aggs)} FROM {src}").fetchone()
        total, filled = r[0], dict(zip(names, r[1:1 + len(names)]))
        both = dict(zip(pairs, r[1 + len(names):]))
        parent = {c: c for c in names}

        def root(x):
            while parent[x] != x:
                x = parent[x]
            return x
        jac = {}
        for (a, b), n in both.items():
            den = filled[a] + filled[b] - n
            j = n / den if den else 0
            jac[(a, b)] = j
            if j >= GROUP_SIMILARITY and filled[a] and 0.02 * total <= filled[a] <= 0.98 * total:
                parent[root(b)] = root(a)
        cl: dict = {}
        for c in names:
            cl.setdefault(root(c), []).append(c)
        for ms in cl.values():
            if len(ms) < 2:
                continue
            sim = min(jac.get((a, b), jac.get((b, a), 1)) for i, a in enumerate(ms) for b in ms[i + 1:])
            groups.append({"columns": ms, "filled_rows": min(filled[c] for c in ms), "row_count": total, "similarity": round(sim, 4)})
    # --- conditional rules: one GROUP BY per explaining column
    explainers = sorted([p for p in prof.values() if codes.is_code(p) and (p.get("distinct_count") or 0) <= COND_MAX_VALUES],
                        key=lambda p: p.get("distinct_count") or 0)[:15]
    best: dict = {}
    for y in explainers:
        yc = y["column_name"]
        xs = [c for c in names if c != yc]
        if not xs:
            continue
        rows = con.execute(f"SELECT CAST({qi(yc)} AS VARCHAR), count(*), {', '.join(f'count(*) FILTER (WHERE {fx[c]})' for c in xs)} "
                           f"FROM {src} GROUP BY 1").fetchall()
        total = sum(r[1] for r in rows)
        for i, x in enumerate(xs):
            filled_all = sum(r[2 + i] for r in rows)
            if filled_all < 20 or not total:
                continue
            s_rows = [r for r in rows if r[1] and r[2 + i] / r[1] >= 0.5]
            if not s_rows or len(s_rows) == len(rows):
                continue
            rows_s, filled_s = sum(r[1] for r in s_rows), sum(r[2 + i] for r in s_rows)
            precision, coverage = filled_s / filled_all, filled_s / rows_s
            if precision < 0.98 or coverage < 0.3 or rows_s > 0.9 * total:
                continue
            score = precision * coverage - 0.01 * len(s_rows)
            if x not in best or score > best[x]["score"]:
                best[x] = {"column_name": x, "by_column": yc, "when_values": sorted(r[0] if r[0] is not None else None for r in s_rows),
                           "precision": round(precision, 4), "coverage": round(coverage, 4), "filled_rows": filled_all,
                           "rows_when": rows_s, "score": score}
    return list(best.values()), groups


def optional_view(con, schema: str, table: str) -> dict:
    """Stored rules and groups, with groups that share one rule labelled as a possible subtype."""
    if not has_meta(con, "conditional_fill"):
        return {"rules": [], "groups": []}
    cur = con.execute(f"SELECT * EXCLUDE (schema_name, table_name, found_at) FROM {META}.conditional_fill "
                      "WHERE schema_name=? AND table_name=? ORDER BY column_name", [schema, table])
    names = [d[0] for d in cur.description]
    rules = []
    for r in cur.fetchall():
        d = dict(zip(names, r))
        d["when_values"] = json.loads(d["when_values"] or "[]")
        vals = ", ".join("(empty)" if v is None else v for v in d["when_values"])
        d["sentence"] = (f"{d['column_name']} is filled only when {d['by_column']} = {vals}"
                         f" – in {d['coverage'] * 100:.0f}% of those rows")
        rules.append(d)
    groups = []
    for cols_, filled, total, sim in con.execute(
            f"SELECT columns, filled_rows, row_count, similarity FROM {META}.optional_groups WHERE schema_name=? AND table_name=?",
            [schema, table]).fetchall():
        cols = json.loads(cols_)
        rs = [r for r in rules if r["column_name"] in cols]
        same = len(rs) == len(cols) and len({(r["by_column"], tuple(map(str, r["when_values"]))) for r in rs}) == 1
        g = {"columns": cols, "filled_rows": filled, "row_count": total, "similarity": sim,
             "filled_pct": round(100 * filled / total, 1) if total else 0,
             "when": {"by_column": rs[0]["by_column"], "when_values": rs[0]["when_values"]} if same else None}
        g["sentence"] = (f"{', '.join(cols)} are filled together in {g['filled_pct']:g}% of rows"
                         + (f", only when {g['when']['by_column']} = {', '.join(str(v) for v in g['when']['when_values'])}"
                            " – a possible subtype" if same else " – optional attributes of the same kind of row"))
        groups.append(g)
    return {"rules": rules, "groups": groups}


# ------------------------------------------------------------------ run / save / read
def run(con, schema: str, table: str, sample_rows: int | None = DEFAULT_SAMPLE, only: set[str] | None = None) -> dict:
    """Compute and store insights for one local (or cached) table. `con` must be writable."""
    only = set(only or KINDS)
    tp, prof = load_profile(con, schema, table)
    if not tp or not prof:
        raise NoProfile(f"{schema}.{table} has no profile – run bearings profile -t {schema}.{table} first")
    cols = [_col_info(p) for p in prof.values()]
    full = fq(schema, table)
    n_full = con.execute(f"SELECT count(*) FROM {full}").fetchone()[0]
    src, n = full, n_full
    t0 = time.time()
    if sample_rows and n_full > sample_rows:
        con.execute(f"CREATE OR REPLACE TEMP TABLE {SAMPLE_TABLE} AS SELECT * FROM {full} USING SAMPLE {int(sample_rows)} ROWS (reservoir, 42)")
        src, n = f"temp.main.{SAMPLE_TABLE}", int(sample_rows)
    from .relationships import sampled_tables
    cache_sample = (schema, table) in sampled_tables(con)
    on_sample = src != full or cache_sample
    res: dict = {"schema": schema, "table": table, "rows": n_full, "scanned_rows": n, "on_sample": on_sample}
    try:
        if "grain" in only and n:
            res["grain"] = find_grain(con, src, n, cols, full_src=full)
        if "time" in only:
            res["time"] = time_coverage(con, src, cols)
        if "deps" in only and n:
            res["dependencies"] = dependencies(con, src, cols)
        if "codes" in only:
            res["codes"] = codes.capture(con, src, list(prof.values()))
        if "optional" in only and n:
            res["rules"], res["groups"] = optional_attributes(con, src, prof)
    finally:
        if src != full:
            con.execute(f"DROP TABLE IF EXISTS temp.main.{SAMPLE_TABLE}")
    res["seconds"] = round(time.time() - t0, 2)
    save(con, res)
    return res


def save(con, res: dict):
    now = datetime.now()
    s, t = res["schema"], res["table"]
    if "grain" in res:
        g = res["grain"]
        con.execute(f"UPDATE {META}.table_profile SET grain=?, grain_dup_rows=?, grain_on_sample=?, insights_at=? "
                    "WHERE schema_name=? AND table_name=?",
                    [json.dumps(g["combos"]), g["dup_rows"], res["on_sample"], now, s, t])
    else:
        con.execute(f"UPDATE {META}.table_profile SET insights_at=? WHERE schema_name=? AND table_name=?", [now, s, t])
    if "time" in res:
        con.execute(f"DELETE FROM {META}.time_profile WHERE schema_name=? AND table_name=?", [s, t])
        keys = ["column_name", "parsed_from_text", "first_month", "last_month", "months_present", "empty_months", "future_rows",
                "sentinel_rows", "dated_rows", "kind", "is_primary"]
        if res["time"]:
            con.executemany(f"INSERT INTO {META}.time_profile (schema_name, table_name, {', '.join(keys)}, series, on_sample, profiled_at) "
                            f"VALUES ({', '.join('?' * (len(keys) + 5))})",
                            [[s, t] + [x[k] for k in keys] + [json.dumps(x["series"]), res["on_sample"], now] for x in res["time"]])
    if "dependencies" in res:
        con.execute(f"DELETE FROM {META}.dependencies WHERE schema_name=? AND table_name=?", [s, t])
        keys = ["determinant", "dependent", "strength", "exceptions", "rows_checked", "determinant_distinct", "kind"]
        if res["dependencies"]:
            con.executemany(f"INSERT INTO {META}.dependencies (schema_name, table_name, {', '.join(keys)}, on_sample, found_at) "
                            f"VALUES ({', '.join('?' * (len(keys) + 4))})",
                            [[s, t] + [e[k] for k in keys] + [res["on_sample"], now] for e in res["dependencies"]])
    _save_more(con, res, now)


def _save_more(con, res: dict, now):
    s, t = res["schema"], res["table"]
    if "codes" in res and has_meta(con, "code_values"):
        con.execute(f"DELETE FROM {META}.code_values WHERE schema_name=? AND table_name=?", [s, t])
        rows = [[s, t, c, v, n, res["on_sample"]] for c, vals in res["codes"].items() for v, n in vals]
        if rows:
            con.executemany(f"INSERT INTO {META}.code_values VALUES (?,?,?,?,?,?)", rows)
    if "rules" in res and has_meta(con, "conditional_fill"):
        con.execute(f"DELETE FROM {META}.conditional_fill WHERE schema_name=? AND table_name=?", [s, t])
        con.execute(f"DELETE FROM {META}.optional_groups WHERE schema_name=? AND table_name=?", [s, t])
        if res["rules"]:
            con.executemany(f"INSERT INTO {META}.conditional_fill VALUES (?,?,?,?,?,?,?,?,?,?)",
                            [[s, t, r["column_name"], r["by_column"], json.dumps(r["when_values"]), r["precision"], r["coverage"],
                              r["filled_rows"], r["rows_when"], now] for r in res["rules"]])
        if res["groups"]:
            con.executemany(f"INSERT INTO {META}.optional_groups VALUES (?,?,?,?,?,?,?)",
                            [[s, t, json.dumps(g["columns"]), g["filled_rows"], g["row_count"], g["similarity"], now] for g in res["groups"]])


def available(con) -> bool:
    return has_meta(con, "dependencies") and has_meta_column(con, "table_profile", "grain")


def read(con, schema: str, table: str) -> dict:
    """Stored insights of a table: {grain, time, dependencies} (structure() turns dependencies into entities)."""
    if not available(con):
        return {"available": False, "grain": None, "time": [], "dependencies": []}
    tp, _ = load_profile(con, schema, table)
    time_cur = con.execute(f"SELECT * EXCLUDE (schema_name, table_name) FROM {META}.time_profile WHERE schema_name=? AND table_name=? "
                           "ORDER BY is_primary DESC, dated_rows DESC", [schema, table])
    tnames = [d[0] for d in time_cur.description]
    times = []
    for r in time_cur.fetchall():
        d = dict(zip(tnames, r))
        d["series"] = json.loads(d["series"] or "{}")
        times.append(d)
    dep_cur = con.execute(f"SELECT * EXCLUDE (schema_name, table_name) FROM {META}.dependencies WHERE schema_name=? AND table_name=?",
                          [schema, table])
    dnames = [d[0] for d in dep_cur.description]
    deps = [dict(zip(dnames, r)) for r in dep_cur.fetchall()]
    grain = None
    if tp and tp.get("grain") is not None:
        grain = {"combos": tp["grain"], "dup_rows": tp.get("grain_dup_rows") or 0, "on_sample": tp.get("grain_on_sample")}
    return {"available": True, "computed_at": (tp or {}).get("insights_at"), "grain": grain, "time": times, "dependencies": deps}


def exceptions_sql(schema: str, table: str, determinant: str, dependent: str, limit: int = 200) -> str:
    """Rows whose `dependent` isn't the most common value for their `determinant` (the dirty rows of a dependency)."""
    x, y, src = qi(determinant), qi(dependent), fq(schema, table)
    return (f"WITH g AS (SELECT {x} AS x, {y} AS y, count(*) AS n,\n"
            f"                  row_number() OVER (PARTITION BY {x} ORDER BY count(*) DESC, {y}) AS rk\n"
            f"           FROM {src} WHERE {x} IS NOT NULL GROUP BY 1, 2)\n"
            f"SELECT t.*, (SELECT y FROM g m WHERE m.x = t.{x} AND m.rk = 1) AS expected_{dependent}\n"
            f"FROM {src} t JOIN g ON g.x = t.{x} AND g.y IS NOT DISTINCT FROM t.{y}\n"
            f"WHERE g.rk > 1\nORDER BY t.{x}\nLIMIT {int(limit)}")


def targets(con, schemas: set[str] | None = None, tables: list[str] | None = None) -> list[tuple[str, str]]:
    """Local / cached tables that have a profile (optionally within schemas or a list of schema.table)."""
    have = set(con.execute(f"SELECT schema_name, table_name FROM {META}.table_profile").fetchall())
    out = [x for x in user_tables(con) if x in have]
    if schemas:
        out = [x for x in out if x[0] in schemas]
    if tables:
        want = {t.lower() for t in tables}
        out = [(s, t) for s, t in out if f"{s}.{t}".lower() in want or t.lower() in want]
    return out


def run_many(con, tabs: list[tuple[str, str]], sample_rows: int | None = DEFAULT_SAMPLE, only: set[str] | None = None,
             echo=lambda *_: None) -> tuple[list[dict], list[dict]]:
    done, errors = [], []
    for s, t in tabs:
        try:
            done.append(run(con, s, t, sample_rows=sample_rows, only=only))
        except Exception as e:  # noqa: BLE001 - one odd table shouldn't stop the rest
            errors.append({"table": f"{s}.{t}", "error": str(e).splitlines()[0] if str(e) else type(e).__name__})
            echo(f"  ✗ {s}.{t}: {errors[-1]['error']}")
            continue
        echo(summary_line(done[-1]))
    return done, errors


def summary_line(r: dict) -> str:
    g = r.get("grain") or {}
    grain = " + ".join(g["combos"][0]) if g.get("combos") else "—"
    if g.get("dup_rows"):
        grain += f" ({g['dup_rows']:,} dup rows)"
    prim = next((x for x in r.get("time", []) if x["is_primary"]), None)
    hist = f"{prim['column_name']} {prim['first_month']:%Y-%m}..{prim['last_month']:%Y-%m}" if prim else "—"
    deps = r.get("dependencies")
    return (f"  ✓ {r['schema']}.{r['table']:<32} grain: {grain:<34} history: {hist:<34} "
            f"{len(deps) if deps is not None else '-':>3} dependencies  {r['seconds']:.1f}s{'  (sample)' if r['on_sample'] else ''}")
