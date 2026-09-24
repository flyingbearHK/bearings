"""Built-in readers for formats DuckDB reads natively: CSV / TSV, Parquet and JSON."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from .base import FileReader, LoadItem, LoadOptions


class CsvReader(FileReader):
    name = "csv"
    label = "CSV / TSV"
    extensions = (".csv", ".csv.gz", ".tsv", ".tsv.gz", ".txt")
    folder_as_table = True

    @contextmanager
    def relation(self, con, item: LoadItem, opts: LoadOptions) -> Iterator[str]:
        o = ["header=true", "all_varchar=true" if opts.all_varchar else "sample_size=-1", "union_by_name=true"]
        if opts.delim:
            o.append("delim='" + opts.delim.replace("'", "''") + "'")
        yield f"read_csv({self.source_expr(item)}, {', '.join(o)})"


class ParquetReader(FileReader):
    name = "parquet"
    label = "Parquet"
    extensions = (".parquet", ".pq")
    folder_as_table = True

    @contextmanager
    def relation(self, con, item: LoadItem, opts: LoadOptions) -> Iterator[str]:
        yield f"read_parquet({self.source_expr(item)}, union_by_name=true, hive_partitioning=true)"


class JsonReader(FileReader):
    """JSON arrays / objects and newline-delimited JSON (Spark writes `part-*.json` as NDJSON)."""
    name = "json"
    label = "JSON / NDJSON"
    extensions = (".json", ".jsonl", ".ndjson", ".json.gz", ".jsonl.gz", ".ndjson.gz")
    folder_as_table = True

    @contextmanager
    def relation(self, con, item: LoadItem, opts: LoadOptions) -> Iterator[str]:
        o = ["format='auto'", "union_by_name=true", "sample_size=-1"]  # JSON strings stay strings, so leading zeros survive
        yield f"read_json_auto({self.source_expr(item)}, {', '.join(o)})"
