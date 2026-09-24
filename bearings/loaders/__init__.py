"""Local file readers for `bearings load`, behind one small interface (`base.FileReader`).

Built in: CSV/TSV, Parquet, JSON/NDJSON and Excel. To add a format, subclass `FileReader`
(set `name`, `extensions`, and implement `relation`) and call `register(MyReader())`.
"""
from __future__ import annotations

from pathlib import Path

from .base import FileReader, LoadItem, LoadOptions
from .excel import ExcelReader
from .formats import CsvReader, JsonReader, ParquetReader

_readers: list[FileReader] = []


def register(reader: FileReader, first: bool = False) -> None:
    """Add a reader. Earlier readers win when several claim the same file or folder."""
    global _readers
    _readers = [r for r in _readers if r.name != reader.name]
    _readers.insert(0, reader) if first else _readers.append(reader)


def readers() -> list[FileReader]:
    return list(_readers)


def get(name: str) -> FileReader:
    for r in _readers:
        if r.name == name:
            return r
    raise KeyError(name)


def reader_for(p: Path) -> FileReader | None:
    for r in _readers:
        if r.matches(p):
            return r
    return None


def supported_extensions() -> list[str]:
    return [e for r in _readers for e in r.extensions]


# Parquet first: a Spark export folder can hold both part-*.parquet and stray .crc / .json files
for _r in (ParquetReader(), CsvReader(), JsonReader(), ExcelReader()):
    register(_r)

__all__ = ["FileReader", "LoadItem", "LoadOptions", "register", "readers", "get", "reader_for", "supported_extensions"]
