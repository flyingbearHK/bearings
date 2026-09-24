"""Modelling insights (v0.4): disguised nulls / type hints, relationship cardinality + ER diagram, grain, time coverage
and dependencies (candidate entities, hierarchies) – on the generated demo data."""
import importlib
import os

import duckdb
import pytest
from typer.testing import CliRunner


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("insights")
    old = os.getcwd()
    os.chdir(d)
    try:
        from bearings.cli import app
        r = CliRunner().invoke(app, ["demo", "--scale", "0.1", "--db", "data/demo.duckdb"])
        assert r.exit_code == 0, r.output
        assert "modelling insights for 9 tables" in r.output
    finally:
        os.chdir(old)
    return d / "data" / "demo.duckdb"


@pytest.fixture(scope="module")
def con(demo_db):
    from bearings.db import connect
    c = connect(demo_db)
    yield c
    c.close()


def _col(con, s, t, c):
    from bearings.profiler import load_profile
    return load_profile(con, s, t)[1][c]


# ---------------------------------------------------------------- F1 disguised nulls + type hints
def test_placeholders_and_type_hints(con):
    p = _col(con, "pms", "folio_charge", "posting_date_txt")
    assert p["type_hint"]["type"] == "DATE" and set(p["type_hint"]["formats"]) == {"%Y-%m-%d", "%d/%m/%Y"}
    assert "type_hint" in p["flags"]
    comp = _col(con, "dwh", "stay_flat", "company_name")
    assert "placeholders" in comp["flags"] and {x["v"] for x in comp["placeholder_values"]} >= {"N/A", "-", "UNKNOWN"}
    assert comp["effective_null_pct"] > comp["null_pct"] + 20
    cancel = _col(con, "dwh", "stay_flat", "cancel_date")
    assert cancel["placeholder_values"][0]["v"] == "1900-01-01" and cancel["effective_null_pct"] > 80


def test_type_hint_kinds():
    from bearings import profiler
    c = duckdb.connect()
    c.execute("""CREATE TABLE t AS SELECT * FROM (VALUES
        ('00123', '12', 'Y', '1.5', '20250105', 'x1'), ('00124', '13', 'N', '2', '20250106', 'x2'),
        ('125', '-4', 'Y', '3.25', '20250107', 'x3'), ('126', '15', 'N', '4', '20250108', 'x4')) v(acct_no, qty, active, rate, posting_dt, other)""")
    _, cols = profiler.profile_table(c, "main", "t")
    by = {p["column_name"]: p for p in cols}
    assert by["acct_no"]["type_hint"] is None and by["acct_no"]["leading_zero_count"] == 2 and "leading_zeros" in by["acct_no"]["flags"]
    assert by["qty"]["type_hint"]["type"] == "BIGINT"
    assert by["active"]["type_hint"]["type"] == "BOOLEAN"
    assert by["rate"]["type_hint"]["type"] == "DECIMAL"
    assert by["posting_dt"]["type_hint"] == {"type": "DATE", "share": 1.0, "checked": 4, "formats": {"%Y%m%d": 1.0}}
    assert by["other"]["type_hint"] is None


# ---------------------------------------------------------------- F2 cardinality + ERD
def test_cardinality(con):
    from bearings import export
    rels = {(r["from_table"], r["from_column"], r["to_table"]): r for r in export.relationships(con)}
    la = rels[("loyalty_account", "CustomerId", "customer")]
    assert la["cardinality"] == "1:1" and la["parent_no_child_pct"] > 0 and la["fk_null_pct"] == 0
    assert "at most one loyalty_account" in la["summary"]
    assert rels[("folio_charge", "resv_ref", "reservation")]["orphan_rows"] > 0
    x = rels[("customer", "PmsGuestCode", "guest")]
    assert x["cardinality"] == "1:N" and x["child_max"] == 2 and x["fk_null_pct"] > 0   # CRM duplicates, optional link
    assert rels[("marketing_consent", "CustomerId", "customer")]["child_max"] == 3
    # amounts are never foreign keys, even when a flattened copy shares their values
    assert not any(r["from_column"] == "room_revenue" for r in rels.values())


def test_erd(con, demo_db):
    from bearings import catalog, export
    txt = export.erd(con, catalog.build(con, demo_db), {"crm"})
    assert txt.startswith("erDiagram")
    assert 'customer ||--o| loyalty_account : "CustomerId"' in txt
    assert 'customer ||--o{ marketing_consent : "CustomerId"' in txt or 'customer ||--|{ marketing_consent : "CustomerId"' in txt
    assert "varchar Channel PK" in txt          # no single-column key: the grain is used as the key
    # only the chosen entities: links need both ends selected; a chosen table without links is still drawn
    sub = export.erd(con, catalog.build(con, demo_db), None, tables={("crm", "customer"), ("crm", "loyalty_account"), ("pms", "property")})
    assert "loyalty_account" in sub and "marketing_consent" not in sub and "property {" in sub
    assert sum(1 for x in sub.splitlines() if "--" in x) == 1


# ---------------------------------------------------------------- F3 grain
def test_grain(con):
    from bearings import insights
    assert insights.read(con, "crm", "marketing_consent")["grain"]["combos"] == [["CustomerId", "Channel"]]
    assert insights.read(con, "pms", "reservation")["grain"]["combos"][0] == ["reservation_id"]


def test_grain_on_sample_is_confirmed(con):
    from bearings import insights
    r = insights.run(con, "crm", "marketing_consent", sample_rows=500)
    assert r["on_sample"] and r["grain"]["combos"] == [["CustomerId", "Channel"]] and r["grain"]["dup_rows"] == 0
    insights.run(con, "crm", "marketing_consent")   # back to the full-table result


# ---------------------------------------------------------------- F4 time coverage
def test_time_coverage(con):
    from bearings import insights
    t = {x["column_name"]: x for x in insights.read(con, "pms", "reservation")["time"]}
    a = t["arrival_date"]
    assert a["is_primary"] and a["kind"] == "event" and a["empty_months"] == 0 and a["future_rows"] > 0
    assert t["last_modified_ts"]["kind"] == "stamp"
    p = {x["column_name"]: x for x in insights.read(con, "pms", "property")["time"]}
    assert p["opening_date"]["kind"] == "attribute"
    f = {x["column_name"]: x for x in insights.read(con, "pms", "folio_charge")["time"]}
    assert f["posting_date_txt"]["parsed_from_text"] and f["posting_date_txt"]["months_present"] > 12
    s = {x["column_name"]: x for x in insights.read(con, "dwh", "stay_flat")["time"]}
    assert s["cancel_date"]["sentinel_rows"] > 0


# ---------------------------------------------------------------- F5 dependencies → entities
def _structure(con, s, t):
    from bearings import insights, profiler, relationships
    _, prof = profiler.load_profile(con, s, t)
    cols = {}
    for s_, t_, c in con.execute("SELECT table_schema, table_name, column_name FROM information_schema.columns").fetchall():
        cols.setdefault((s_, t_), []).append(c)
    return insights.structure(insights.read(con, s, t)["dependencies"], {c: insights._col_info(p) for c, p in prof.items()},
                              relationships.with_targets(con, cols), s, t)


def test_entities_in_flat_extract(con):
    st = _structure(con, "dwh", "stay_flat")
    ents = {e["name"]: e for e in st["entities"]}
    prop = ents["Property"]
    assert prop["columns"][0] == "property_code" and "property_name" in prop["columns"]
    assert {d["columns"][0] for d in prop["determines"]} == {"region_name", "brand_name"}
    levels = [[lv["name"] for lv in h["levels"]] for h in st["hierarchies"]]
    assert ["Room type", "Property", "Region"] in levels and ["Room type", "Property", "Brand"] in levels
    assert any(d["dependent"] == "property_name" and d["determinant"] == "property_code" for d in st["dirty"])  # misspelt names
    assert any(n["kind"] == "redundant_fk" for n in st["notes"])
    assert any(n["kind"] == "denormalised" and "room_type_desc" in n["columns"] for n in st["notes"])


def test_no_accidental_dependencies(con):
    st = _structure(con, "pms", "reservation")
    cols = {c for e in st["entities"] for c in e["columns"] + [x for d in e["determines"] for x in d["columns"]]}
    assert not cols & {"channel_code", "nights", "market_segment", "guest_id", "travel_agent_id"}
    assert [e["columns"] for e in st["entities"]] == [["room_type_id"]]   # room type implies the hotel (redundant FK)
    fc = {tuple(e["columns"]) for e in _structure(con, "pms", "folio_charge")["entities"]}
    assert ("charge_type", "gl_account") in fc


# ---------------------------------------------------------------- API
def test_api(demo_db, con):
    con.close()   # the app opens its own (read-only) connections
    os.environ["BEARINGS_DB"] = str(demo_db)
    import bearings.api as api
    importlib.reload(api)
    from fastapi.testclient import TestClient
    c = TestClient(api.app)
    assert c.get("/api/stats").json()["version"]
    d = c.get("/api/table/dwh/stay_flat").json()
    assert d["insights"]["grain"]["combos"][0] == ["stay_id"] and d["insights"]["time"]["column_name"] == "arrival_date"
    ins = c.get("/api/table/dwh/stay_flat/insights").json()
    assert any(e["name"] == "Property" for e in ins["structure"]["entities"])
    ex = c.get("/api/table/dwh/stay_flat/insights/exceptions", params={"determinant": "property_code", "dependent": "property_name"}).json()
    assert ex["rows"] and ex["columns"][-1] == "expected_property_name"
    # dismiss / undo
    item = "property_code->region_name"
    assert c.post("/api/insights/dismiss", json={"schema": "dwh", "table": "stay_flat", "item": item}).json()["dismissed"] == [item]
    prop = next(e for e in c.get("/api/table/dwh/stay_flat/insights").json()["structure"]["entities"] if e["name"] == "Property")
    assert [d["columns"][0] for d in prop["determines"]] == ["brand_name"]
    c.post("/api/insights/dismiss", json={"schema": "dwh", "table": "stay_flat", "item": item, "undo": True})
    job = c.post("/api/insights", json={"tables": ["pms.guest"], "wait": True}).json()
    assert job["status"] == "done" and job["results"][0]["table"] == "pms.guest"
    assert c.get("/api/erd.mmd", params={"schemas": "pms"}).text.startswith("erDiagram")
    e = c.post("/api/erd", json={"tables": ["pms.reservation", "pms.guest", "pms.property"], "min_confidence": 0.8}).json()
    assert e["entities"] == 3 and e["links"] == 2 and "folio_charge" not in e["mermaid"]
    assert "room_type" not in c.get("/api/erd.mmd", params={"tables": "pms.reservation,pms.guest"}).text
    ov = c.get("/api/overlap", params={"left": "crm.marketing_consent.CustomerId", "right": "crm.customer.CustomerId"}).json()
    assert ov["cardinality"] == "1:N" and ov["summary"]
    md = c.get("/api/table/dwh/stay_flat/export.md").text
    assert "- Grain: one row per stay_id" in md and "## Candidate entities" in md and "Room type → Property → Region" in md
    assert c.get("/api/export/catalog.xlsx").status_code == 200


def test_wide_tables_get_a_smaller_sample():
    from bearings import insights
    assert insights.sample_size(10, insights.DEFAULT_SAMPLE) == insights.DEFAULT_SAMPLE
    assert insights.sample_size(144, insights.DEFAULT_SAMPLE) == insights.SAMPLE_CELLS // 144
    assert insights.sample_size(2000, insights.DEFAULT_SAMPLE) == insights.MIN_SAMPLE
    assert insights.sample_size(144, 500) == 500 and insights.sample_size(144, None) is None


def test_optional_rule_with_empty_code_value():
    """A fill rule whose code column includes NULL among its values (used to fail sorting None with strings)."""
    from bearings import insights, profiler
    c = duckdb.connect()
    c.execute("""CREATE TABLE t AS SELECT i AS id, CASE WHEN i % 4 = 0 THEN NULL WHEN i % 4 = 1 THEN 'A' ELSE 'B' END AS kind,
                 CASE WHEN i % 4 IN (0, 1) THEN 'v' || i END AS extra FROM range(4000) r(i)""")
    _, cols = profiler.profile_table(c, "main", "t")
    rules, _ = insights.optional_attributes(c, "t", {p["column_name"]: p for p in cols})
    r = next(x for x in rules if x["column_name"] == "extra")
    assert r["by_column"] == "kind" and r["when_values"] == ["A", None]


def test_rare_dates_and_codes_read_the_whole_table(tmp_path):
    """Time coverage and code lists scan the whole table, so a date filled on a handful of rows isn't lost to the sample."""
    from bearings import insights, profiler
    from bearings.db import connect
    c = connect(tmp_path / "rare.duckdb")
    c.execute("""CREATE SCHEMA s; CREATE TABLE s.t AS SELECT i AS id, 'k' || (i % 50) AS kind,
                 DATE '2025-01-01' + (i % 300)::INT AS posting_date,
                 CASE WHEN i IN (7, 70007) THEN DATE '2024-03-01' END AS rare_date FROM range(100000) r(i)""")
    tp, cols = profiler.profile_table(c, "s", "t")
    profiler.save(c, tp, cols)
    r = insights.run(c, "s", "t", sample_rows=500)
    assert r["on_sample"] and not r["columns_on_sample"]
    assert "rare_date" in {x["column_name"] for x in r["time"]}
    assert sum(n for _, n in r["codes"]["kind"]) == 100000
    # --missing: nothing left to do, until the table is profiled again
    assert insights.targets(c, {"s"}, missing=True) == []
    c.execute("UPDATE _meta.table_profile SET profiled_at = insights_at + INTERVAL 1 MINUTE WHERE schema_name = 's'")
    assert insights.targets(c, {"s"}, missing=True) == [("s", "t")]
    c.close()
