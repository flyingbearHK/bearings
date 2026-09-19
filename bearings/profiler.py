"""Standard column profiling into _meta.column_profile / _meta.table_profile."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from .db import META, fq, qi

NUMERIC = re.compile(r"^(TINYINT|SMALLINT|INTEGER|BIGINT|HUGEINT|UTINYINT|USMALLINT|UINTEGER|UBIGINT|UHUGEINT|FLOAT|DOUBLE|REAL|DECIMAL.*|NUMERIC.*)$", re.I)
TEMPORAL = re.compile(r"^(DATE|TIMESTAMP.*|TIME.*)$", re.I)
STRING = re.compile(r"^(VARCHAR.*|TEXT|STRING|CHAR.*)$", re.I)

PII_NAME = re.compile(r"(e_?mail|phone|mobile|cell|fax|passport|birth|dob|address|addr_|street|postcode|postal|zip|first_?name|last_?name|family_?name|surname|given_?name|full_?name|national_?id|id_?card|ssn|credit_?card|card_?no|iban|ip_?addr)", re.I)
EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
PHONE_RE = r"^\+?\(?[0-9][0-9 ()\-.]{6,}$"


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
                exprs += ["NULL", "NULL", "NULL", "NULL",
                          f"avg({q})::DOUBLE", f"stddev_samp({q})::DOUBLE",
                          f"CAST(quantile_cont({q}, 0.25) AS VARCHAR)", f"CAST(quantile_cont({q}, 0.5) AS VARCHAR)", f"CAST(quantile_cont({q}, 0.75) AS VARCHAR)"]
            elif f == "temporal":
                exprs += ["NULL", "NULL", "NULL", "NULL", "NULL", "NULL",
                          f"CAST(quantile_disc({q}, 0.25) AS VARCHAR)", f"CAST(quantile_disc({q}, 0.5) AS VARCHAR)", f"CAST(quantile_disc({q}, 0.75) AS VARCHAR)"]
            else:
                exprs += ["NULL"] * 9
        row = con.execute(f"SELECT {', '.join(exprs)} FROM {src}").fetchone()
        k = 13
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
            })

    for p in results:
        c, t = p["column_name"], p["data_type"]
        f, q = family(t), qi(c)
        v = q if f in ("string", "numeric", "temporal", "bool") else f"CAST({q} AS VARCHAR)"
        nn = p["row_count"] - p["null_count"]
        unique = nn > 0 and p["distinct_count"] >= nn and not approx
        # top values (skip for fully unique columns: every value would have count 1)
        top = []
        if nn and not unique:
            top = [{"v": _trim(x[0]), "n": x[1]} for x in con.execute(
                f"SELECT CAST({v} AS VARCHAR), count(*) FROM {src} WHERE {q} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT {int(top_n)}").fetchall()]
        # character-shape patterns for strings
        patterns = []
        email_share = phone_share = 0.0
        if f == "string" and nn:
            patterns = [{"p": x[0], "n": x[1]} for x in con.execute(
                f"""SELECT regexp_replace(regexp_replace(regexp_replace(left({q}, 40), '[A-Z]', 'A', 'g'), '[a-z]', 'a', 'g'), '[0-9]', '9', 'g') AS p,
                           count(*) FROM {src} WHERE {q} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 8""").fetchall()]
            em, ph = con.execute(
                f"""SELECT avg(CASE WHEN regexp_matches({q}, '{EMAIL_RE}') THEN 1 ELSE 0 END),
                           avg(CASE WHEN regexp_matches({q}, '{PHONE_RE}') THEN 1 ELSE 0 END)
                    FROM (SELECT {q} FROM {src} WHERE {q} IS NOT NULL LIMIT 2000)""").fetchone()
            email_share, phone_share = em or 0, ph or 0
        # histogram for numeric / temporal
        hist = []
        if f in ("numeric", "temporal") and p["distinct_count"] > 1:
            x = f"epoch({q})" if f == "temporal" else f"CAST({q} AS DOUBLE)"
            lo, hi = con.execute(f"SELECT min({x}), max({x}) FROM {src}").fetchone()
            if lo is not None and hi is not None and hi > lo:
                bins = 20
                rows = con.execute(
                    f"""SELECT least(floor(({x} - {lo}) / ({hi} - {lo}) * {bins}), {bins - 1})::INT b, count(*)
                        FROM {src} WHERE {q} IS NOT NULL GROUP BY 1 ORDER BY 1""").fetchall()
                counts = dict(rows)
                w = (hi - lo) / bins
                for b in range(bins):
                    a, z = lo + b * w, lo + (b + 1) * w
                    if f == "temporal":
                        a, z = _fmt_epoch(a, t), _fmt_epoch(z, t)
                    else:
                        a, z = round(a, 4), round(z, 4)
                    hist.append({"lo": a, "hi": z, "n": counts.get(b, 0)})
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
        if email_share > 0.8:
            flags.append("pii_email")
        if phone_share > 0.8 and PII_NAME.search(c):
            flags.append("pii_phone")
        if PII_NAME.search(c) and not any(fl.startswith("pii_") for fl in flags):
            flags.append("pii_name_hint")
        if len(patterns) > 1 and nn and p["distinct_count"] > 1:
            shapes: dict = {}
            for pt in patterns:  # compare shapes ignoring run length: 'Aaaaa' ~ 'Aaa'
                k = re.sub(r"(A)A+|(a)a+|(9)9+", lambda m: m.group(1) or m.group(2) or m.group(3), pt["p"])
                shapes[k] = shapes.get(k, 0) + pt["n"]
            if max(shapes.values()) / nn < 0.8:
                flags.append("mixed_format")
        if (p["blank_count"] or 0) > 0:
            flags.append("has_blanks")
        p.update(top_values=top, patterns=patterns, histogram=hist, flags=flags)

    tprof = {
        "schema_name": schema, "table_name": table, "row_count": total,
        "column_count": len(_columns(con, fq(schema, table))),
        "candidate_keys": [p["column_name"] for p in results if "candidate_pk" in p["flags"]],
        "sampled_rows": sampled,
    }
    return tprof, results


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


def save(con, tprof: dict, cols: list[dict]):
    now = datetime.now()
    s, t = tprof["schema_name"], tprof["table_name"]
    con.execute(f"DELETE FROM {META}.table_profile WHERE schema_name=? AND table_name=?", [s, t])
    con.execute(f"INSERT INTO {META}.table_profile VALUES (?,?,?,?,?,?,?)",
                [s, t, tprof["row_count"], tprof["column_count"], json.dumps(tprof["candidate_keys"]), tprof["sampled_rows"], now])
    con.execute(f"DELETE FROM {META}.column_profile WHERE schema_name=? AND table_name=?", [s, t])
    rows = []
    for p in cols:
        d = dict(p, profiled_at=now)
        for k in ("top_values", "patterns", "histogram", "flags"):
            d[k] = json.dumps(d[k], default=str)
        rows.append([d.get(k) for k in COLS])
    con.executemany(f"INSERT INTO {META}.column_profile ({', '.join(COLS)}) VALUES ({', '.join('?' * len(COLS))})", rows)


def load_profile(con, schema: str, table: str):
    """Stored profile for a table → (table dict | None, {column_name: dict})."""
    t = con.execute(f"SELECT row_count, column_count, candidate_keys, sampled_rows, profiled_at FROM {META}.table_profile WHERE schema_name=? AND table_name=?",
                    [schema, table]).fetchone()
    tp = None
    if t:
        tp = {"row_count": t[0], "column_count": t[1], "candidate_keys": json.loads(t[2] or "[]"),
              "sampled_rows": t[3], "profiled_at": str(t[4])}
    cur = con.execute(f"SELECT {', '.join(COLS)} FROM {META}.column_profile WHERE schema_name=? AND table_name=? ORDER BY ordinal", [schema, table])
    cols = {}
    for r in cur.fetchall():
        d = dict(zip(COLS, r))
        for k in ("top_values", "patterns", "histogram", "flags"):
            d[k] = json.loads(d[k] or "[]")
        d["profiled_at"] = str(d["profiled_at"])
        cols[d["column_name"]] = d
    return tp, cols
