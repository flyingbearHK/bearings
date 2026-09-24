"""Standard column profiling into _meta.column_profile / _meta.table_profile."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from .db import META, fq, has_meta_column, qi

NUMERIC = re.compile(r"^(TINYINT|SMALLINT|INTEGER|BIGINT|HUGEINT|UTINYINT|USMALLINT|UINTEGER|UBIGINT|UHUGEINT|FLOAT|DOUBLE|REAL|DECIMAL.*|NUMERIC.*)$", re.I)
TEMPORAL = re.compile(r"^(DATE|TIMESTAMP.*|TIME.*)$", re.I)
STRING = re.compile(r"^(VARCHAR.*|TEXT|STRING|CHAR.*)$", re.I)

PII_NAME = re.compile(r"(e_?mail|phone|mobile|cell|fax|passport|birth|dob|address|addr_|street|postcode|postal|zip|first_?name|last_?name|family_?name|surname|given_?name|full_?name|national_?id|id_?card|ssn|credit_?card|card_?no|iban|ip_?addr)", re.I)
EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PHONE_RE = r"^\+?\(?[0-9][0-9 ()\-.]{6,}$"


# values that stand in for "no value" (compared upper-cased and trimmed; blanks are counted separately)
PLACEHOLDERS = ("N/A", "N.A.", "#N/A", "NULL", "(NULL)", "NONE", "NIL", "-", "--", "---", "?", ".", "UNKNOWN", "UNK",
                "TBD", "TBA", "NOT APPLICABLE", "NOT AVAILABLE", "MISSING", "(BLANK)", "0000-00-00", "1900-01-01",
                "01/01/1900", "9999-12-31", "31/12/9999")
KEYISH_NAME = re.compile(r"(_?(id|key|code|no|num|nbr|number|cd|ref))$", re.I)
DATEISH_NAME = re.compile(r"(date|_dt$|^dt_|_dt_|_on$|time|_ts$|^ts_|day|period|month|year)", re.I)
# text → date formats tried in this order (the first that parses wins, so each value counts once)
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y", "%Y/%m/%d", "%d-%b-%Y", "%d %b %Y", "%d-%m-%Y")
BOOL_WORDS = ("Y", "N", "YES", "NO", "TRUE", "FALSE", "T", "F")
HINT_SHARE = 0.95   # share of the (non-placeholder) values that must parse before a type is suggested


def _sql_list(vals) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in vals)


def family(dtype: str) -> str:
    d = dtype.strip()
    if NUMERIC.match(d):
        return "numeric"
    if TEMPORAL.match(d) and not d.upper().startswith("TIME ") and d.upper() != "TIME":
        return "temporal"
    if STRING.match(d):
        return "string"
    if d.upper() == "BOOLEAN":
        return "bool"
    return "other"


def _columns(con, src: str):
    return [(r[0], r[1]) for r in con.execute(f"DESCRIBE {src}").fetchall()]


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def profile_table(con, schema: str, table: str, columns: list[str] | None = None,
                  sample_rows: int | None = None, approx: bool = False, top_n: int = 10):
    """Return (table_profile dict, [column_profile dict]). Read-only: safe to call live."""
    src = fq(schema, table)
    total = con.execute(f"SELECT count(*) FROM {src}").fetchone()[0]
    sampled = None
    if sample_rows and total > sample_rows:
        src = f"(SELECT * FROM {src} USING SAMPLE {int(sample_rows)} ROWS (reservoir, 42))"
        sampled = int(sample_rows)
    n_rows = sampled or total
    cols = _columns(con, fq(schema, table))
    ordinals = {c: i + 1 for i, (c, _) in enumerate(cols)}
    if columns:
        wanted = {c.lower() for c in columns}
        cols = [(c, t) for c, t in cols if c.lower() in wanted]

    results = []
    dcount = "approx_count_distinct" if approx else "count(DISTINCT {})"
    for chunk in _chunks(cols, 25):
        exprs = []
        for i, (c, t) in enumerate(chunk):
            f = family(t)
            q = qi(c)
            v = q if f != "other" else f"CAST({q} AS VARCHAR)"
            dc = f"approx_count_distinct({v})" if approx else f"count(DISTINCT {v})"
            exprs += [f"count({q})", dc, f"CAST(min({v}) AS VARCHAR)", f"CAST(max({v}) AS VARCHAR)"]
            if f == "string":
                exprs += [f"count(*) FILTER (WHERE trim({q}) = '')", f"min(length({q}))", f"avg(length({q}))", f"max(length({q}))",
                          "NULL", "NULL", "NULL", "NULL", "NULL"]
            elif f == "numeric":
                # statistics in DOUBLE: DECIMAL arithmetic/interpolation can overflow the column's declared precision
                n = f"CAST({q} AS DOUBLE)"
                exprs += ["NULL", "NULL", "NULL", "NULL",
                          f"avg({n})", f"stddev_samp({n})",
                          f"CAST(quantile_cont({n}, 0.25) AS VARCHAR)", f"CAST(quantile_cont({n}, 0.5) AS VARCHAR)", f"CAST(quantile_cont({n}, 0.75) AS VARCHAR)"]
            elif f == "temporal":
                exprs += ["NULL", "NULL", "NULL", "NULL", "NULL", "NULL",
                          f"CAST(quantile_disc({q}, 0.25) AS VARCHAR)", f"CAST(quantile_disc({q}, 0.5) AS VARCHAR)", f"CAST(quantile_disc({q}, 0.75) AS VARCHAR)"]
            else:
                exprs += ["NULL"] * 9
        k = 13
        failed: dict[str, str] = {}
        try:
            row = con.execute(f"SELECT {', '.join(exprs)} FROM {src}").fetchone()
        except Exception:
            # one odd column shouldn't lose the whole table: retry column by column
            row = []
            for i, (c, t) in enumerate(chunk):
                try:
                    row += list(con.execute(f"SELECT {', '.join(exprs[i * k:(i + 1) * k])} FROM {src}").fetchone())
                except Exception as e:
                    failed[c] = str(e).splitlines()[0]
                    try:
                        nn_only = con.execute(f"SELECT count({qi(c)}) FROM {src}").fetchone()[0]
                    except Exception:
                        nn_only = None
                    row += [nn_only, 0] + [None] * (k - 2)
        for i, (c, t) in enumerate(chunk):
            r = row[i * k:(i + 1) * k]
            nn, dist = r[0] or 0, r[1] or 0
            nulls = n_rows - nn
            results.append({
                "schema_name": schema, "table_name": table, "column_name": c, "ordinal": ordinals[c],
                "data_type": t, "row_count": n_rows, "null_count": nulls,
                "null_pct": round(100.0 * nulls / n_rows, 2) if n_rows else 0.0,
                "blank_count": r[4], "distinct_count": dist,
                "distinct_pct": round(100.0 * dist / nn, 2) if nn else 0.0,
                "min_val": _trim(r[2]), "max_val": _trim(r[3]),
                "min_len": r[5], "avg_len": round(r[6], 2) if r[6] is not None else None, "max_len": r[7],
                "mean": r[8], "stddev": r[9], "p25": r[10], "p50": r[11], "p75": r[12],
                "errors": [failed[c]] if c in failed else [],
            })

    for p in results:
        c, t = p["column_name"], p["data_type"]
        f, q = family(t), qi(c)
        v = q if f in ("string", "numeric", "temporal", "bool") else f"CAST({q} AS VARCHAR)"
        nn = p["row_count"] - p["null_count"]
        unique = nn > 0 and p["distinct_count"] >= nn and not approx
        # top values (skip for fully unique columns: every value would have count 1)
        top, patterns, hist = [], [], []
        email_share = phone_share = 0.0
        errors = p.pop("errors", [])
        try:
            if nn and not unique:
                top = [{"v": _trim(x[0]), "n": x[1]} for x in con.execute(
                    f"SELECT CAST({v} AS VARCHAR), count(*) FROM {src} WHERE {q} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT {int(top_n)}").fetchall()]
        except Exception as e:
            errors.append(f"top values: {str(e).splitlines()[0]}")
        # character-shape patterns for strings
        try:
            if f == "string" and nn:
                patterns = [{"p": x[0], "n": x[1]} for x in con.execute(
                    f"""SELECT regexp_replace(regexp_replace(regexp_replace(left({q}, 40), '[A-Z]', 'A', 'g'), '[a-z]', 'a', 'g'), '[0-9]', '9', 'g') AS p,
                               count(*) FROM {src} WHERE {q} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 8""").fetchall()]
                em, ph = con.execute(
                    f"""SELECT avg(CASE WHEN regexp_matches({q}, '{EMAIL_RE}') THEN 1 ELSE 0 END),
                               avg(CASE WHEN regexp_matches({q}, '{PHONE_RE}') THEN 1 ELSE 0 END)
                        FROM (SELECT {q} FROM {src} WHERE {q} IS NOT NULL LIMIT 2000)""").fetchone()
                email_share, phone_share = em or 0, ph or 0
        except Exception as e:
            errors.append(f"patterns: {str(e).splitlines()[0]}")
        # histogram for numeric / temporal (bounds passed as DOUBLE parameters, never as DECIMAL literals)
        try:
            if f in ("numeric", "temporal") and p["distinct_count"] > 1:
                x = f"epoch({q})" if f == "temporal" else f"CAST({q} AS DOUBLE)"
                lo, hi = con.execute(f"SELECT min({x})::DOUBLE, max({x})::DOUBLE FROM {src}").fetchone()
                if lo is not None and hi is not None and hi > lo:
                    bins = 20
                    rows = con.execute(
                        f"""SELECT least(floor(({x} - $lo) / ($hi - $lo) * {bins}), {bins - 1})::INT b, count(*)
                            FROM {src} WHERE {q} IS NOT NULL GROUP BY 1 ORDER BY 1""", {"lo": float(lo), "hi": float(hi)}).fetchall()
                    counts = dict(rows)
                    w = (hi - lo) / bins
                    for b in range(bins):
                        a, z = lo + b * w, lo + (b + 1) * w
                        if f == "temporal":
                            a, z = _fmt_epoch(a, t), _fmt_epoch(z, t)
                        else:
                            a, z = round(a, 4), round(z, 4)
                        hist.append({"lo": a, "hi": z, "n": counts.get(b, 0)})
        except Exception as e:
            errors.append(f"histogram: {str(e).splitlines()[0]}")
            hist = []
        try:
            if f == "numeric" and nn and not KEYISH_NAME.search(c):
                p.update(outliers(con, src, c, p))
        except Exception as e:
            errors.append(f"outliers: {str(e).splitlines()[0]}")
        try:
            p.update(disguised_nulls(con, src, c, t, nn))
        except Exception as e:
            errors.append(f"placeholders / type hint: {str(e).splitlines()[0]}")
        empty = (p["null_count"] or 0) + (p.get("blank_count") or 0) + (p.get("placeholder_count") or 0)
        p["effective_null_pct"] = round(100.0 * empty / p["row_count"], 2) if p["row_count"] else 0.0
        p["errors"] = errors
        p.update(email_share=email_share, phone_share=phone_share, approx=approx, pattern_base=nn)
        flags = compute_flags(p, patterns)
        p.update(top_values=top, patterns=patterns, histogram=hist, flags=flags)

    tprof = {
        "schema_name": schema, "table_name": table, "row_count": total,
        "column_count": len(_columns(con, fq(schema, table))),
        "candidate_keys": [p["column_name"] for p in results if "candidate_pk" in p["flags"]],
        "sampled_rows": sampled,
        "errors": [f"{p['column_name']}: {e}" for p in results for e in p.get("errors", [])],
    }
    return tprof, results


def outliers(con, src: str, column: str, p: dict) -> dict:
    """Far-out values (Tukey fences at 3 × IQR) and negative values of a numeric column, with the most extreme examples."""
    out = {"outlier_count": 0, "outlier_low": None, "outlier_high": None, "outlier_values": [], "negative_count": 0}
    q = f"CAST({qi(column)} AS DOUBLE)"
    out["negative_count"] = con.execute(f"SELECT count(*) FROM {src} WHERE {q} < 0").fetchone()[0]
    try:
        q1, q3 = float(p.get("p25")), float(p.get("p75"))
    except (TypeError, ValueError):
        return out
    iqr = q3 - q1
    if iqr <= 0:
        return out
    lo, hi = q1 - OUTLIER_IQR * iqr, q3 + OUTLIER_IQR * iqr
    out.update(outlier_low=round(lo, 6), outlier_high=round(hi, 6))
    rows = con.execute(f"""SELECT v, count(*) FROM (SELECT {q} v FROM {src} WHERE {q} < $lo OR {q} > $hi)
                           GROUP BY 1 ORDER BY abs(v - $mid) DESC LIMIT 5""", {"lo": lo, "hi": hi, "mid": (q1 + q3) / 2}).fetchall()
    out["outlier_count"] = con.execute(f"SELECT count(*) FROM {src} WHERE {q} < $lo OR {q} > $hi", {"lo": lo, "hi": hi}).fetchone()[0]
    out["outlier_values"] = [{"v": v, "n": n} for v, n in rows]
    return out


def disguised_nulls(con, src: str, column: str, dtype: str, non_null: int) -> dict:
    """Placeholder values that mean "no value" (N/A, -, 1900-01-01, 0 / -1 in a key column…), and for text columns the
    type most values would parse as (with the date formats seen) plus how many values have leading zeros."""
    out = {"placeholder_count": 0, "placeholder_values": [], "type_hint": None, "leading_zero_count": 0}
    if not non_null:
        return out
    f, q = family(dtype), qi(column)
    if f == "string":
        cond = f"upper(trim({q})) IN ({_sql_list(PLACEHOLDERS + (('0', '-1') if KEYISH_NAME.search(column) else ()))})"
    elif f == "temporal":
        cond = f"(year({q}) <= 1900 OR year({q}) >= 9999)"
    elif f == "numeric" and KEYISH_NAME.search(column):
        cond = f"CAST({q} AS DOUBLE) IN (0, -1)"
    else:
        return out
    ph = con.execute(f"SELECT CAST({q} AS VARCHAR), count(*) FROM {src} WHERE {q} IS NOT NULL AND {cond} "
                     "GROUP BY 1 ORDER BY 2 DESC, 1").fetchall()
    out["placeholder_count"] = sum(n for _, n in ph)
    out["placeholder_values"] = [{"v": v, "n": n} for v, n in ph[:5]]
    if f != "string":
        return out
    v = f"trim({q})"
    ymd = (f"WHEN length({v}) = 8 AND TRY_STRPTIME({v}, '%Y%m%d') IS NOT NULL THEN 'date:%Y%m%d' "
           if DATEISH_NAME.search(column) else "")
    dates = " ".join(f"WHEN TRY_STRPTIME({v}, '{fmt}') IS NOT NULL THEN 'date:{fmt}'" for fmt in DATE_FORMATS)
    kinds = dict(con.execute(f"""
        SELECT k, count(*) FROM (
          SELECT CASE {ymd}
                   WHEN regexp_full_match({v}, '[+-]?[0-9]+') THEN 'int'
                   WHEN regexp_full_match({v}, '[+-]?([0-9]+[.][0-9]*|[.][0-9]+)') THEN 'decimal'
                   WHEN upper({v}) IN ({_sql_list(BOOL_WORDS)}) THEN 'bool'
                   {dates}
                   WHEN TRY_CAST({v} AS TIMESTAMP) IS NOT NULL THEN 'timestamp'
                   ELSE 'text' END AS k
          FROM {src} WHERE {q} IS NOT NULL AND {v} <> '' AND NOT ({cond})) GROUP BY 1""").fetchall())
    total = sum(kinds.values())
    out["leading_zero_count"] = con.execute(
        f"SELECT count(*) FROM {src} WHERE regexp_full_match(trim({q}), '0[0-9]+')").fetchone()[0] if kinds.get("int") else 0
    if not total:
        return out
    share = lambda *ks: sum(kinds.get(k, 0) for k in ks) / total
    date_ks = [k for k in kinds if k.startswith("date:")]
    hint = None
    if share("int") >= HINT_SHARE and not out["leading_zero_count"]:
        hint = {"type": "BIGINT", "share": share("int")}
    elif share("int", "decimal") >= HINT_SHARE and kinds.get("decimal") and not out["leading_zero_count"]:
        hint = {"type": "DECIMAL", "share": share("int", "decimal")}
    elif share("bool") >= HINT_SHARE and len(kinds) == 1:
        hint = {"type": "BOOLEAN", "share": share("bool")}
    elif date_ks and share(*date_ks) >= HINT_SHARE:
        hint = {"type": "DATE", "share": share(*date_ks)}
    elif (date_ks or kinds.get("timestamp")) and share("timestamp", *date_ks) >= HINT_SHARE:
        hint = {"type": "TIMESTAMP", "share": share("timestamp", *date_ks)}
    if hint:
        hint["share"] = round(hint["share"], 4)
        hint["checked"] = total
        if date_ks:
            n_dates = sum(kinds[k] for k in date_ks)
            hint["formats"] = {k[5:]: round(kinds[k] / n_dates, 4) for k in sorted(date_ks, key=lambda k: -kinds[k])}
        out["type_hint"] = hint
    return out


def compute_flags(p: dict, patterns: list[dict]) -> list[str]:
    """Profile flags from a column profile dict (also used after remote exact stats replace sample stats)."""
    c, t = p["column_name"], p["data_type"]
    f = family(t)
    nn = (p["row_count"] or 0) - (p["null_count"] or 0)
    unique = nn > 0 and (p["distinct_count"] or 0) >= nn and not p.get("approx")
    flags = []
    if nn == 0:
        flags.append("all_null")
    elif p["distinct_count"] == 1:
        flags.append("constant")
    keyish = f == "string" or (f == "numeric" and not re.match(r"^(FLOAT|DOUBLE|REAL)", t, re.I))
    if unique and p["null_count"] == 0 and keyish:
        flags.append("candidate_pk")
    elif unique and p["null_count"] == 0:
        flags.append("unique")
    elif unique:
        flags.append("unique_with_nulls")
    if nn > 0 and p["null_pct"] >= 50:
        flags.append("high_null")
    if (p.get("email_share") or 0) > 0.8:
        flags.append("pii_email")
    if (p.get("phone_share") or 0) > 0.8 and PII_NAME.search(c):
        flags.append("pii_phone")
    if PII_NAME.search(c) and not any(fl.startswith("pii_") for fl in flags):
        flags.append("pii_name_hint")
    if len(patterns) > 1 and nn and p["distinct_count"] > 1:
        shapes: dict = {}
        for pt in patterns:  # compare shapes ignoring run length: 'Aaaaa' ~ 'Aaa'
            k = re.sub(r"(A)A+|(a)a+|(9)9+", lambda m: m.group(1) or m.group(2) or m.group(3), pt["p"])
            shapes[k] = shapes.get(k, 0) + pt["n"]
        if max(shapes.values()) / (p.get("pattern_base") or nn) < 0.8:
            flags.append("mixed_format")
    if (p["blank_count"] or 0) > 0:
        flags.append("has_blanks")
    if (p.get("placeholder_count") or 0) > 0:
        flags.append("placeholders")
    if p.get("type_hint"):
        flags.append("type_hint")
    if (p.get("leading_zero_count") or 0) > 0:
        flags.append("leading_zeros")
    if (p.get("outlier_count") or 0) > 0:
        flags.append("outliers")
    if nn and 0 < (p.get("negative_count") or 0) <= 0.05 * nn:
        flags.append("negatives")   # a few negatives in a mostly positive column: refunds, reversals or errors
    if p.get("errors"):
        flags.append("profile_error")
    return flags


def _trim(v, n=200):
    if v is None:
        return None
    s = str(v)
    return s if len(s) <= n else s[:n] + "…"


def _fmt_epoch(e, dtype="TIMESTAMP"):
    try:
        d = datetime.fromtimestamp(e, timezone.utc)
        return d.strftime("%Y-%m-%d") if dtype.upper() == "DATE" else d.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(e)


COLS = ["schema_name", "table_name", "column_name", "ordinal", "data_type", "row_count", "null_count", "null_pct",
        "blank_count", "distinct_count", "distinct_pct", "min_val", "max_val", "mean", "stddev", "p25", "p50", "p75",
        "min_len", "avg_len", "max_len", "top_values", "patterns", "histogram", "flags", "profiled_at"]
# v0.4 columns (older databases opened read-only may not have them yet)
COLS_V4 = ["placeholder_count", "placeholder_values", "effective_null_pct", "type_hint", "leading_zero_count",
           "outlier_count", "outlier_low", "outlier_high", "outlier_values", "negative_count"]
JSON_COLS = ("top_values", "patterns", "histogram", "flags", "placeholder_values", "type_hint", "outlier_values")
OUTLIER_IQR = 3.0   # "far out": beyond Q1 − 3·IQR or Q3 + 3·IQR


def save(con, tprof: dict, cols: list[dict]):
    now = datetime.now()
    s, t = tprof["schema_name"], tprof["table_name"]
    con.execute(f"DELETE FROM {META}.table_profile WHERE schema_name=? AND table_name=?", [s, t])
    con.execute(f"INSERT INTO {META}.table_profile (schema_name, table_name, row_count, column_count, candidate_keys, sampled_rows, profiled_at) "
                "VALUES (?,?,?,?,?,?,?)",
                [s, t, tprof["row_count"], tprof["column_count"], json.dumps(tprof["candidate_keys"]), tprof["sampled_rows"], now])
    con.execute(f"DELETE FROM {META}.column_profile WHERE schema_name=? AND table_name=?", [s, t])
    names = COLS + COLS_V4
    rows = []
    for p in cols:
        d = dict(p, profiled_at=now)
        for k in JSON_COLS:
            if k in d:
                d[k] = json.dumps(d[k], default=str) if d[k] is not None else None
        rows.append([d.get(k) for k in names])
    con.executemany(f"INSERT INTO {META}.column_profile ({', '.join(names)}) VALUES ({', '.join('?' * len(names))})", rows)


def load_profile(con, schema: str, table: str):
    """Stored profile for a table → (table dict | None, {column_name: dict})."""
    stale = ", stale" if has_meta_column(con, "table_profile", "stale") else ", false"
    t = con.execute(f"SELECT row_count, column_count, candidate_keys, sampled_rows, profiled_at{stale} FROM {META}.table_profile WHERE schema_name=? AND table_name=?",
                    [schema, table]).fetchone()
    tp = None
    if t:
        tp = {"row_count": t[0], "column_count": t[1], "candidate_keys": json.loads(t[2] or "[]"),
              "sampled_rows": t[3], "profiled_at": str(t[4]), "stale": bool(t[5])}
        if has_meta_column(con, "table_profile", "grain"):
            g = con.execute(f"SELECT grain, grain_dup_rows, grain_on_sample, insights_at FROM {META}.table_profile "
                            "WHERE schema_name=? AND table_name=?", [schema, table]).fetchone()
            tp.update(grain=json.loads(g[0]) if g[0] else None, grain_dup_rows=g[1], grain_on_sample=bool(g[2]),
                      insights_at=str(g[3]) if g[3] else None)
    names = COLS + (COLS_V4 if has_meta_column(con, "column_profile", "outlier_count") else
                    COLS_V4[:5] if has_meta_column(con, "column_profile", "type_hint") else [])
    cur = con.execute(f"SELECT {', '.join(names)} FROM {META}.column_profile WHERE schema_name=? AND table_name=? ORDER BY ordinal", [schema, table])
    cols = {}
    for r in cur.fetchall():
        d = dict(zip(names, r))
        for k in ("top_values", "patterns", "histogram", "flags", "placeholder_values", "outlier_values"):
            d[k] = json.loads(d.get(k) or "[]")
        d["type_hint"] = json.loads(d["type_hint"]) if d.get("type_hint") else None
        d["profiled_at"] = str(d["profiled_at"])
        cols[d["column_name"]] = d
    return tp, cols
