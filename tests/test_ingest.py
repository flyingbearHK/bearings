"""Add data from the app: folder picker, upload, preview, background load + profile + relationships."""
from __future__ import annotations

import importlib

import openpyxl
import pytest


@pytest.fixture()
def app_client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BEARINGS_DB", str(tmp_path / "data" / "t.duckdb"))
    import bearings.api as api
    importlib.reload(api)
    from bearings import catalog
    catalog._cache["key"] = None
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def _files(root):
    (root / "crm").mkdir(parents=True)
    (root / "crm" / "customer.csv").write_text("customer_id,name,tier_code\nC1,Ann,GLD\nC2,Bo,SLV\nC3,Cy,GLD\n")
    (root / "crm" / "orders.csv").write_text("order_id,customer_id,amount\n1,C1,10\n2,C1,20\n3,C2,5\n4,C3,7\n")
    (root / "crm" / "columns.csv").write_text("table_name,column_name,comment\ncustomer,tier_code,Loyalty tier\n")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Tiers"
    for r in (["tier_code", "tier_name"], ["GLD", "Gold"], ["SLV", "Silver"]):
        ws.append(r)
    wb.save(root / "crm" / "reference.xlsx")


def test_load_from_path(tmp_path, app_client):
    c = app_client
    _files(tmp_path / "exports")
    ls = c.get("/api/load/ls", params={"path": str(tmp_path / "exports")}).json()
    assert ls["dirs"] == ["crm"] and ls["parent"]
    assert {f["format"] for f in c.get("/api/load/ls", params={"path": str(tmp_path / "exports" / "crm")}).json()["files"]} == {"csv", "excel"}

    pv = c.post("/api/load/preview", json={"path": str(tmp_path / "exports" / "crm")}).json()
    assert pv["suggested_schema"] == "crm"
    assert sorted(i["table"] for i in pv["items"]) == ["customer", "orders", "reference"]   # columns.csv is a description file
    assert [p.endswith("columns.csv") for p in pv["comments"]] == [True]

    job = c.post("/api/load", json={"path": str(tmp_path / "exports" / "crm"), "schema": pv["suggested_schema"],
                                    "tables": ["customer", "orders", "reference"], "comments": pv["comments"], "wait": True}).json()
    assert job["status"] == "done", job
    assert job["summary"]["profiled"] == 3 and job["summary"]["comments"] == 1
    st = c.get("/api/stats").json()
    assert st["tables"] == 3 and st["profiled"] == 3
    t = c.get("/api/table/crm/customer").json()
    assert next(x for x in t["columns"] if x["column"] == "tier_code")["comment"] == "Loyalty tier"
    rels = c.get("/api/relationships").json()
    assert any(r["from_table"] == "orders" and r["to_table"] == "customer" for r in rels)

    # only the ticked tables; bad input is refused
    job = c.post("/api/load", json={"path": str(tmp_path / "exports" / "crm"), "schema": "crm2", "tables": ["orders"],
                                    "profile": False, "wait": True}).json()
    assert [r["table"] for r in job["results"]] == ["orders"] and job["summary"]["profiled"] == 0
    assert c.post("/api/load", json={"path": str(tmp_path / "nope"), "schema": "x"}).status_code == 404
    assert c.post("/api/load", json={"path": str(tmp_path / "exports"), "schema": "_meta"}).status_code == 400


def test_upload_dropped_folder(tmp_path, app_client):
    c = app_client
    _files(tmp_path / "src")
    batch = "drop_abc123"
    for p in sorted((tmp_path / "src").rglob("*")):
        if p.is_file():
            rel = p.relative_to(tmp_path / "src").as_posix()          # crm/customer.csv, like a dropped folder
            r = c.post("/api/load/upload", params={"batch": batch, "name": rel}, content=p.read_bytes())
            assert r.status_code == 200, r.text
    pv = c.post("/api/load/preview", json={"upload": batch}).json()
    assert pv["path"] is None and pv["suggested_schema"] == "crm"          # the dropped folder's name
    assert sorted(i["table"] for i in pv["items"]) == ["customer", "orders", "reference"]
    assert pv["comments_display"] == ["columns.csv"]
    job = c.post("/api/load", json={"upload": batch, "schema": "crm", "comments": pv["comments"], "wait": True}).json()
    assert job["status"] == "done" and job["summary"]["comments"] == 1, job
    assert (tmp_path / "data" / "uploads" / batch / "crm" / "customer.csv").exists()

    # loose files; names can't escape the upload folder
    assert c.post("/api/load/upload", params={"batch": "../x", "name": "a.csv"}, content=b"x").status_code == 400
    r = c.post("/api/load/upload", params={"batch": "loose_1234", "name": "../../evil.csv"}, content=b"a\n1\n")
    assert r.json()["name"] == "evil.csv"
    c.post("/api/load/upload", params={"batch": "loose_1234", "name": "b.csv"}, content=b"b\n2\n")
    pv = c.post("/api/load/preview", json={"upload": "loose_1234"}).json()
    assert pv["suggested_schema"] == "main" and {i["table"] for i in pv["items"]} == {"evil", "b"}


def test_part_file_heuristic(tmp_path):
    from bearings import loader
    exp = tmp_path / "exp"
    for d, names in {"resv": ["part-00000-a.csv", "part-00001-b.csv"], "chunks": ["guest_001.csv", "guest_002.csv"],
                     "hive": ["year=2025/x.csv", "year=2026/y.csv"], "mixed": ["customer.csv", "orders.csv"]}.items():
        for n in names:
            (exp / d / n).parent.mkdir(parents=True, exist_ok=True)
            (exp / d / n).write_text("a\n1\n")
    assert sorted(i.table for i in loader.discover(exp)) == ["chunks", "customer", "hive", "orders", "resv"]
