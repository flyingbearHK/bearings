"""Phase 3 (v0.4): code lists, optional attributes / subtypes, attribute comparison across a link, near-duplicates,
outliers, and DQ rule export (DQX / Great Expectations / Purview) – on the generated demo data."""
import importlib
import io
import json
import os
import zipfile

import pytest
from typer.testing import CliRunner


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory):
    d = tmp_path_factory.mktemp("phase3")
    old = os.getcwd()
    os.chdir(d)
    try:
        from bearings.cli import app
        r = CliRunner().invoke(app, ["demo", "--scale", "0.1", "--db", "data/demo.duckdb"])
        assert r.exit_code == 0, r.output
    finally:
        os.chdir(old)
    return d / "data" / "demo.duckdb"


@pytest.fixture(scope="module")
def con(demo_db):
    import duckdb
    c = duckdb.connect(str(demo_db), read_only=True)
    yield c
    c.close()


def test_code_lists(con):
    from bearings import codes
    lists = {(x["schema"], x["table"], x["column"]): x for x in codes.lists(con)}
    assert ("crm", "customer", "CountryOfResidence") in lists and lists[("pms", "guest", "guest_type")]["values"] == 2
    assert ("pms", "guest", "guest_id") not in lists and ("pms", "guest", "first_name") not in lists   # keys and PII aren't code lists
    sim = codes.similar(con, "crm", "customer", "CountryOfResidence")
    assert sim[0]["column"] == "nationality_code" and sim[0]["containment"] == 1.0
    cmp = codes.compare(con, ("pms", "reservation", "status_code"), ("dwh", "stay_flat", "status_code"))
    assert cmp["matched"] == 4 and cmp["only_left"] == 0 and cmp["only_right"] == 0


def test_optional_attributes_and_subtypes(con):
    from bearings import insights
    g = insights.optional_view(con, "pms", "guest")
    grp = g["groups"][0]
    assert set(grp["columns"]) == {"company_name", "company_tax_id"} and grp["when"]["by_column"] == "guest_type"
    assert grp["when"]["when_values"] == ["CORPORATE"] and "subtype" in grp["sentence"]
    s = insights.optional_view(con, "dwh", "stay_flat")
    rule = next(r for r in s["rules"] if r["column_name"] == "cancel_date")     # 1900-01-01 counts as empty
    assert rule["by_column"] == "status_code" and rule["when_values"] == ["CXL"] and rule["precision"] == 1.0


def test_outliers_and_negatives(con):
    from bearings.profiler import load_profile
    a = load_profile(con, "pms", "folio_charge")[1]["amount"]
    assert {"outliers", "negatives"} <= set(a["flags"]) and a["negative_count"] > 0 and a["outlier_values"][0]["v"] > 10000
    assert "outliers" not in load_profile(con, "pms", "guest")[1]["guest_id"]["flags"]   # ids are not measures


def test_duplicates(con):
    from bearings import duplicates
    roles = duplicates.roles(con, "crm", "customer")
    assert roles == {"first_name": "GivenName", "last_name": "FamilyName", "email": "EmailAddr", "dob": "BirthDate"}
    r = duplicates.find(con, "crm", "customer")
    assert r["pairs"] >= 9 and r["largest_group"] == 2
    keys = {(row[1], row[1 + len(r["shown_columns"])]) for row in r["examples"]}
    assert ("C-0000003", "C-9000003") in keys      # "Rossi" vs "Rossie", birth date in two formats
    assert duplicates.find(con, "pms", "folio_charge")["error"]


def test_attribute_comparison(con):
    from bearings import compare
    from bearings.profiler import load_profile
    cl = {c: p["data_type"] for c, p in load_profile(con, "crm", "customer")[1].items()}
    cr = {c: p["data_type"] for c, p in load_profile(con, "pms", "guest")[1].items()}
    hints = {("l", "BirthDate"): load_profile(con, "crm", "customer")[1]["BirthDate"]["type_hint"]}
    r = compare.attributes(con, ("crm", "customer", "PmsGuestCode"), ("pms", "guest", "guest_code"), cl, cr, hints)
    pairs = {(p["left"], p["right"]): p for p in r["pairs"]}
    assert ("GivenName", "first_name") in pairs and ("EmailAddr", "email_address") in pairs
    bd = pairs[("BirthDate", "date_of_birth")]
    assert bd["agree_pct"] == 100.0 and bd["equal"] < bd["equal_normalised"]          # same dates, different format
    fam = pairs[("FamilyName", "last_name")]
    assert fam["equal"] == 0 and fam["differ"] > 0 and fam["agree_pct"] > 90           # upper-case in the CRM + typos
    em = pairs[("EmailAddr", "email_address")]
    assert em["only_left"] > 0 and em["only_right"] > 0


def test_dq_rules_and_exports(con, demo_db):
    from bearings import catalog, dqrules
    cat = catalog.build(con, demo_db)
    rules = dqrules.all_rules(con, cat, [("pms", "folio_charge"), ("pms", "guest"), ("crm", "marketing_consent"), ("dwh", "stay_flat")])
    by = {(r["table"], r["rule"], tuple(r["columns"])): r for r in rules}
    assert by[("folio_charge", "foreign_key", ("resv_ref",))]["criticality"] == "warn"
    assert by[("folio_charge", "foreign_key", ("reservation_id",))]["criticality"] == "error"
    assert by[("folio_charge", "non_negative", ("amount",))]["criticality"] == "warn"
    assert ("folio_charge", "non_negative", ("gl_account",)) not in by                 # 'account' is not an amount
    assert by[("folio_charge", "valid_date", ("posting_date_txt",))]["args"]["date_format"] == "yyyy-MM-dd"
    assert by[("marketing_consent", "unique_combo", ("CustomerId", "Channel"))]["criticality"] == "error"
    assert by[("guest", "regex", ("guest_code",))]["args"]["regex"] == "^[A-Z][0-9]{8}$"
    assert by[("guest", "filled_when", ("company_name",))]["filter"] == "\"guest_type\" IN ('CORPORATE')"
    assert set(by[("guest", "in_list", ("guest_type",))]["args"]["allowed"]) == {"CORPORATE", "INDIVIDUAL"}
    y = dqrules.to_dqx_yaml([r for r in rules if r["table"] == "guest"])
    assert "function: is_not_null_and_is_in_list" in y and "filter: \"`guest_type` IN ('CORPORATE')\"" in y
    suite = dqrules.to_gx_suite(rules, "demo")
    types = {e["type"] for e in suite["expectations"]}
    assert {"expect_column_values_to_be_in_set", "expect_compound_columns_to_be_unique", "expect_column_values_to_match_regex"} <= types
    z = zipfile.ZipFile(io.BytesIO(dqrules.bundle(rules)))
    assert {"purview_rules.csv", "README.txt", "dqx/pms.guest.yml", "gx/pms.guest.json"} <= set(z.namelist())
    assert "Table lookup" in z.read("purview_rules.csv").decode()
    try:
        import yaml  # optional: check the YAML parses into DQX's shape
        checks = yaml.safe_load(z.read("dqx/pms.guest.yml"))
        assert all({"criticality", "check"} <= set(c) and "function" in c["check"] for c in checks)
    except ImportError:
        pass


def test_api(demo_db, con):
    con.close()
    os.environ["BEARINGS_DB"] = str(demo_db)
    import bearings.api as api
    importlib.reload(api)
    from fastapi.testclient import TestClient
    c = TestClient(api.app)
    assert any(x["column"] == "guest_type" for x in c.get("/api/codes", params={"schemas": "pms"}).json())
    v = c.get("/api/codes/values", params={"ref": "crm.customer.CountryOfResidence"}).json()
    assert len(v["values"]) == 10 and v["similar"]
    assert c.get("/api/codes/compare", params={"left": "pms.reservation.status_code", "right": "dwh.stay_flat.status_code"}).json()["matched"] == 4
    ins = c.get("/api/table/pms/guest/insights").json()
    assert ins["optional"]["groups"] and any(x["column"] == "guest_type" for x in ins["code_lists"])
    bd = c.get("/api/table/pms/guest/breakdown", params={"column": "company_name", "by": "guest_type"}).json()
    assert {r[0]: r[3] for r in bd["rows"]} == {"INDIVIDUAL": 0.0, "CORPORATE": 100.0}
    d = c.post("/api/table/crm/customer/duplicates", json={}).json()
    assert d["pairs"] >= 9
    cmp = c.post("/api/compare", json={"left": "crm.customer.PmsGuestCode", "right": "pms.guest.guest_code"}).json()
    assert cmp["joined_rows"] > 0 and any(p["left"] == "FamilyName" for p in cmp["pairs"])
    diff = c.get("/api/compare/differences", params={"left": "crm.customer.PmsGuestCode", "right": "pms.guest.guest_code",
                                                       "left_column": "FamilyName", "right_column": "last_name"}).json()
    assert diff["rows"] and all(r[1].lower() != r[2].lower() for r in diff["rows"])
    rules = c.get("/api/dq/rules", params={"tables": "pms.guest"}).json()
    ids = [r["id"] for r in rules][:3]
    y = c.post("/api/dq/export", json={"tables": ["pms.guest"], "ids": ids, "format": "dqx"})
    assert y.status_code == 200 and y.text.count("- criticality:") == 3
    gx = c.post("/api/dq/export", json={"tables": ["pms.guest"], "format": "gx"}).json()
    assert gx["name"] == "pms.guest" and gx["expectations"]
    assert c.post("/api/dq/export", json={"schemas": ["pms"], "format": "zip"}).headers["content-type"] == "application/zip"
    e = c.post("/api/erd", json={"tables": ["pms.reservation", "pms.guest"]}).json()
    assert e["model"]["links"][0]["parent_arrow"] == "ERmandOne" and e["model"]["entities"]
    wb = c.get("/api/export/catalog.xlsx")
    import openpyxl
    names = openpyxl.load_workbook(io.BytesIO(wb.content)).sheetnames
    assert {"Code lists", "DQ rules"} <= set(names)


def test_cli(demo_db, tmp_path):
    from bearings.cli import app
    out = tmp_path / "rules.zip"
    r = CliRunner().invoke(app, ["dq-rules", "-o", str(out), "-s", "pms", "--db", str(demo_db)])
    assert r.exit_code == 0 and out.exists(), r.output
    r = CliRunner().invoke(app, ["dq-rules", "-o", str(tmp_path / "g.yml"), "-t", "pms.guest", "--errors-only", "--db", str(demo_db)])
    assert r.exit_code == 0 and "warn" not in (tmp_path / "g.yml").read_text().split("criticality: ")[1][:5]
    r = CliRunner().invoke(app, ["duplicates", "crm.customer", "--db", str(demo_db)])
    assert r.exit_code == 0 and "likely duplicate pairs" in r.output
