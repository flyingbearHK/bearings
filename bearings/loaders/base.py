"""The file-reader abstraction behind `bearings load`.

A `FileReader` knows one family of files (CSV, Parquet, Excel, JSON…):

- which files it reads (`extensions`),
- how a file, or a folder of part-files, maps to tables (`items_for_file` / `items_for_folder`),
- and how to expose one table's rows to DuckDB (`relation`: a context manager yielding a
  `SELECT`-able relation such as `read_parquet('…')`).

The loader (`bearings.loader`) only talks to readers through this interface, so adding a format is
one new module plus a `register()` call – see `bearings/loaders/__init__.py`.
"""
from __future__ import annotations

from abc import ABC
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar, Iterator

from ..db import safe_name


@dataclass
class LoadOptions:
    """Options for one `load` call. Readers ignore what doesn't apply to them."""
    all_varchar: bool = False            # keep raw text (leading zeros, odd formats)
    delim: str | None = None             # CSV delimiter when auto-detect fails
    sheets: list[str] = field(default_factory=list)   # Excel: only these sheets (case-insensitive)
    header_row: int | None = None        # Excel: 1-based header row (default: first non-empty row)


@dataclass
class LoadItem:
    """One table to create: where its rows come from and which reader reads them."""
    table: str                      # target table name (already safe)
    source: str                     # file, glob or file#sheet – shown and stored in _meta.load_log
    format: str                     # reader name, e.g. "csv", "excel"
    paths: list[Path]               # the file(s) behind it
    options: dict = field(default_factory=dict)   # reader-specific (e.g. {"sheet": "Bookings"})

    @property
    def label(self) -> str:
        return self.source if "*" in self.source else Path(self.source.split("#", 1)[0]).name + (
            f" [{self.options['sheet']}]" if self.options.get("sheet") else "")


def sql_str(s: str | Path) -> str:
    return "'" + str(s).replace("'", "''") + "'"


class FileReader(ABC):
    """Base class for a local file format."""

    name: ClassVar[str] = ""                  # short id, stored as the file_format in _meta.load_log
    label: ClassVar[str] = ""                 # for humans ("CSV / TSV")
    extensions: ClassVar[tuple[str, ...]] = ()
    folder_as_table: ClassVar[bool] = False   # a folder of these files (Spark part-files) is one table
    needs: ClassVar[str | None] = None        # optional Python module the reader needs (checked in `available`)

    # ---------------------------------------------------------------- matching
    def matches(self, p: Path) -> bool:
        n = p.name.lower()
        return n.endswith(self.extensions) and not n.startswith(("~$", ".", "_"))

    def stem(self, p: Path) -> str:
        n = p.name
        for ext in sorted(self.extensions, key=len, reverse=True):
            if n.lower().endswith(ext):
                return n[: -len(ext)]
        return p.stem

    @classmethod
    def available(cls) -> bool:
        if not cls.needs:
            return True
        try:
            __import__(cls.needs)
            return True
        except ImportError:
            return False

    # ---------------------------------------------------------------- tables
    def items_for_file(self, p: Path, opts: LoadOptions) -> list[LoadItem]:
        """Tables in one file (usually one, named after the file)."""
        return [LoadItem(safe_name(self.stem(p)), str(p), self.name, [p])]

    def items_for_folder(self, d: Path, files: list[Path], opts: LoadOptions) -> list[LoadItem]:
        """A folder of part-files → one table named after the folder (only when `folder_as_table`)."""
        exts = {next(e for e in sorted(self.extensions, key=len, reverse=True) if f.name.lower().endswith(e)) for f in files}
        if len(exts) == 1:
            return [LoadItem(safe_name(d.name), str(d / "**" / f"*{exts.pop()}"), self.name, files)]
        # mixed extensions (e.g. .csv and .csv.gz): read the exact file list
        return [LoadItem(safe_name(d.name), str(d / "**" / "*"), self.name, files, {"file_list": True})]

    def source_expr(self, item: LoadItem) -> str:
        """SQL for the file argument of a DuckDB table function: the glob / path, or a list of files."""
        if item.options.get("file_list") or ("*" not in item.source and len(item.paths) > 1):
            return "[" + ", ".join(sql_str(p) for p in item.paths) + "]"
        return sql_str(item.source)

    # ---------------------------------------------------------------- reading
    @contextmanager
    def relation(self, con, item: LoadItem, opts: LoadOptions) -> Iterator[str]:
        """Yield an SQL relation DuckDB can `SELECT * FROM` for this item. Readers that need to stage data
        (e.g. convert a sheet) do it here and clean up afterwards."""
        raise NotImplementedError  # pragma: no cover
        yield ""
