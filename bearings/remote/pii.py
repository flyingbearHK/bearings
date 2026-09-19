"""PII masking for the local cache of remote tables.

When a remote schema has masking on (`bearings cache --mask-pii`, asked by `bearings connect`), columns
that look like personal data are replaced in the local copy by a salted hash:

    guest@example.com  ->  pii_3f9a1c0b7d2e4f61@example.com   (e-mail keeps its domain)
    +852 9123 4567     ->  pii_8b0e5d2c9a7f1e34

The hash is deterministic within one Bearings database (per-database random salt in _meta.settings), so
the same person gets the same token in every table: joins, key checks, duplicates, overlap and
relationship discovery still work, and a lookup of a real value is hashed the same way before matching.
The stored profile (top values, min/max) and key fingerprints of those columns are masked too.
Live queries (⚡ Remote) show real values – they're displayed, not stored; workshop mode masks them on screen.

Which columns: values that look like e-mail addresses or phone numbers (profile flags), columns tagged PII,
and string columns whose name says they hold a personal value (e-mail, phone, passport, birth date, first /
last name, street, postcode…) – but not ids, codes, types, flags or dates about it (EmailAddressID,
PhoneType, NameCode…). Tag a column `no-pii` to keep it readable, or `pii` to force masking; see
`bearings pii -s <alias>` for what gets masked and why.
"""
from __future__ import annotations

import hashlib
import json
import re
import secrets

from ..db import META, fq, has_meta, qi

PREFIX = "pii_"


def salt(con) -> str:
    """Per-database secret; created on first use (needs a read-write connection)."""
    r = con.execute(f"SELECT value FROM {META}.settings WHERE key='pii_salt'").fetchone()
    if r:
        return r[0]
    s = secrets.token_hex(16)
    con.execute(f"INSERT INTO {META}.settings VALUES ('pii_salt', ?)", [s])
    return s


def mask_value(v, salt_: str, email: bool = False):
    if v is None:
        return None
    sv = str(v)
    if sv.startswith(PREFIX):  # already masked
        return sv
    h = PREFIX + hashlib.sha256((salt_ + sv).encode()).hexdigest()[:16]
    if email and "@" in sv:
        return h + "@" + sv.rsplit("@", 1)[1]
    return h


def mask_sql(col: str, salt_: str, email: bool = False) -> str:
    """DuckDB expression producing exactly mask_value()."""
    q = f"CAST({qi(col)} AS VARCHAR)"
    s = salt_.replace("'", "''")
    expr = f"'{PREFIX}' || left(sha256('{s}' || {q}), 16)"
    if email:
        expr += f" || CASE WHEN {q} LIKE '%@%' THEN '@' || split_part({q}, '@', -1) ELSE '' END"
    return f"CASE WHEN {qi(col)} IS NULL THEN NULL WHEN starts_with({q}, '{PREFIX}') THEN {q} ELSE {expr} END"


def enabled(con, alias: str) -> bool:
    from ..db import has_meta_column
    if not has_meta_column(con, "remote_sources", "mask_pii"):
        return False
    r = con.execute(f"SELECT mask_pii FROM {META}.remote_sources WHERE alias=?", [alias]).fetchone()
    return bool(r and r[0])


def set_enabled(con, alias: str, on: bool) -> None:
    con.execute(f"UPDATE {META}.remote_sources SET mask_pii=? WHERE alias=?", [bool(on), alias])


# names of columns that hold a personal *value* (not keys, types or flags about it)
PERSONAL = re.compile(
    r"(e_?mail|phone|mobile|cell_?(no|num|phone)|fax|passport|national_?id|id_?card|\bssn\b|social_?sec|"
    r"credit_?card|card_?holder|birth|\bdob\b|"
    r"first_?name|last_?name|middle_?name|given_?name|family_?name|sur_?name|full_?name|maiden|guest_?name|"
    r"street|address|addr_?\d|ip_?addr)", re.I)
# identifier numbers: personal values even though their names end in id / number
IDENTIFIER = re.compile(r"(passport_?(no|num|number)?$|tax_?(id|identifier|no|number)|national_?id|id_?card|migration_?card|"
                        r"card_?(no|num|number)$)", re.I)
# ...unless the name says it's structural: an id, a key, a type, a flag, a setting, a date about the row…
STRUCTURAL = re.compile(
    r"(id|key|type|typ|status|flag|ind|indicator|seq|sequence|count|cnt|code|cd|version|pref|preference|optin|consent|"
    r"verified|valid|primary|format|usage|category|class|source|method|level|order|rank|check|checked|required|yn|"
    r"extension|ext|body|subject|template|message|folio|policy|"
    r"insert(ed)?(date|dt|ts|time)?|update(d)?(date|dt|ts|time)?|create(d)?(date|dt|ts|time)?|modif\w*)$", re.I)
# ...or about a business, not a person: websites, headquarters, banks, merchants, masking settings
BUSINESS_COL = re.compile(r"(web_?site|url|\bhq|_hq|hq_|bank|merchant|dsn|dns|access_?number|mask|optin|opt_in)", re.I)
# tables that describe organisations (hotels, companies, agencies, rooms…) rather than people;
# an optional vendor prefix such as x5_ or dim_ is ignored
BUSINESS_TABLE = re.compile(r"^([a-z]\d_?|dim_?|ref_?)?(propert(y|ies)|organi[sz]ation|org|travel_?agency|agency|company|companies|vendor|"
                            r"supplier|merchant|bank|hotel|room|roomtype|transaction_?code|rate_?plan|promotion|outlet)s?$", re.I)


def _reason(col: str, dtype: str, flags: list[str], tags: str, table: str = "") -> str | None:
    """Why this column is masked (None = not masked). Tags always win; then business tables/columns are left
    alone; then content (values that look like e-mail / phone) and names of personal values."""
    from .profile import spark_family
    if re.search(r"\bno[-_ ]?pii\b", tags, re.I):
        return None
    if re.search(r"\bpii\b", tags, re.I):
        return "tagged PII"
    if table and BUSINESS_TABLE.search(table):
        return None      # a hotel's / company's own phone, e-mail, address – tag a column pii to mask it anyway
    if BUSINESS_COL.search(col):
        return None
    if "pii_email" in flags:
        return "values look like e-mail addresses"
    if "pii_phone" in flags:
        return "values look like phone numbers"
    fam = spark_family(dtype or "")
    base = re.sub(r"\d+$", "", re.sub(r"[^a-z0-9_]", "", col.lower()))
    flat = base.replace("_", "")
    if IDENTIFIER.search(base) and fam == "string":
        return "an identity / tax / card number"
    if PERSONAL.search(base) and not STRUCTURAL.search(flat):
        if fam == "string":
            return "name looks like personal data"
        if fam in ("temporal", "numeric") and re.search(r"birth|\bdob\b", base):
            return "birth date (or part of it)"
    return None


def pii_columns(con, db_path, alias: str, table: str, columns: list[str], explain: bool = False) -> dict[str, str]:
    """{column: 'email' | 'other'} for the columns to mask (explain=True: {column: reason})."""
    from ..catalog import annotations
    flags = {c: json.loads(f or "[]") for c, f in con.execute(
        f"SELECT column_name, flags FROM {META}.column_profile WHERE schema_name=? AND table_name=?", [alias, table]).fetchall()}
    types = dict(con.execute(f"SELECT column_name, data_type FROM {META}.remote_columns WHERE alias=? AND table_name=?", [alias, table]).fetchall())
    ann = annotations(db_path)
    out = {}
    for c in columns:
        tags = (ann.get((alias, table, c)) or {}).get("tags") or ""
        why = _reason(c, types.get(c, "STRING"), flags.get(c, []), tags, table)
        if why:
            out[c] = why if explain else ("email" if ("pii_email" in flags.get(c, []) or re.search(r"e_?mail", c, re.I)) else "other")
    return out


def mask_table(con, schema: str, table: str, cols: dict[str, str], salt_: str) -> None:
    if not cols:
        return
    rep = ", ".join(f"{mask_sql(c, salt_, k == 'email')} AS {qi(c)}" for c, k in cols.items())
    con.execute(f"CREATE OR REPLACE TABLE {fq(schema, table)} AS SELECT * REPLACE ({rep}) FROM {fq(schema, table)}")


def scrub_profile(con, alias: str, table: str, cols: dict[str, str], salt_: str) -> None:
    """Mask values kept in the stored profile and key fingerprints of these columns."""
    for c, kind in cols.items():
        email = kind == "email"
        r = con.execute(f"SELECT top_values, min_val, max_val FROM {META}.column_profile WHERE schema_name=? AND table_name=? AND column_name=?",
                        [alias, table, c]).fetchone()
        if r:
            top = [{**x, "v": mask_value(x.get("v"), salt_, email)} for x in json.loads(r[0] or "[]")]
            con.execute(f"""UPDATE {META}.column_profile SET top_values=?, min_val=?, max_val=?
                            WHERE schema_name=? AND table_name=? AND column_name=?""",
                        [json.dumps(top), mask_value(r[1], salt_, email), mask_value(r[2], salt_, email), alias, table, c])
        if has_meta(con, "key_values"):
            con.execute(f"UPDATE {META}.key_values SET v = {mask_sql('v', salt_, email)} WHERE schema_name=? AND table_name=? AND column_name=?",
                        [alias, table, c])


def apply(con, db_path, alias: str, table: str, local_copy: bool) -> list[str]:
    """Mask a cached copy (if any) and the stored profile/fingerprints of one remote table. Returns masked columns."""
    if not enabled(con, alias):
        return []
    cols_all = [r[0] for r in con.execute(f"SELECT column_name FROM {META}.remote_columns WHERE alias=? AND table_name=? ORDER BY ordinal",
                                          [alias, table]).fetchall()]
    cols = pii_columns(con, db_path, alias, table, cols_all)
    s = salt(con)
    if local_copy:
        mask_table(con, alias, table, cols, s)
    scrub_profile(con, alias, table, cols, s)
    return sorted(cols)


def apply_schema(db_path, alias: str) -> dict[str, list[str]]:
    """Turn masking on for everything already stored for a remote schema: cached copies are masked in place
    (no re-download), profiles and key fingerprints are scrubbed. Returns {table: masked columns}."""
    from ..db import connect, user_tables
    con = connect(db_path, read_only=False, retries=5)
    out = {}
    try:
        set_enabled(con, alias, True)
        local = {t for s_, t in user_tables(con) if s_ == alias}
        for (t,) in con.execute(f"SELECT table_name FROM {META}.remote_tables WHERE alias=? AND NOT dropped ORDER BY 1", [alias]).fetchall():
            cols = apply(con, db_path, alias, t, local_copy=t in local)
            if cols:
                out[t] = cols
                if t in local:
                    con.execute(f"UPDATE {META}.remote_cache SET masked_columns=? WHERE alias=? AND table_name=?", [json.dumps(cols), alias, t])
        con.execute("CHECKPOINT")
    finally:
        con.close()
    return out
