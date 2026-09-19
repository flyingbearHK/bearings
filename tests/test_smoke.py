"""End-to-end smoke test on the generated demo data (no real data needed)."""
import os

from typer.testing import CliRunner


def test_demo_end_to_end(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from bearings.cli import app

    r = CliRunner().invoke(app, ["demo", "--scale", "0.1", "--db", "data/demo.duckdb"])
    assert r.exit_code == 0, r.output

    os.environ["BEARINGS_DB"] = str(tmp_path / "data" / "demo.duckdb")
    from fastapi.testclient import TestClient
    import importlib
    import bearings.api as api
    importlib.reload(api)
    c = TestClient(api.app)

    st = c.get("/api/stats").json()
    assert st["tables"] == 8 and set(st["schemas"]) == {"pms", "crm"}

    # exact vs fuzzy name matching
    exact = c.get("/api/search", params={"q": "reservationid", "match": "exact", "columns_only": True}).json()
    cols = {(t["table"], m["column"]) for t in exact["tables"] for m in t["matched_columns"]}
    assert ("reservation", "reservation_id") in cols and ("folio_charge", "resv_ref") not in cols

    # schema scope
    scoped = c.get("/api/search", params={"q": "guest", "schemas": "crm"}).json()
    assert {t["schema"] for t in scoped["tables"]} == {"crm"}

    # multi-table lookup
    targets = [{"schema": "pms", "table": "reservation", "columns": ["reservation_id"]},
               {"schema": "pms", "table": "folio_charge", "columns": ["reservation_id"]}]
    lk = c.post("/api/lookup", json={"targets": targets, "op": "=", "value": "42"}).json()
    assert lk["results"][0]["count"] == 1

    # profile + sample + relationships
    assert c.get("/api/table/pms/guest/profile").json()["stored"] is True
    assert len(c.get("/api/table/pms/guest/sample", params={"n": 5}).json()["rows"]) == 5
    assert any(r["from_column"] == "PmsGuestCode" for r in c.get("/api/relationships").json())
