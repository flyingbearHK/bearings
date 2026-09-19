"""Remote (Databricks) mode against a fake Unity Catalog + SQL warehouse – no workspace needed."""
from __future__ import annotations

import importlib
import re
from types import SimpleNamespace as NS

import pytest

pa = pytest.importorskip("pyarrow", reason="remote mode needs: uv sync --extra databricks")
from typer.testing import CliRunner

from bearings.remote import connections as cx

# ------------------------------------------------------------------ fake Databricks


def col(name, type_text, pos, comment=None):
    return NS(name=name, type_text=type_text, type_name=None, position=pos, nullable=True, comment=comment)


def tbl(name, cols, comment=None, updated=1_760_000_000_000):
    return NS(name=name, table_type=NS(value="MANAGED"), comment=comment, columns=cols, updated_at=updated,
              properties={"spark.sql.statistics.numRows": "3"})


class FakeUC:
    def __init__(self):
        self.schemas_data = {("lakehouse", "bronze_opera"): {
            "reservation": tbl("reservation", [col("reservation_id", "bigint", 0, "Opera confirmation number"),
                                               col("guest_id", "string", 1), col("arrival_dt", "date", 2),
                                               col("guest_email", "string", 3, "Guest e-mail address")], comment="Stays"),
            "guest": tbl("guest", [col("guest_id", "string", 0, "Opera profile id"), col("full_name", "string", 1)]),
        }}
        self.tables = NS(list=self._list)
        self.catalogs = NS(list=lambda: [NS(name="lakehouse"), NS(name="main")])
        self.schemas = NS(list=lambda catalog_name: [NS(name=s, comment=None) for (c, s) in self.schemas_data if c == catalog_name]
                          + [NS(name="information_schema", comment=None)])
        self.warehouses = NS(list=lambda: [NS(id="4b9e1c0f2a7d6e53", name="Serverless Starter Warehouse", state=NS(value="STOPPED"),
                                              enable_serverless_compute=True, warehouse_type=NS(value="PRO"), cluster_size="2X-Small")])
        self.current_user = NS(me=lambda: NS(user_name="bruce@example.com", display_name="Bruce"))
        self.config = NS(host="https://adb-1.azuredatabricks.net", authenticate=lambda: {"Authorization": "Bearer x"})

    def _list(self, catalog_name, schema_name, **_):
        key = (catalog_name, schema_name)
        if key not in self.schemas_data:
            raise RuntimeError(f"NOT_FOUND: Schema '{catalog_name}.{schema_name}' does not exist.")
        return list(self.schemas_data[key].values())


VERSIONS: dict = {}   # table -> Delta version reported by DESCRIBE HISTORY (default 1)

ROWS = {"reservation": pa.table({"reservation_id": [9401, 9402, 9403], "guest_id": ["G1", "G2", "G1"],
                                 "arrival_dt": pa.array([19000, 19001, 19002], pa.date32()),
                                 "guest_email": ["a@x.com", None, "a@x.com"]})}


class FakeCursor:
    """Runs the Databricks SQL we generate on DuckDB (after a light Spark → DuckDB translation)."""

    def __init__(self, log):
        import duckdb
        self.log, self.data, self.pos = log, None, 0
        self.db = duckdb.connect()
        for name, tbl_ in ROWS.items():
            self.db.register(name.replace(".", "__"), tbl_)

    def execute(self, sql, params=None):
        self.log.append(sql)
        m = re.match(r"DESCRIBE HISTORY `[^`]+`\.`([^`]+)`\.`([^`]+)`", sql)
        if m:
            key = m.group(2) if m.group(1) == "bronze_opera" else f"{m.group(1)}.{m.group(2)}"
            self.data, self.pos = pa.table({"version": [VERSIONS.get(key, 1)], "operation": ["WRITE"]}), 0
            return
        q = re.sub(r"`([^`]+)`\.`([^`]+)`\.`([^`]+)`",
                   lambda m: '"' + (m.group(3) if m.group(2) == "bronze_opera" else f"{m.group(2)}__{m.group(3)}") + '"', sql)
        q = q.replace("`", '"')
        q = re.sub(r"TABLESAMPLE \(([\d.]+) PERCENT\)( REPEATABLE \(\d+\))?", r"TABLESAMPLE \1% (bernoulli, 7)", q)
        q = re.sub(r"\brand\(\d*\)", "random()", q)
        q = re.sub(r"pmod\(xxhash64\((.+?) AS STRING\)\), (\d+)\)", r"(hash(\1 AS VARCHAR)) % \2)", q)
        q = re.sub(r"(?<![:\w]):(\w+)", r"$\1", q)            # named :p parameters -> DuckDB $p
        res = self.db.execute(q, params or {})
        self.data, self.pos = (res.to_arrow_table() if hasattr(res, "to_arrow_table") else res.fetch_arrow_table()), 0
        names = self.data.column_names
        if len(set(names)) != len(names):  # like the real connector (Arrow results must have unique column names)
            raise RuntimeError("Can't unify schema with duplicate field names.")

    def fetchone(self):
        return [self.data.column(i)[self.pos].as_py() for i in range(self.data.num_columns)]

    def fetchmany_arrow(self, n):
        b = self.data.slice(self.pos, n)
        self.pos += n
        return b

    def fetchall_arrow(self):
        b = self.data.slice(self.pos)
        self.pos = self.data.num_rows
        return b

    def close(self):
        pass


class FakeSQL:
    def __init__(self, log):
        self.log = log

    def cursor(self):
        return FakeCursor(self.log)

    def close(self):
        pass


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BEARINGS_HOME", str(tmp_path / "home"))
    db = tmp_path / "data" / "t.duckdb"
    monkeypatch.setenv("BEARINGS_DB", str(db))
    uc, sql_log = FakeUC(), []
    monkeypatch.setattr(cx, "workspace_client_factory", lambda conn: uc)
    monkeypatch.setattr(cx, "sql_connect_factory", lambda conn, client, *a: FakeSQL(sql_log))
    from bearings.remote import query as rq
    rq.close_all()
    cx.reset_clients()
    from bearings.cli import app
    run = lambda *a: CliRunner().invoke(app, list(a))  # noqa: E731
    return NS(db=db, uc=uc, sql_log=sql_log, run=run, tmp=tmp_path)


def client(env):
    import bearings.api as api
    importlib.reload(api)
    from bearings import catalog
    catalog._cache["key"] = None
    from fastapi.testclient import TestClient
    return TestClient(api.app)


def test_connection_profiles(env):
    r = env.run("remote", "add", "dev", "--host", "https://adb-1.azuredatabricks.net/", "--warehouse", "wh1")
    assert r.exit_code == 0, r.output
    c = cx.get("dev")
    assert c.hostname == "adb-1.azuredatabricks.net" and c.http_path == "/sql/1.0/warehouses/wh1"
    assert "token" not in cx.config_path().read_text().lower()
    r = env.run("remote", "test", "dev", "--catalog", "lakehouse")
    assert r.exit_code == 0 and "bruce@example.com" in r.output and "bronze_opera" in r.output and "answered 1" in r.output, r.output
    assert "information_schema" not in env.run("remote", "schemas", "dev", "--catalog", "lakehouse").output
    r = env.run("remote", "warehouses", "dev")
    assert "4b9e1c0f2a7d6e53" in r.output and "serverless" in r.output, r.output
    assert env.run("attach", "nope", "lakehouse.bronze_opera").exit_code == 1


def test_attach_search_sync_orphans_pull_detach(env):
    env.run("remote", "add", "dev", "--host", "https://adb-1.azuredatabricks.net", "--warehouse", "wh1")
    r = env.run("attach", "dev", "lakehouse.bronze_opera")
    assert r.exit_code == 0 and "first sync" in r.output and "opera_dbx" in r.output, r.output
    assert env.run("attach", "dev", "lakehouse.missing", "--as", "x").exit_code == 1          # nothing written on failure
    assert env.run("attach", "dev", "lakehouse.bronze_opera").exit_code == 1                  # already attached

    c = client(env)
    st = c.get("/api/stats").json()
    sch = {s["schema"]: s for s in st["schema_stats"]}
    assert sch["bronze_opera_dbx" if "bronze_opera_dbx" in sch else "opera_dbx"]["kind"] == "remote"
    alias = next(a for a in sch if sch[a]["kind"] == "remote")
    assert st["tables"] == 2 and st["columns"] == 6

    # name search runs locally on synced metadata, including column comments
    hits = c.get("/api/search", params={"q": "confirmation number", "schemas": alias}).json()
    assert any(m["column"] == "reservation_id" for t in hits["tables"] for m in t["matched_columns"])
    t = c.get(f"/api/table/{alias}/reservation").json()
    assert t["kind"] == "remote" and t["remote"]["full_name"] == "lakehouse.bronze_opera.reservation" and t["comment"] == "Stays"

    # row-level features run live on the warehouse (phase 3); the local SQL console explains the engine switch
    r = c.get(f"/api/table/{alias}/reservation/sample")
    assert r.status_code == 200 and r.json()["remote"] and len(r.json()["rows"]) == 3
    assert c.post(f"/api/table/{alias}/reservation/uniqueness", json={"columns": ["reservation_id"]}).json()["is_unique"]
    lk = c.post("/api/lookup", json={"targets": [{"schema": alias, "table": "reservation", "columns": ["reservation_id"]}],
                                     "op": "=", "value": "9401"}).json()
    assert lk["results"][0]["remote"] and lk["results"][0]["count"] == 1
    assert c.get("/api/search", params={"q": "G1", "mode": "value"}).json()["skipped_remote"] == 2
    assert "Databricks" in c.post("/api/sql", json={"sql": f"SELECT * FROM {alias}.reservation"}).json()["detail"]
    assert c.get(f"/api/table/{alias}/reservation/profile", params={"live": True}).status_code == 409

    # annotate remote columns (works offline, like local ones)
    for colname, tags in (("guest_email", "PII"), ("arrival_dt", "date")):
        assert c.put("/api/annotations", json={"schema": alias, "table": "reservation", "column": colname,
                                               "tags": tags, "cdm_entity": "Reservation"}).status_code == 200

    # the data team changes the source: rename a column, change a type and a comment, add and drop tables
    s = env.uc.schemas_data[("lakehouse", "bronze_opera")]
    s["reservation"] = tbl("reservation", [col("reservation_id", "bigint", 0, "Confirmation number (Opera)"),
                                           col("guest_id", "bigint", 1), col("arrival_date", "date", 2),
                                           col("guest_email", "string", 3, "Guest e-mail address")], comment="Stays")
    s["folio"] = tbl("folio", [col("folio_id", "bigint", 0)])
    del s["guest"]
    r = env.run("sync", "--dry-run")
    assert "dry run" in r.output
    r = env.run("sync")
    assert r.exit_code == 0, r.output
    for kind in ("table_added", "table_dropped", "column_added", "column_dropped", "type_changed", "comment_changed"):
        assert kind in r.output, (kind, r.output)
    assert "arrival_dt" in r.output and "maybe arrival_date" in r.output   # orphaned annotation + suggestion

    c = client(env)
    ch = c.get("/api/remote/changes", params={"alias": alias}).json()
    assert {x["change"] for x in ch} >= {"table_added", "table_dropped", "column_added", "column_dropped", "type_changed"}
    assert (alias, "guest") not in {(x["schema"], x["table"]) for x in c.get("/api/tables").json()}
    orph = c.get("/api/annotations/orphans").json()
    assert [(o["column"], o["suggestions"][0]["column"]) for o in orph] == [("arrival_dt", "arrival_date")]
    assert c.post("/api/annotations/remap", json={"schema": alias, "table": "reservation", "column": "arrival_dt",
                                                  "new_column": "guest_email"}).status_code == 409   # won't overwrite
    assert c.post("/api/annotations/remap", json={"schema": alias, "table": "reservation", "column": "arrival_dt",
                                                  "new_column": "arrival_date"}).status_code == 200
    assert c.get("/api/annotations/orphans").json() == []

    # a sync with no remote change reports none (and the UI endpoint runs it as a job)
    job = c.post("/api/remote/sync", json={"wait": True}).json()
    assert job["status"] == "done" and job["results"][0]["changes"] == []
    ov = c.get("/api/remote").json()
    assert ov["sources"][0]["alias"] == alias and ov["sources"][0]["tables"] == 2 and ov["connections"][0]["name"] == "dev"

    # pull a sample: the local copy replaces the metadata-only entry and every local feature works
    r = env.run("pull", f"{alias}.reservation", "--rows", "2")
    assert r.exit_code == 0 and "Pulled 2 rows × 4 columns" in r.output, r.output
    assert any(q.startswith("SELECT count(*)") for q in env.sql_log[-3:])
    assert env.sql_log[-1] == "SELECT * FROM `lakehouse`.`bronze_opera`.`reservation` TABLESAMPLE (73.333333 PERCENT) LIMIT 2"
    c = client(env)
    t = c.get(f"/api/table/{alias}/reservation").json()
    assert t["kind"] == "local" and t["remote"]["pulled"] and t["storage"] == "sample" and t["row_count"] == 3 and t["cached_rows"] == 2
    assert {x["column"]: x["comment"] for x in t["columns"]}["guest_email"] == "Guest e-mail address"
    assert len(c.get(f"/api/table/{alias}/reservation/sample", params={"n": 5}).json()["rows"]) == 2
    assert "(remote)" not in env.run("info").output and "folio" in env.run("info").output

    r = env.run("pull", f"{alias}.reservation", "--where", "1=1; DROP TABLE x")
    assert r.exit_code == 1 and "simple filter" in r.output
    r = env.run("pull", f"{alias}.reservation", "--where", "guest_id = 'G1'", "--rows", "5", "--as", "pms.resv_copy")
    assert r.exit_code == 0 and "WHERE guest_id = 'G1' LIMIT 5" in env.sql_log[-1], r.output

    # detach forgets the cached metadata and pulled copies; annotations are kept by default
    r = env.run("detach", alias, "-y")
    assert r.exit_code == 0, r.output
    c = client(env)
    assert alias not in c.get("/api/stats").json()["schemas"] and "pms" in c.get("/api/stats").json()["schemas"]
    assert any(a["schema_name"] == alias for a in c.get("/api/annotations").json())


def test_old_database_read_only(env):
    """A database created before remote mode (no _meta.remote_* tables) still opens read-only."""
    import duckdb
    from bearings import catalog
    from bearings.db import connect, ro
    connect(env.db).close()
    con = duckdb.connect(str(env.db))
    for t in ("remote_sources", "remote_tables", "remote_columns", "sync_log"):
        con.execute(f"DROP TABLE _meta.{t}")
    con.execute("ALTER TABLE _meta.table_profile DROP COLUMN stale")
    con.execute("CREATE TABLE main.t AS SELECT 1 AS id")
    con.close()
    catalog._cache["key"] = None
    with ro(env.db) as con:
        cat = catalog.build(con, env.db)
    assert list(cat["tables"]) == [("main", "t")] and cat["tables"][("main", "t")]["kind"] == "local"
    assert client(env).get("/api/remote").json()["sources"] == []


# ------------------------------------------------------------------ phase 2: remote profiling + key fingerprints
def _pms_tables():
    import datetime as dt
    n_g, n_r = 300, 1000
    guest = pa.table({"guest_id": [f"G{i:04d}" for i in range(1, n_g + 1)],
                      "email_address": [f"guest{i}@example.com" if i % 10 else None for i in range(1, n_g + 1)],
                      "nationality": [["HK", "GB", "US", "CN"][i % 4] for i in range(n_g)]})
    reservation = pa.table({
        "reservation_id": pa.array(range(1, n_r + 1), pa.int64()),
        "guest_id": [f"G{(i * 7) % n_g + 1:04d}" if i % 200 else f"GX{i}" for i in range(n_r)],   # 5 orphans
        "property_code": [["HKG", "LON", "NYC", "BKK", "TYO"][i % 5] for i in range(n_r)],
        "status": ["RSV"] * n_r,
        "arrival_date": pa.array([dt.date(2026, 1, 1) + dt.timedelta(days=i % 200) for i in range(n_r)], pa.date32()),
        "room_revenue": pa.array([100.0 + (i % 37) * 12.5 for i in range(n_r)], pa.float64()),
        "notes": pa.array([None] * n_r, pa.string()),
    })
    prop = pa.table({"property_code": ["HKG", "LON", "NYC", "BKK", "TYO"], "property_name": ["Hong Kong", "London", "New York", "Bangkok", "Tokyo"]})
    # like a real exchange-rate table: a value larger than the column's declared DECIMAL(18,10) allows
    import decimal
    rates = [decimal.Decimal(x) for x in ["7.8", "0.1282", "183823530.0", "1.0", "15.2"] * 4]
    fx = pa.table({"currency_code": [c for c in ["HKD", "USD", "IDR", "GBP", "CNY"] * 4],
                   "rate_date": pa.array([dt.date(2026, 1, 1 + i // 5) for i in range(20)], pa.date32()),
                   "rate": pa.array(rates, pa.decimal128(38, 10)).cast(pa.decimal128(18, 10), safe=False)})
    return {"guest": guest, "reservation": reservation, "property": prop, "exchangerate": fx}


def _uc_from_arrow(tables):
    spark = {"int64": "bigint", "string": "string", "date32[day]": "date", "double": "double", "decimal128(18, 10)": "decimal(18,10)"}
    out = {name: tbl(name, [col(f.name, spark[str(f.type)], i) for i, f in enumerate(t.schema)]) for name, t in tables.items()}
    for name, t in tables.items():
        out[name].properties = {"spark.sql.statistics.numRows": str(t.num_rows)}
    return out


@pytest.fixture()
def pms_data(env):
    tables = _pms_tables()
    for k, v in tables.items():
        ROWS[f"bronze_pms.{k}"] = v
    env.uc.schemas_data[("lakehouse", "bronze_pms")] = _uc_from_arrow(tables)
    yield env
    for k in tables:
        ROWS.pop(f"bronze_pms.{k}", None)


@pytest.fixture()
def pms(pms_data):
    env = pms_data
    env.run("remote", "add", "dev", "--host", "https://adb-1.azuredatabricks.net", "--warehouse", "wh1")
    r = env.run("attach", "dev", "lakehouse.bronze_pms", "--as", "pms_dbx")
    assert r.exit_code == 0, r.output
    yield env


def test_remote_profile_fingerprints_relationships(pms):
    env = pms
    r = env.run("profile")
    assert "only when named" in r.output, r.output                     # never hits the warehouse by surprise
    r = env.run("profile", "-s", "pms_dbx", "--sample-rows", "400")
    assert r.exit_code == 0 and "4/4" in r.output, r.output
    assert "rate: values exceed its declared DECIMAL(18,10)" in r.output
    assert "1,000 rows (sample" in r.output                              # big table sampled, small ones read whole
    sqls = "\n".join(env.sql_log)
    assert "approx_count_distinct(`reservation_id`) AS _c" in sqls and "count(DISTINCT `reservation_id`) AS _d0" in sqls
    assert "count(*) FROM `lakehouse`.`bronze_pms`.`guest`" in sqls and "SELECT DISTINCT CAST(`guest_id` AS STRING)" in sqls

    c = client(env)
    t = c.get("/api/table/pms_dbx/reservation").json()
    assert t["kind"] == "remote" and t["row_count"] == 1000 and t["profiled"]
    cols = {x["column"]: x for x in t["columns"]}
    assert "candidate_pk" in cols["reservation_id"]["flags"]             # exact distinct over the whole table
    assert "all_null" in cols["notes"]["flags"] and "constant" in cols["status"]["flags"]
    fk_vals = set(ROWS["bronze_pms.reservation"].column("guest_id").to_pylist())
    fk_hit = fk_vals & set(ROWS["bronze_pms.guest"].column("guest_id").to_pylist())
    assert cols["notes"]["null_pct"] == 100.0 and cols["guest_id"]["distinct_count"] == len(fk_vals)   # exact, from the fingerprint
    assert t["table_profile"]["sampled_rows"] == 400 and t["table_profile"]["row_count"] == 1000
    g = {x["column"]: x for x in c.get("/api/table/pms_dbx/guest").json()["columns"]}
    assert "candidate_pk" in g["guest_id"]["flags"] and "pii_email" in g["email_address"]["flags"]
    prof = c.get("/api/table/pms_dbx/guest/profile").json()
    assert prof["stored"] and prof["columns"][0]["top_values"] == []      # unique column: no top values
    assert c.get("/api/table/pms_dbx/guest/profile", params={"live": True}).status_code == 409

    # relationships between remote tables, from fingerprints (no rows locally)
    r = env.run("relate", "-s", "pms_dbx")
    assert r.exit_code == 0, r.output
    rels = {(x["from_table"], x["from_column"], x["to_table"], x["to_column"]): x for x in c.get("/api/relationships").json()}
    fk = rels[("reservation", "guest_id", "guest", "guest_id")]
    assert fk["overlap_pct"] == pytest.approx(len(fk_hit) / len(fk_vals) * 100, abs=0.01)
    assert ("reservation", "property_code", "property", "property_code") in rels
    ov = c.get("/api/overlap", params={"left": "pms_dbx.reservation.guest_id", "right": "pms_dbx.guest.guest_id"}).json()
    assert ov["via_fingerprints"] and ov["complete"] and ov["left_orphans"][0].startswith("GX")

    # cross-system: a local CRM export against the remote PMS
    import csv
    (env.tmp / "crm").mkdir()
    with open(env.tmp / "crm" / "customer.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["CustomerId", "PmsGuestCode"])
        for i in range(1, 151):
            w.writerow([f"C{i}", f"G{(i % 100 + 1) * 2:04d}"])   # duplicate customers, like a real CRM
    assert env.run("load", str(env.tmp / "crm"), "--schema", "crm").exit_code == 0
    assert env.run("profile", "-s", "crm").exit_code == 0
    r = env.run("relate", "--deep", "-s", "crm", "-s", "pms_dbx")
    assert "customer.PmsGuestCode" in r.output and "guest.guest_id" in r.output, r.output

    # value search finds remote key values and top values from the local cache
    vs = c.get("/api/search", params={"q": "G0007", "mode": "value", "exact": True}).json()
    hit = {(t["schema"], t["table"]): t for t in vs["tables"]}
    assert ("pms_dbx", "guest") in hit and hit[("pms_dbx", "guest")]["matched_columns"][0]["cached"]
    assert vs["skipped_remote"] == 0
    vs = c.get("/api/search", params={"q": "LON", "mode": "value", "exact": True}).json()
    assert {"reservation", "property"} <= {t["table"] for t in vs["tables"]}

    # a schema change upstream makes the profile stale; --only-stale re-profiles just that table
    env.uc.schemas_data[("lakehouse", "bronze_pms")]["guest"].comment = "Guest master"
    ROWS["bronze_pms.guest"] = ROWS["bronze_pms.guest"]
    assert env.run("sync").exit_code == 0
    assert client(env).get("/api/table/pms_dbx/guest").json()["table_profile"]["stale"]
    n = len(env.sql_log)
    r = env.run("profile", "-s", "pms_dbx", "--only-stale")
    assert "1/1" in r.output and "pms_dbx.guest" in r.output, r.output
    assert all("reservation" not in q for q in env.sql_log[n:])

    # the web app can run it as a job
    c = client(env)
    job = c.post("/api/remote/profile", json={"tables": ["pms_dbx.property"], "wait": True}).json()
    assert job["status"] == "done" and job["results"][0]["rows"] == 5
    ov = c.get("/api/remote").json()["sources"]
    assert {s["alias"]: s["profiled"] for s in ov}["pms_dbx"] == 4
    fx = {x["column"]: x for x in c.get("/api/table/pms_dbx/exchangerate").json()["columns"]}
    assert "precision_overflow" in fx["rate"]["flags"] and fx["rate"]["profile"]["max_val"].startswith("183823530")


# ------------------------------------------------------------------ phase 3: live queries on the warehouse
def test_live_remote_queries(pms):
    env = pms
    c = client(env)
    r = c.get("/api/table/pms_dbx/reservation/sample", params={"n": 5, "nonnull": "guest_id", "where": "status = 'RSV'"})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["remote"] and len(s["rows"]) == 5 and s["columns"][0] == "reservation_id"
    assert "TABLESAMPLE (10.0 PERCENT) WHERE `guest_id` IS NOT NULL AND (status = 'RSV') LIMIT 5" in s["sql"]   # no full sort
    assert c.get("/api/table/pms_dbx/reservation/sample", params={"where": "1=1; DROP TABLE x"}).status_code == 400

    u = c.post("/api/table/pms_dbx/reservation/uniqueness", json={"columns": ["reservation_id"]}).json()
    assert u["is_unique"] and u["rows"] == 1000
    u = c.post("/api/table/pms_dbx/reservation/uniqueness", json={"columns": ["guest_id"]}).json()
    assert not u["is_unique"] and u["duplicate_examples"] and u["duplicate_examples"][0][-1] > 1

    lk = c.post("/api/lookup", json={"targets": [{"schema": "pms_dbx", "table": "reservation", "columns": ["guest_id"]},
                                                 {"schema": "pms_dbx", "table": "guest", "columns": ["guest_id"]}],
                                     "op": "=", "value": "g0008, G0009", "limit": 3}).json()
    res = {x["table"]: x for x in lk["results"]}
    assert res["guest"]["count"] == 2 and res["reservation"]["count"] > 2 and len(res["reservation"]["rows"]) == 3
    assert "lower(trim(`guest_id`)) IN ('g0008', 'g0009')" in res["reservation"]["sql"]
    lk = c.post("/api/lookup", json={"targets": [{"schema": "pms_dbx", "table": "reservation", "columns": ["arrival_date"]}],
                                     "op": ">=", "value": "2026-07-01"}).json()
    assert lk["results"][0]["count"] > 0 and not lk["results"][0].get("error")

    vs = c.get("/api/search", params={"q": "G0007", "mode": "value", "exact": True, "remote": True}).json()
    live = {t["table"]: t for t in vs["tables"] if t.get("live")}
    assert {"guest", "reservation"} <= set(live) and live["guest"]["matched_columns"][0]["examples"] == ["G0007"]
    assert vs["remote_searched"] == 4 and not vs["remote_errors"]

    q = c.post("/api/sql", json={"engine": "databricks:dev", "sql": "SELECT count(*) AS n FROM pms_dbx.reservation WHERE status <> 'pms_dbx.x'"}).json()
    assert q["rows"] == [[1000]] and "`lakehouse`.`bronze_pms`.`reservation`" in q["sql"] and "'pms_dbx.x'" in q["sql"]
    bad = c.post("/api/sql", json={"engine": "databricks:dev", "sql": "WITH x AS (SELECT 1) INSERT INTO t SELECT * FROM x"})
    assert bad.status_code == 400 and "Read-only" in bad.json()["detail"]
    err = c.post("/api/sql", json={"engine": "databricks:dev", "sql": "SELECT nope FROM pms_dbx.reservation"})
    assert err.status_code == 400 and err.json()["detail"].startswith("Databricks:")


# ------------------------------------------------------------------ fewer steps + speed
def test_connect_wizard_and_refresh(pms_data):
    env = pms_data
    # scripted: one command from nothing to attached, profiled, related and partly local
    r = env.run("connect", "--host", "adb-1.azuredatabricks.net", "-c", "lakehouse", "-s", "bronze_pms", "--prefix", "dev_",
                "--profile", "--pull-max-rows", "400", "-y")
    assert r.exit_code == 0, r.output
    assert "signed in as bruce@example.com" in r.output and "Serverless Starter Warehouse" in r.output
    assert "[4/4]" in r.output and "relationships found" in r.output
    assert "3 cached whole, 1 as a sample" in r.output
    c = client(env)
    storage = {t["table"]: t["storage"] for t in c.get("/api/tables").json() if t["schema"] == "dev_bronze_pms"}
    assert storage == {"guest": "cached", "property": "cached", "exchangerate": "cached", "reservation": "sample"}
    resv = c.get("/api/table/dev_bronze_pms/reservation").json()
    assert resv["row_count"] == 1000 and resv["cached_rows"] == 400
    assert resv["table_profile"]["row_count"] == 1000        # whole-table profile from Databricks, not the sample's
    assert cx.get("databricks").warehouse_id == "4b9e1c0f2a7d6e53"
    rels = {(x["from_table"], x["from_column"], x["to_table"]) for x in c.get("/api/relationships").json()}
    assert ("reservation", "guest_id", "guest") in rels
    assert c.get("/api/table/dev_bronze_pms/guest").json()["table_profile"]     # copies are profiled right away

    # running it again re-syncs instead of attaching twice
    r = env.run("connect", "--name", "databricks", "-c", "lakehouse", "-s", "bronze_pms", "--no-profile", "--pull-max-rows", "0", "-y")
    assert r.exit_code == 0 and "already attached as dev_bronze_pms" in r.output, r.output

    # refresh: sync + re-profile only what changed + relationships
    env.uc.schemas_data[("lakehouse", "bronze_pms")]["reservation"].comment = "Stays"
    n = len(env.sql_log)
    r = env.run("refresh")
    assert r.exit_code == 0 and "table comment changed" in r.output and "✓ dev_bronze_pms.reservation" in r.output, r.output
    assert not any("`property`" in q and not q.startswith("DESCRIBE HISTORY") for q in env.sql_log[n:])


def test_connect_interactive(pms_data):
    env = pms_data
    answers = "\n".join(["adb-1.azuredatabricks.net", "dev", "1", "bronze_pms", "", "y", "n", "n"]) + "\n"
    r = CliRunner().invoke(__import__("bearings.cli", fromlist=["app"]).app, ["connect"], input=answers)
    assert r.exit_code == 0, r.output
    assert "Catalog" in r.output and "bronze_pms" in r.output and "Ready." in r.output
    c = client(env)
    assert "bronze_pms" in c.get("/api/stats").json()["schemas"]


def test_speed_features(pms):
    env = pms
    from bearings.remote import query as rq
    # warm-up wakes the warehouse; status reports it
    c = client(env)
    assert rq.warm("dev", background=False)["state"] == "ready"
    assert c.get("/api/remote/warm").json()["dev"]["state"] == "ready"
    # lookup: rows + total in one query
    n = len(env.sql_log)
    lk = c.post("/api/lookup", json={"targets": [{"schema": "pms_dbx", "table": "reservation", "columns": ["guest_id"]}],
                                     "op": "=", "value": "G0008", "limit": 2}).json()["results"][0]
    assert lk["count"] > 2 and len(lk["rows"]) == 2 and len(lk["rows"][0]) == 7
    assert len(env.sql_log) - n == 1 and "count(*) OVER ()" in env.sql_log[-1]
    # identical lookups within the TTL come from the cache
    c.post("/api/lookup", json={"targets": [{"schema": "pms_dbx", "table": "reservation", "columns": ["guest_id"]}],
                                "op": "=", "value": "G0008", "limit": 2})
    assert len(env.sql_log) - n == 1
    # batch pull of small tables, whole; bigger ones stay live
    r = env.run("pull", "-s", "pms_dbx", "--max-rows", "400")
    assert r.exit_code == 0 and "3 table(s) copied" in r.output and "stays remote" in r.output, r.output
    job = c.post("/api/remote/pull", json={"tables": ["pms_dbx.reservation"], "rows": 50, "wait": True}).json()
    assert job["status"] == "done" and job["results"][0]["rows"] == 50
    assert client(env).get("/api/table/pms_dbx/reservation").json()["kind"] == "local"
    # dropping the local copy (as the README says) puts the table back to live/remote
    assert env.run("drop", "pms_dbx.reservation", "-y").exit_code == 0
    assert client(env).get("/api/table/pms_dbx/reservation").json()["kind"] == "remote"


# ------------------------------------------------------------------ local-first cache + Remote on demand
def test_local_first_cache_and_remote_toggle(pms):
    env = pms
    r = env.run("profile", "-s", "pms_dbx", "--sample-rows", "400")
    assert r.exit_code == 0, r.output
    r = env.run("cache", "-s", "pms_dbx", "--max-rows", "400")
    assert r.exit_code == 0 and "3 cached whole, 1 cached as a sample" in r.output, r.output
    c = client(env)
    t = c.get("/api/table/pms_dbx/reservation").json()
    assert t["storage"] == "sample" and t["row_count"] == 1000 and t["cached_rows"] == 400
    assert t["table_profile"]["row_count"] == 1000            # the exact whole-table profile from Databricks is kept
    assert "candidate_pk" in {c_["column"]: c_ for c_ in t["columns"]}["reservation_id"]["flags"]
    assert c.get("/api/table/pms_dbx/guest").json()["storage"] == "cached"

    # queries run locally by default …
    n = len(env.sql_log)
    s1 = c.get("/api/table/pms_dbx/reservation/sample", params={"n": 5}).json()
    u1 = c.post("/api/table/pms_dbx/guest/uniqueness", json={"columns": ["guest_id"]}).json()
    assert s1["source"] == "sample" and s1["cached_rows"] == 400 and u1["source"] == "cached" and u1["is_unique"]
    lk = c.post("/api/lookup", json={"targets": [{"schema": "pms_dbx", "table": "reservation", "columns": ["guest_id"]}],
                                     "op": "=", "value": "G0008"}).json()["results"][0]
    assert lk["source"] == "sample" and not lk.get("remote")
    assert len(env.sql_log) == n                                   # nothing went to Databricks
    # … and on Databricks when asked for
    s2 = c.get("/api/table/pms_dbx/reservation/sample", params={"n": 5, "remote": True}).json()
    u2 = c.post("/api/table/pms_dbx/reservation/uniqueness", json={"columns": ["reservation_id"], "remote": True}).json()
    lk2 = c.post("/api/lookup", json={"targets": [{"schema": "pms_dbx", "table": "reservation", "columns": ["guest_id"]}],
                                      "op": "=", "value": "G0008", "remote": True}).json()["results"][0]
    assert s2["source"] == "remote" and u2["source"] == "remote" and u2["rows"] == 1000 and lk2["source"] == "remote"
    assert lk2["count"] >= lk["count"] and len(env.sql_log) > n
    # value search: hits in a cached sample are marked partial; remote=true searches sample-cached tables live
    vs = c.get("/api/search", params={"q": "RSV", "mode": "value", "exact": True}).json()
    resv = next(x for x in vs["tables"] if x["table"] == "reservation")
    assert resv["partial"] and resv["matched_columns"][0]["matched_by"] == "value (cached sample)"
    vs = c.get("/api/search", params={"q": "RSV", "mode": "value", "exact": True, "remote": True}).json()
    assert next(x for x in vs["tables"] if x["table"] == "reservation").get("live")

    # the cache size is remembered per schema; --drop empties the cache (tables run live again)
    from bearings.db import connect as dbconnect
    con = dbconnect(env.db, read_only=True)
    assert con.execute("SELECT cache_max_rows FROM _meta.remote_sources WHERE alias='pms_dbx'").fetchone()[0] == 400
    con.close()
    r = env.run("cache", "-s", "pms_dbx", "--drop")
    assert r.exit_code == 0 and "Removed 4 cached table(s)" in r.output, r.output
    t = client(env).get("/api/table/pms_dbx/reservation").json()
    assert t["storage"] == "remote" and t["table_profile"]["row_count"] == 1000   # profile survives the cache


# ------------------------------------------------------------------ PII masking, data freshness, join-consistent samples
def test_pii_masking_in_cache(pms):
    env = pms
    assert env.run("profile", "-s", "pms_dbx").exit_code == 0
    assert env.run("cache", "-s", "pms_dbx", "--max-rows", "400").exit_code == 0
    import duckdb
    con = duckdb.connect(str(env.db), read_only=True)
    raw = con.execute("SELECT email_address FROM pms_dbx.guest WHERE email_address IS NOT NULL LIMIT 1").fetchone()[0]
    con.close()
    assert raw.startswith("guest")                                  # masking is off by default for `cache`

    r = env.run("cache", "-s", "pms_dbx", "--mask-pii")
    assert r.exit_code == 0 and "PII masking on" in r.output, r.output
    con = duckdb.connect(str(env.db), read_only=True)
    emails = [x for (x,) in con.execute("SELECT email_address FROM pms_dbx.guest WHERE email_address IS NOT NULL").fetchall()]
    prof = con.execute("SELECT top_values, min_val FROM _meta.column_profile WHERE schema_name='pms_dbx' AND table_name='guest' "
                       "AND column_name='email_address'").fetchone()
    con.close()
    assert all(e.startswith("pii_") and e.endswith("@example.com") for e in emails)   # hashed, domain kept
    assert "guest" not in (prof[0] + (prof[1] or ""))                                 # stored profile scrubbed too
    c = client(env)
    g = c.get("/api/table/pms_dbx/guest").json()
    assert "email_address" in g["remote"]["cache"]["masked"] and "nationality" not in g["remote"]["cache"]["masked"]
    # a lookup with the real value still finds the (hashed) row, because the value is hashed the same way
    lk = c.post("/api/lookup", json={"targets": [{"schema": "pms_dbx", "table": "guest", "columns": ["email_address"]}],
                                     "op": "=", "value": "guest7@example.com"}).json()["results"][0]
    assert lk["count"] == 1 and lk["source"] == "cached"
    # re-caching keeps masking (remembered per schema) – even though hashed values no longer look like e-mail
    r = env.run("cache", "-s", "pms_dbx", "-t", "pms_dbx.guest", "--refresh")
    assert "PII col(s) masked" in r.output, r.output


def test_freshness_recaches_changed_data(pms):
    env = pms
    assert env.run("profile", "-s", "pms_dbx").exit_code == 0
    assert env.run("cache", "-s", "pms_dbx", "--max-rows", "400").exit_code == 0
    c = client(env)
    assert c.get("/api/table/pms_dbx/guest").json()["remote"]["cache"]["version"] == 1
    VERSIONS["bronze_pms.guest"] = 5                                 # new data written to guest on Databricks
    try:
        n = len(env.sql_log)
        r = env.run("refresh")
        assert r.exit_code == 0 and "pms_dbx.guest: data changed (version 1 → 5)" in r.output, r.output
        assert "1 table(s) with new data" in r.output and "1 re-cached" in r.output
        pulled = [q for q in env.sql_log[n:] if q.startswith("SELECT * FROM")]
        assert pulled and all("`guest`" in q for q in pulled)       # only the changed table came back down
        g = client(env).get("/api/table/pms_dbx/guest").json()["remote"]["cache"]
        assert g["version"] == 5 and not g["outdated"]
    finally:
        VERSIONS.clear()


def test_join_consistent_samples(pms):
    env = pms
    assert env.run("profile", "-s", "pms_dbx").exit_code == 0
    assert env.run("relate", "-s", "pms_dbx").exit_code == 0
    r = env.run("cache", "-s", "pms_dbx", "--max-rows", "250")      # guest (300) and reservation (1000) both too big
    assert r.exit_code == 0 and "keyed on guest_id" in r.output, r.output
    import duckdb
    con = duckdb.connect(str(env.db), read_only=True)
    n_res, orphans = con.execute("""SELECT count(*), count(*) FILTER (WHERE g.guest_id IS NULL AND r.guest_id NOT LIKE 'GX%')
                                    FROM pms_dbx.reservation r LEFT JOIN pms_dbx.guest g USING (guest_id)""").fetchone()
    con.close()
    assert n_res > 0 and orphans == 0                                 # every cached reservation finds its cached guest
    t = client(env).get("/api/table/pms_dbx/reservation").json()
    assert t["storage"] == "sample" and t["remote"]["cache"]["method"].startswith("key:guest_id")


def test_pii_rules_are_narrow():
    from bearings.remote.pii import _reason
    masked = {"EmailAddress", "PhoneNumber", "FirstName", "LastName", "BirthDate", "AddressLine1", "CardNumber", "PassportNo",
              "MobilePhone", "GuestName"}
    kept = {"EmailAddressID", "EmailTypeCode", "PhoneType", "NameCode", "PostalCode", "City", "PropertyName", "OrganizationName",
            "IsPrimaryEmail", "EmailPrimaryFlag", "InsertDate", "ProfileID", "UpdateDate"}
    types = {"BirthDate": "DATE", "EmailAddressID": "BIGINT", "IsPrimaryEmail": "BOOLEAN", "InsertDate": "TIMESTAMP"}
    for c in masked:
        assert _reason(c, types.get(c, "STRING"), [], ""), c
    for c in kept:
        assert _reason(c, types.get(c, "STRING"), [], "") is None, c
    assert _reason("Value", "STRING", ["pii_email"], "")                     # content wins over the name
    assert _reason("FirstName", "STRING", [], "no-pii") is None               # tags override
    assert _reason("Remarks", "STRING", [], "PII, contact")


def test_pii_command_and_keep(pms):
    env = pms
    assert env.run("profile", "-s", "pms_dbx").exit_code == 0
    assert env.run("cache", "-s", "pms_dbx", "--max-rows", "400", "--mask-pii").exit_code == 0
    r = env.run("pii", "-s", "pms_dbx")
    assert r.exit_code == 0 and "email_address" in r.output and "values look like e-mail" in r.output, r.output
    assert "guest_id" not in r.output and "nationality" not in r.output
    r = env.run("pii", "--keep", "pms_dbx.guest.email_address")
    assert "tagged pms_dbx.guest.email_address no-pii" in r.output and "re-cache to restore" in r.output, r.output
    assert env.run("cache", "-s", "pms_dbx", "-t", "pms_dbx.guest", "--refresh").exit_code == 0
    import duckdb
    con = duckdb.connect(str(env.db), read_only=True)
    e = con.execute("SELECT email_address FROM pms_dbx.guest WHERE email_address IS NOT NULL LIMIT 1").fetchone()[0]
    con.close()
    assert e.startswith("guest")                                             # readable again after the re-cache


# column names in the style of a hotel PMS: masked (1) or kept readable (0)
PMS_PII_CASES = [
    ("guestnameinfo", "FirstName", "STRING", [], 1), ("guestnameinfo", "PassportNumber", "STRING", [], 1),
    ("guestnameinfo", "DateOfBirth", "DATE", [], 1), ("guestnameinfo", "MigrationCardNumber", "STRING", [], 1),
    ("guestnameinfo", "PassportVisaCheck", "STRING", [], 0), ("guestnameinfo", "PassportType", "STRING", [], 0),
    ("guestnameinfo", "BirthCity", "STRING", [], 1), ("guestnameinfo", "StreetNumber", "STRING", [], 1),
    ("guestnameinfo", "EmailType", "STRING", [], 0), ("guestnameinfo", "MobileCountryCode", "STRING", [], 0),
    ("guestnameinfo", "PostalCode", "STRING", [], 0), ("profile", "BirthDay", "INT", [], 1), ("profile", "TaxID2", "STRING", [], 1),
    ("profile", "WebSiteAddress", "STRING", [], 0), ("profile", "AutoEmailFolio", "STRING", [], 0), ("profile", "IsEmailOptIn", "STRING", [], 0),
    ("x5account", "ACC_EMAILADDRESS", "STRING", [], 1), ("x5account", "ACC_ZIPCODE", "STRING", [], 0),
    ("phonenumber", "CountryAccessNumber", "STRING", [], 0), ("phonenumber", "PhoneExtension", "STRING", [], 0),
    ("phonenumber", "PhoneNumber", "STRING", [], 1), ("property", "PhoneNumber", "STRING", [], 0), ("organization", "StreetAddress", "STRING", [], 0),
    ("y5organization", "ORG_EMAILCONFBODY", "STRING", [], 0), ("y5organization", "ORG_RESVEEMAILADD", "STRING", ["pii_email"], 0),
    ("travelagency", "StreetAddress", "STRING", [], 0), ("x5room", "ROO_PHONENUMBER", "STRING", [], 0),
    ("x5transactioncode", "TRC_MERCHANTPHONE", "STRING", [], 0), ("x5personnel", "PER_MASKGUESTNAME", "STRING", [], 0),
    ("y5users", "USR_FIRSTNAME", "STRING", [], 1), ("reservation", "ConfirmationEmail", "STRING", [], 1),
    ("reservation", "CreditCardID", "BIGINT", [], 0), ("ar_account", "SettlementCreditCardId", "STRING", [], 0),
    ("x5profilecontactdetails", "PCD_EMAILADDRESSID2", "STRING", [], 0), ("x5groupbookings", "GRB_BILLINGEMAILADDRESS", "STRING", [], 1),
    ("x5groupbookings", "GRB_CANCELLATIONNUMBER", "STRING", [], 0),
]


@pytest.mark.parametrize("table,col,dtype,flags,masked", PMS_PII_CASES)
def test_pii_rules_on_pms_names(table, col, dtype, flags, masked):
    from bearings.remote.pii import _reason
    assert bool(_reason(col, dtype, flags, "", table)) == bool(masked), (table, col, _reason(col, dtype, flags, "", table))
