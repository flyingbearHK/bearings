"""Local file readers: CSV / Parquet / JSON / Excel discovery and loading."""
from __future__ import annotations

import datetime as dt
import json

import duckdb
import openpyxl
import pytest
from typer.testing import CliRunner

from bearings import loader
from bearings.db import connect
from bearings.loaders import FileReader, LoadOptions, get, readers, register
from bearings.loaders.excel import column_type, header_names


def _workbook(path, sheets: dict[str, list[list]]):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    wb.save(path)


@pytest.fixture()
def con(tmp_path):
    c = connect(tmp_path / "t.duckdb")
    yield c
    c.close()


def test_excel_types_names_and_sheets(tmp_path, con):
    _workbook(tmp_path / "Hotel Master.xlsx", {
        "Properties": [
            [None, None, None],                                   # blank rows before the header are skipped
            ["Code", "Name", "Opened", "Rooms", "Rate", "Active", "Code", None],
            ["00123", "Harbour View", dt.datetime(2019, 5, 1), 120, 1850.5, True, "HK1", None],
            ["00456", "Peak Lodge", dt.datetime(2021, 1, 15), 80, 990, False, "HK2", None],
            [None, None, None, None, None, None, None, None],     # empty row inside the data
            ["00789", "Bay Suites", dt.datetime(2022, 3, 3, 14, 30), 45, 1200, True, "HK3", None],
        ],
        "Notes": [["Remark"], ["mixed"], [42]],
        "Empty": [],
    })
    items = loader.discover(tmp_path)
    assert sorted(i.table for i in items) == ["hotel_master_notes", "hotel_master_properties"]  # empty sheet skipped

    res = loader.load(con, tmp_path, schema="ref", echo=lambda *_: None)
    assert all("error" not in r for r in res), res
    cols = dict(con.execute("SELECT column_name, data_type FROM information_schema.columns "
                            "WHERE table_schema='ref' AND table_name='hotel_master_properties' ORDER BY ordinal_position").fetchall())
    assert list(cols) == ["Code", "Name", "Opened", "Rooms", "Rate", "Active", "Code_2"]   # duplicate header de-duplicated
    assert cols["Code"] == "VARCHAR" and cols["Rooms"] == "BIGINT" and cols["Rate"] == "DOUBLE"
    assert cols["Opened"] == "TIMESTAMP" and cols["Active"] == "BOOLEAN"
    rows = con.execute('SELECT "Code", "Rooms" FROM ref.hotel_master_properties ORDER BY 1').fetchall()
    assert rows == [("00123", 120), ("00456", 80), ("00789", 45)]    # leading zeros kept, empty row dropped
    # a column mixing text and numbers is text; the number keeps its plain form
    assert con.execute("SELECT list(\"Remark\" ORDER BY \"Remark\") FROM ref.hotel_master_notes").fetchone()[0] == ["42", "mixed"]
    src = con.execute("SELECT source, file_format FROM _meta.load_log WHERE table_name='hotel_master_notes'").fetchone()
    assert src[0].endswith("Hotel Master.xlsx#Notes") and src[1] == "excel"


def test_excel_single_sheet_named_after_file_and_sheet_filter(tmp_path, con):
    _workbook(tmp_path / "rates.xlsx", {"Sheet1": [["rate_code", "amount"], ["BAR", 100]], "Old": [["x"], [1]]})
    items = loader.discover(tmp_path / "rates.xlsx", LoadOptions(sheets=["sheet1"]))
    assert [(i.table, i.options["sheet"]) for i in items] == [("rates", "Sheet1")]
    loader.load(con, tmp_path / "rates.xlsx", schema="ref", sheets=["Sheet1"], all_varchar=True, echo=lambda *_: None)
    assert con.execute("SELECT data_type FROM information_schema.columns WHERE table_name='rates' AND column_name='amount'").fetchone()[0] == "VARCHAR"
    assert con.execute("SELECT amount FROM ref.rates").fetchone()[0] == "100"


def test_excel_header_row_and_helpers(tmp_path, con):
    _workbook(tmp_path / "r.xlsx", {"S": [["Report title"], ["generated 2026-09-01"], ["id", "d"], [1, dt.datetime(2026, 1, 2)]]})
    loader.load(con, tmp_path / "r.xlsx", schema="x", header_row=3, echo=lambda *_: None)
    assert con.execute("SELECT id, d FROM x.r").fetchone() == (1, dt.date(2026, 1, 2))
    assert header_names(["a", None, "A", "a"]) == ["a", "column_2", "A_2", "a_3"]
    assert column_type({"int", "float"}) == "DOUBLE" and column_type({"date", "timestamp"}) == "TIMESTAMP"
    assert column_type({"int", "str"}) == "VARCHAR" and column_type(set()) == "VARCHAR"


def test_folders_json_and_legacy(tmp_path, con):
    exp = tmp_path / "exports"
    (exp / "reservation" / "_delta_log").mkdir(parents=True)
    duckdb.sql("COPY (SELECT range AS id FROM range(5)) TO '" + str(exp / "reservation" / "part-0.parquet") + "' (FORMAT parquet)")
    (exp / "reservation" / "_delta_log" / "0000.json").write_text("{}")
    (exp / "events").mkdir()
    (exp / "events" / "part-0.json").write_text("\n".join(json.dumps({"id": i, "code": f"0{i}"}) for i in range(3)))
    (exp / "books").mkdir()
    _workbook(exp / "books" / "a.xlsx", {"S": [["k"], ["v"]]})
    (exp / "guest.csv").write_text("guest_id,name\nG1,Ann\n")
    (exp / "old.xls").write_bytes(b"\xd0\xcf")
    (exp / "~$lock.xlsx").write_bytes(b"")
    msgs: list[str] = []
    found = {(i.table, i.format) for i in loader.discover(exp, echo=msgs.append)}
    assert found == {("reservation", "parquet"), ("events", "json"), ("a", "excel"), ("guest", "csv")}
    assert any("legacy .xls" in m for m in msgs)
    res = loader.load(con, exp, schema="src", echo=lambda *_: None)
    assert {r["table"]: r["rows"] for r in res if "error" not in r} == {"reservation": 5, "events": 3, "a": 1, "guest": 1}
    assert con.execute("SELECT code FROM src.events ORDER BY id").fetchall()[0] == ("00",)


def test_register_a_custom_reader(tmp_path, con):
    from contextlib import contextmanager

    class PipeReader(FileReader):
        name, label, extensions = "pipe", "Pipe-delimited", (".psv",)

        @contextmanager
        def relation(self, con, item, opts):
            yield f"read_csv({self.source_expr(item)}, delim='|', header=true)"

    register(PipeReader(), first=True)
    try:
        (tmp_path / "x.psv").write_text("a|b\n1|2\n")
        assert loader.load(con, tmp_path / "x.psv", schema="p", echo=lambda *_: None)[0]["rows"] == 1
        assert get("pipe").label == "Pipe-delimited"
    finally:
        import bearings.loaders as L
        L._readers = [r for r in readers() if r.name != "pipe"]


def test_cli_dry_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _workbook(tmp_path / "wb.xlsx", {"A": [["x"], [1]], "B": [["y"], [2]]})
    from bearings.cli import app
    r = CliRunner().invoke(app, ["load", str(tmp_path / "wb.xlsx"), "-s", "ref", "--dry-run", "--db", "t.duckdb"])
    assert r.exit_code == 0, r.output
    assert "ref.wb_a" in r.output and "ref.wb_b" in r.output and not (tmp_path / "t.duckdb").exists()
