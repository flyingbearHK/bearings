"""The remote-connector abstraction: a second, non-Databricks connector plugs in without touching Bearings.

The test connector serves a DuckDB file as a "remote platform" with plain ANSI SQL (double-quoted names,
no TABLESAMPLE, no count_if), so every remote code path is exercised with a dialect other than Databricks.
"""
from __future__ import annotations

import importlib
from contextlib import suppress
from types import SimpleNamespace as NS

import duckdb
import pytest

pa = pytest.importorskip("pyarrow", reason="remote mode needs pyarrow (uv sync --extra databricks)")
from typer.testing import CliRunner

from bearings.remote import RemoteError, connectors
from bearings.remote import connections as cx
from bearings.remote.connectors import ConfigField, Connector, Dialect
from bearings.remote.connectors.databricks import DatabricksDialect


class DuckDialect(Dialect):
    name = "duckfile"

    def param(self, name):
        return f"${name}"


class _Cursor:
    def __init__(self, con, log):
        self.cur, self.log, self.tbl, self.pos = con.cursor(), log, None, 0

    def execute(self, sql, params=None):
        self.log.append(sql)
        res = self.cur.execute(sql, params or {})
        self.tbl, self.pos = (res.to_arrow_table() if hasattr(res, "to_arrow_table") else res.fetch_arrow_table()), 0

    def fetchone(self):
        return [self.tbl.column(i)[self.pos].as_py() for i in range(self.tbl.num_columns)]

    def fetchmany_arrow(self, n):
        b = self.tbl.slice(self.pos, n)
        self.pos += n
        return b

    def fetchall_arrow(self):
        b = self.tbl.slice(self.pos)
        self.pos = self.tbl.num_rows
        return b

    def close(self):
        self.cur.close()


class _Conn:
    def __init__(self, path, log):
        self.con, self.log = duckdb.connect(), log
        self.con.execute(f"ATTACH '{path}' AS remote (READ_ONLY)")

    def cursor(self):
        return _Cursor(self.con, self.log)

    def close(self):
        self.con.close()


class DuckFileConnector(Connector):
    type = "duckfile"
    label = "DuckFile"
    compute_label = "DuckDB engine"
    fields = (ConfigField("path", "DuckDB file standing in for a remote platform", required=True),)
    dialect = DuckDialect()
    log: list = []

    def _meta(self, sql, params=()):
        con = duckdb.connect()
        try:
            con.execute(f"ATTACH '{self.conn.path}' AS remote (READ_ONLY)")
            return con.execute(sql, list(params)).fetchall()
        finally:
            con.close()

    def whoami(self):
        return "tester"

    def list_catalogs(self):
        return ["remote"]

    def list_schemas(self, catalog):
        return [{"schema": s, "comment": None} for (s,) in self._meta(
            "SELECT schema_name FROM information_schema.schemata WHERE catalog_name='remote' AND schema_name NOT IN ('information_schema','pg_catalog')")]

    def fetch_schema(self, catalog, schema):
        rows = self._meta("""SELECT table_name, column_name, ordinal_position, data_type FROM information_schema.columns
                             WHERE table_catalog=? AND table_schema=? ORDER BY 1, 3""", (catalog, schema))
        if not rows:
            raise RemoteError(f"No schema {catalog}.{schema}", self.label)
        out = {}
        for t, c, o, dtp in rows:
            out.setdefault(t, {"table_type": "TABLE", "comment": None, "updated_at": None, "row_count": None, "size_bytes": None,
                               "columns": []})["columns"].append({"column_name": c, "ordinal": o, "data_type": dtp, "nullable": True, "comment": None})
        return out

    def sql_connect(self, session_configuration=None):
        return _Conn(self.conn.path, self.log)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BEARINGS_HOME", str(tmp_path / "home"))
    db = tmp_path / "data" / "t.duckdb"
    monkeypatch.setenv("BEARINGS_DB", str(db))
    src = tmp_path / "remote.duckdb"
    con = duckdb.connect(str(src))
    con.execute("CREATE SCHEMA sales")
    con.execute("""CREATE TABLE sales.orders AS SELECT range AS order_id, 'C' || (range % 50) AS customer_code,
                   DATE '2026-01-01' + CAST(range % 90 AS INTEGER) AS order_date, round(random() * 500, 2) AS amount
                   FROM range(2000)""")
    con.execute("CREATE TABLE sales.customer AS SELECT 'C' || range AS customer_code, 'Name ' || range AS name FROM range(50)")
    con.close()
    connectors.register(DuckFileConnector)
    DuckFileConnector.log = []
    from bearings.remote import query as rq
    rq.close_all()
    rq.clear_cache()
    cx.reset_clients()
    from bearings.cli import app
    yield NS(db=db, src=src, run=lambda *a: CliRunner().invoke(app, list(a)), log=DuckFileConnector.log)
    connectors._types.pop("duckfile", None)
    rq.close_all()
    cx.reset_clients()


def test_second_connector_end_to_end(env):
    r = env.run("remote", "add", "wh", "--type", "duckfile", "--set", f"path={env.src}")
    assert r.exit_code == 0, r.output
    assert 'type = "duckfile"' in cx.config_path().read_text()
    assert "duckfile" in env.run("remote", "list").output and "DuckFile" in env.run("remote", "types").output
    r = env.run("remote", "test", "wh", "--catalog", "remote")
    assert r.exit_code == 0 and "sales" in r.output and "DuckDB engine answered 1" in r.output, r.output

    r = env.run("attach", "wh", "remote.sales", "--as", "sales_wh")
    assert r.exit_code == 0 and "first sync" in r.output, r.output
    r = env.run("profile", "--remote", "-s", "sales_wh")
    assert r.exit_code == 0 and "✗" not in r.output, r.output
    assert any('"remote"."sales"."orders"' in q for q in env.log)             # ANSI quoting, not backticks
    assert not any("`" in q or "count_if" in q or "TABLESAMPLE" in q for q in env.log)

    import bearings.api as api
    importlib.reload(api)
    from bearings import catalog
    catalog._cache["key"] = None
    from fastapi.testclient import TestClient
    c = TestClient(api.app)

    t = c.get("/api/table/sales_wh/orders").json()
    assert t["kind"] == "remote" and t["remote"]["platform"] == "DuckFile" and t["table_profile"]["row_count"] == 2000
    assert "order_id" in t["table_profile"]["candidate_keys"]
    s = c.get("/api/table/sales_wh/orders/sample", params={"n": 5}).json()
    assert s["remote"] and len(s["rows"]) == 5 and "ORDER BY random()" in s["sql"]
    u = c.post("/api/table/sales_wh/customer/uniqueness", json={"columns": ["customer_code"]}).json()
    assert u["is_unique"] and u["rows"] == 50
    lk = c.post("/api/lookup", json={"targets": [{"schema": "sales_wh", "table": "orders", "columns": ["customer_code"]}],
                                     "op": "=", "value": "c7"}).json()["results"][0]
    assert lk["count"] == 40 and "lower(trim(\"customer_code\")) IN ('c7')" in lk["sql"]
    v = c.get("/api/search", params={"q": "C49", "mode": "value", "exact": True, "remote": True, "schemas": "sales_wh"}).json()
    assert {t_["table"] for t_ in v["tables"]} == {"orders", "customer"}
    q = c.post("/api/sql", json={"engine": "duckfile:wh", "sql": "SELECT count(*) AS n FROM sales_wh.customer"}).json()
    assert q["rows"] == [[50]] and q["engine"] == "duckfile:wh"
    err = c.post("/api/sql", json={"engine": "duckfile:wh", "sql": "SELECT nope FROM sales_wh.customer"})
    assert err.status_code == 400 and err.json()["detail"].startswith("DuckFile:")
    info = c.get("/api/remote").json()
    assert {"type": "duckfile", "label": "DuckFile"}.items() <= next(x for x in info["connections"] if x["name"] == "wh").items()

    # pull: a random sample without TABLESAMPLE falls back to ORDER BY random()
    r = env.run("pull", "sales_wh.orders", "--rows", "100")
    assert r.exit_code == 0, r.output
    con = duckdb.connect(str(env.db), read_only=True)
    try:
        assert con.execute("SELECT count(*) FROM sales_wh.orders").fetchone()[0] == 100
        assert con.execute("SELECT file_format FROM _meta.load_log WHERE table_name='orders'").fetchone()[0] == "duckfile"
    finally:
        con.close()


def test_dialects_and_profiles():
    d, b = Dialect(), DatabricksDialect()
    assert d.table_ref("c", "s", 't"x') == '"c"."s"."t""x"' and b.table_ref("c", "s", "t`x") == "`c`.`s`.`t``x`"
    assert d.count_if("a > 1") == "count(CASE WHEN a > 1 THEN 1 END)" and b.count_if("a > 1") == "count_if(a > 1)"
    assert d.tablesample(1.5) == "" and b.tablesample(1.5, 7) == " TABLESAMPLE (1.5 PERCENT) REPEATABLE (7)"
    assert b.hash_bucket("`k`", 100) == "pmod(xxhash64(CAST(`k` AS STRING)), 100)"
    with pytest.raises(RemoteError):
        d.hash_bucket("k", 10)
    assert [connectors.type_family(t) for t in ("STRING", "VARCHAR(20)", "DECIMAL(18,2)", "TIMESTAMP_NTZ", "ARRAY<INT>", "BOOLEAN")] == \
        ["string", "string", "numeric", "temporal", "other", "bool"]
    with pytest.raises(RemoteError):
        connectors.connector_class("nosuch")
    # profiles without a type are Databricks (files written by v0.2.0)
    import os
    import tempfile
    with tempfile.TemporaryDirectory() as h:
        old = os.environ.get("BEARINGS_HOME")
        os.environ["BEARINGS_HOME"] = h
        try:
            cx.config_path().parent.mkdir(parents=True, exist_ok=True)
            cx.config_path().write_text('[dev]\nhost = "https://adb-1.azuredatabricks.net"\nwarehouse_id = "wh1"\n')
            c = cx.get("dev")
            assert c.type == "databricks" and c.warehouse_id == "wh1" and c.auth_type == "external-browser"
            with pytest.raises(AttributeError):
                c.no_such_setting  # noqa: B018
            cx.upsert("dev", warehouse_id="wh2")
            assert 'type = "databricks"' in cx.config_path().read_text() and cx.get("dev").warehouse_id == "wh2"
        finally:
            if old is None:
                os.environ.pop("BEARINGS_HOME", None)
            else:
                os.environ["BEARINGS_HOME"] = old
            with suppress(Exception):
                cx.reset_clients()
