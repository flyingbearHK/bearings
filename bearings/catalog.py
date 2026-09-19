"""Catalog (tables/columns/comments/profile badges/annotations) + name & value search."""
from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path

from rapidfuzz import fuzz

from .db import META, ann_connect, annotations_path, fq, qi, user_tables
from .profiler import family

_cache: dict = {"key": None, "data": None}


def norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def annotations(db_path: Path) -> dict:
    c = ann_connect(db_path)
    try:
        rows = c.execute("SELECT * FROM annotations").fetchall()
    finally:
        c.close()
    return {(r["schema_name"], r["table_name"], r["column_name"]): dict(r) for r in rows}


def build(con, db_path: Path) -> dict:
    key = (Path(db_path).stat().st_mtime if Path(db_path).exists() else 0,
           annotations_path(db_path).stat().st_mtime if annotations_path(db_path).exists() else 0)
    if _cache["key"] == key:
        return _cache["data"]
    cols = con.execute("""SELECT table_schema, table_name, column_name, ordinal_position, data_type
                          FROM information_schema.columns
                          WHERE table_schema NOT IN ('_meta','information_schema','pg_catalog') AND table_catalog = current_database()
                          ORDER BY 1,2,4""").fetchall()
    comments = {(s, t, c.lower()): cm for s, t, c, cm in con.execute(f"SELECT * FROM {META}.comments").fetchall()}
    prof = {(r[0], r[1], r[2]): {"null_pct": r[3], "distinct_count": r[4], "distinct_pct": r[5], "flags": json.loads(r[6] or "[]")}
            for r in con.execute(f"SELECT schema_name, table_name, column_name, null_pct, distinct_count, distinct_pct, flags FROM {META}.column_profile").fetchall()}
    tprof = {(r[0], r[1]): {"row_count": r[2], "candidate_keys": json.loads(r[3] or "[]"), "profiled_at": str(r[4])}
             for r in con.execute(f"SELECT schema_name, table_name, row_count, candidate_keys, profiled_at FROM {META}.table_profile").fetchall()}
    loads = {(r[0], r[1]): {"row_count": r[2], "source": r[3], "loaded_at": str(r[4])}
             for r in con.execute(f"""SELECT schema_name, table_name, arg_max(row_count, loaded_at), arg_max(source, loaded_at), max(loaded_at)
                                       FROM {META}.load_log GROUP BY 1,2""").fetchall()}
    ann = annotations(db_path)
    tables: dict = {}
    for s, t in user_tables(con):
        k = (s, t)
        tables[k] = {"schema": s, "table": t, "columns": [],
                     "row_count": (tprof.get(k) or loads.get(k) or {}).get("row_count"),
                     "profiled": k in tprof, "profiled_at": (tprof.get(k) or {}).get("profiled_at"),
                     "candidate_keys": (tprof.get(k) or {}).get("candidate_keys", []),
                     "source": (loads.get(k) or {}).get("source"), "loaded_at": (loads.get(k) or {}).get("loaded_at"),
                     "comment": comments.get((s, t, "")), "annotation": ann.get((s, t, ""))}
    for s, t, c, o, dt in cols:
        if (s, t) not in tables:
            continue
        tables[(s, t)]["columns"].append({
            "column": c, "ordinal": o, "type": dt, "comment": comments.get((s, t, c.lower())),
            **(prof.get((s, t, c)) or {}), "annotation": ann.get((s, t, c))})
    for tb in tables.values():
        if tb["row_count"] is None:
            try:
                tb["row_count"] = con.execute(f"SELECT count(*) FROM {fq(tb['schema'], tb['table'])}").fetchone()[0]
            except Exception:
                pass
    data = {"tables": tables}
    _cache.update(key=key, data=data)
    return data


def scoped(cat: dict, schemas: set[str] | None) -> dict:
    """Restrict a catalog to the given schemas (None/empty = everything)."""
    if not schemas:
        return cat
    return {**cat, "tables": {k: v for k, v in cat["tables"].items() if k[0] in schemas}}


def parse_schemas(v: str | None) -> set[str] | None:
    xs = {x.strip() for x in (v or "").split(",") if x.strip()}
    return xs or None


def score(q: str, text: str | None) -> float:
    if not text:
        return 0.0
    if any(ch in q for ch in "*?"):
        return 100.0 if fnmatch.fnmatch(text.lower(), q.lower()) else 0.0
    nq, nt = norm(q), norm(text)
    if not nq or not nt:
        return 0.0
    if nq == nt:
        return 100.0
    if nt.startswith(nq):
        return 95.0
    if nq in nt:
        return 90.0 - min(10, (len(nt) - len(nq)) / 4)
    toks = [norm(x) for x in re.split(r"\s+", q.strip()) if norm(x)]
    if len(toks) > 1 and all(tk in nt for tk in toks):
        return 86.0
    s = fuzz.ratio(nq, nt)
    if len(nq) >= 4:
        s = max(s, fuzz.partial_ratio(nq, nt) * 0.88)
    return round(s * 0.9, 1)


def score_text(q: str, text: str | None) -> float:
    """Free text (comments, annotations): phrase containment or best single word."""
    if not text or len(norm(q)) < 3:
        return 0.0
    if any(ch in q for ch in "*?"):
        return max((score(q, w) for w in re.split(r"[\s,;/|]+", text) if w), default=0.0)
    nq, nt = norm(q), norm(text)
    if nq in nt:
        return 85.0
    toks = [norm(x) for x in q.split() if norm(x)]
    if len(toks) > 1 and all(t in nt for t in toks):
        return 82.0
    return max((score(q, w) for w in re.split(r"[\s,;/|.()]+", text) if w), default=0.0) * 0.9


def _ann_text(a: dict | None) -> str:
    if not a:
        return ""
    return " ".join(x for x in (a.get("tags"), a.get("cdm_entity"), a.get("cdm_attribute"), a.get("notes")) if x)


def match_score(q: str, text: str | None, match: str) -> float:
    """match = exact | contains | fuzzy. Names are compared normalised (case, _ and spaces ignored),
    so exact `reservationid` finds reservation_id / ReservationId. Wildcards work in every mode."""
    if not text:
        return 0.0
    if any(ch in q for ch in "*?"):
        return 100.0 if fnmatch.fnmatch(text.lower(), q.lower()) else 0.0
    nq, nt = norm(q), norm(text)
    if not nq:
        return 0.0
    if match == "exact":
        return 100.0 if nq == nt else 0.0
    if match == "contains":
        return 100.0 if nq == nt else 95.0 if nt.startswith(nq) else (90.0 - min(10, (len(nt) - len(nq)) / 4)) if nq in nt else 0.0
    return score(q, text)


def text_score(q: str, text: str | None, match: str) -> float:
    if match == "exact":
        return 0.0  # exact mode matches names only
    if match == "contains":
        return 85.0 if text and len(norm(q)) >= 3 and norm(q) in norm(text) else 0.0
    return score_text(q, text)


def search(cat: dict, q: str, threshold: float = 72.0, limit: int = 300, match: str = "fuzzy",
           columns_only: bool = False) -> dict:
    q = q.strip()
    out = []
    any_cols = False
    for tb in cat["tables"].values():
        ts, tsrc = 0.0, None
        if not columns_only:
            ts = max(match_score(q, tb["table"], match), match_score(q, f"{tb['schema']}.{tb['table']}", match))
            tsrc = "table"
            cs = text_score(q, tb.get("comment"), match)
            if cs > ts:
                ts, tsrc = cs, "table comment"
            a = text_score(q, _ann_text(tb.get("annotation")), match)
            if a > ts:
                ts, tsrc = a, "table annotation"
        matched = []
        for c in tb["columns"]:
            s, src = match_score(q, c["column"], match), "column"
            if "." in q:
                s2 = match_score(q, f"{tb['table']}.{c['column']}", match)
                if s2 > s:
                    s, src = s2, "table.column"
            s3 = text_score(q, c.get("comment"), match)
            if s3 > s:
                s, src = s3, "comment"
            s4 = text_score(q, _ann_text(c.get("annotation")), match)
            if s4 > s:
                s, src = s4, "annotation"
            if s >= threshold:
                matched.append({**_col_summary(c), "score": s, "matched_by": src})
        if ts >= threshold or matched:
            matched.sort(key=lambda x: -x["score"])
            any_cols = any_cols or bool(matched)
            out.append({**_table_summary(tb), "score": max([ts] + [m["score"] for m in matched]),
                        "table_score": ts if ts >= threshold else 0, "table_matched_by": tsrc if ts >= threshold else None,
                        "matched_columns": matched})
    out.sort(key=lambda x: (-x["table_score"], -x["score"], x["table"]))
    return {"query": q, "mode": "name", "match": match, "has_column_matches": any_cols, "tables": out[:limit]}


def _table_summary(tb):
    return {k: tb.get(k) for k in ("schema", "table", "row_count", "profiled", "comment", "candidate_keys")} | {"column_count": len(tb["columns"])}


def _col_summary(c):
    return {k: c.get(k) for k in ("column", "ordinal", "type", "comment", "null_pct", "distinct_count", "distinct_pct", "flags")} | {
        "tags": (c.get("annotation") or {}).get("tags")}


def search_values(con, cat: dict, value: str, exact: bool = False, max_tables: int = 500) -> dict:
    """Find columns containing a value. One scan per table."""
    value = value.strip()
    num = None
    try:
        num = float(value.replace(",", ""))
    except ValueError:
        pass
    esc = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    out = []
    for tb in list(cat["tables"].values())[:max_tables]:
        tests = []
        for c in tb["columns"]:
            fam = family(c["type"])
            q = qi(c["column"])
            if fam == "string":
                cond = f"lower({q}) = lower(?)" if exact else f"{q} ILIKE ? ESCAPE '\\'"
                tests.append((c, cond, value if exact else f"%{esc}%"))
            elif fam == "numeric" and num is not None:
                tests.append((c, f"{q} = ?", num))
            elif fam == "temporal" and re.match(r"^\d{4}-\d{2}-\d{2}", value):
                tests.append((c, f"CAST({q} AS VARCHAR) LIKE ?", value + "%"))
        if not tests:
            continue
        sql = "SELECT " + ", ".join(f"count(*) FILTER (WHERE {cond})" for _, cond, _ in tests) + f" FROM {fq(tb['schema'], tb['table'])}"
        try:
            counts = con.execute(sql, [p for _, _, p in tests]).fetchone()
        except Exception:
            continue
        matched = []
        for (c, cond, p), n in zip(tests, counts):
            if n:
                ex = [r[0] for r in con.execute(
                    f"SELECT DISTINCT CAST({qi(c['column'])} AS VARCHAR) FROM {fq(tb['schema'], tb['table'])} WHERE {cond} LIMIT 3", [p]).fetchall()]
                matched.append({**_col_summary(c), "score": 100, "matched_by": "value", "hits": n, "examples": ex})
        if matched:
            matched.sort(key=lambda x: -x["hits"])
            out.append({**_table_summary(tb), "score": 100, "table_score": 0, "table_matched_by": None,
                        "matched_columns": matched, "hits": sum(m["hits"] for m in matched)})
    out.sort(key=lambda x: -x["hits"])
    return {"query": value, "mode": "value", "has_column_matches": bool(out), "tables": out}
