"""Profiler robustness: odd columns shouldn't lose the whole table."""
import duckdb

from bearings import profiler


class Flaky:
    """DuckDB connection that fails any statement touching one column's statistics."""

    def __init__(self, con, needle):
        self.con, self.needle = con, needle

    def execute(self, sql, *a):
        if self.needle in sql:
            raise duckdb.ConversionException('Casting value "183823530.0" to type DECIMAL(18,10) failed: value is out of range!')
        return self.con.execute(sql, *a)


def test_one_bad_column_does_not_lose_the_table():
    con = duckdb.connect()
    con.execute("CREATE SCHEMA s; CREATE TABLE s.t AS SELECT i AS id, (i % 7)::DECIMAL(18,10) AS rate, 'x' || (i % 3) AS code FROM range(100) r(i)")
    tp, cols = profiler.profile_table(Flaky(con, 'quantile_cont(CAST("rate"'), "s", "t")
    by = {c["column_name"]: c for c in cols}
    assert "candidate_pk" in by["id"]["flags"] and by["code"]["distinct_count"] == 3     # other columns intact
    assert "profile_error" in by["rate"]["flags"] and by["rate"]["null_count"] == 0     # bad column: counts only, flagged
    assert tp["errors"] and "rate" in tp["errors"][0]


def test_decimal_statistics_use_double():
    con = duckdb.connect()
    con.execute("CREATE SCHEMA s; CREATE TABLE s.t AS SELECT (i * 1234567.891)::DECIMAL(18,10) AS amount FROM range(1, 81) r(i)")
    _, cols = profiler.profile_table(con, "s", "t")
    c = cols[0]
    assert not c["errors"] and c["histogram"] and float(c["p50"]) > 0


def test_timestamptz_sample_through_api(tmp_path, monkeypatch):
    """Tables pulled from Databricks have TIMESTAMP WITH TIME ZONE columns; returning them needs pytz."""
    import importlib
    db = tmp_path / "t.duckdb"
    from bearings.db import connect
    con = connect(db)
    con.execute("CREATE SCHEMA s; CREATE TABLE s.t AS SELECT i AS id, TIMESTAMPTZ '2026-01-01 10:00:00+00' + i * INTERVAL 1 HOUR AS created FROM range(5) r(i)")
    con.close()
    monkeypatch.setenv("BEARINGS_DB", str(db))
    import bearings.api as api
    importlib.reload(api)
    from bearings import catalog
    catalog._cache["key"] = None
    from fastapi.testclient import TestClient
    r = TestClient(api.app).get("/api/table/s/t/sample", params={"n": 3})
    assert r.status_code == 200 and len(r.json()["rows"]) == 3


def test_sample_filter_applies_to_whole_table(tmp_path, monkeypatch):
    """The sample's filter selects from the whole table, then samples the matching rows (USING SAMPLE runs before
    WHERE in one SELECT, so a rare value used to come back empty), and a fixed seed repeats the sample."""
    import importlib
    db = tmp_path / "f.duckdb"
    from bearings.db import connect
    con = connect(db)
    con.execute("CREATE SCHEMA s; CREATE TABLE s.t AS SELECT i AS id, i % 1000 AS bucket, 'x' || (i % 7) AS code FROM range(50000) r(i)")
    con.close()
    monkeypatch.setenv("BEARINGS_DB", str(db))
    import bearings.api as api
    importlib.reload(api)
    from bearings import catalog
    catalog._cache["key"] = None
    from fastapi.testclient import TestClient
    c = TestClient(api.app)
    r = c.get("/api/table/s/t/sample", params={"n": 20, "where": "bucket = 417"}).json()
    assert len(r["rows"]) == 20 and all(row[1] == 417 for row in r["rows"]) and r["matched"] == 50
    r = c.get("/api/table/s/t/sample", params={"n": 20, "where": "id = 49999", "columns": "code,id"}).json()
    assert r["columns"] == ["code", "id"] and r["rows"] == [["x5", 49999]]
    a = c.get("/api/table/s/t/sample", params={"n": 5, "seed": 3}).json()["rows"]
    assert a == c.get("/api/table/s/t/sample", params={"n": 5, "seed": 3}).json()["rows"]
