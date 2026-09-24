# Extension points: file readers and remote connectors

Bearings has two plug-in layers. Both are small registries of classes; the rest of the code only talks to the interface.

```
local files ──▶ bearings/loaders  (FileReader)  ──▶ loader.discover / load ──▶ DuckDB
remote      ──▶ bearings/remote/connectors (Connector + Dialect) ──▶ sync · profile · pull/cache · live queries
```

## 1. File readers (`bearings/loaders/`)

| Module | Reader | Notes |
|---|---|---|
| `formats.py` | `CsvReader`, `ParquetReader`, `JsonReader` | DuckDB table functions (`read_csv`, `read_parquet`, `read_json_auto`); a folder of part-files is one table |
| `excel.py` | `ExcelReader` | openpyxl (no DuckDB extension download); one table per non-empty sheet; types from Excel cell types |

A reader declares `name`, `label`, `extensions`, `folder_as_table`, and implements:

- `items_for_file(path, opts) -> [LoadItem]` – the tables in one file (default: one, named after the file; Excel: one per sheet).
- `items_for_folder(dir, files, opts) -> [LoadItem]` – a folder of part-files as one table (only when `folder_as_table`).
- `relation(con, item, opts)` – a context manager yielding SQL DuckDB can `SELECT * FROM` (e.g. `read_parquet('…')`). Readers that
  stage data (Excel writes a typed temporary CSV) do it here and clean up afterwards.

`loader.discover()` walks a path, asks the readers (in registry order) and returns `LoadItem`s with unique table names;
`loader.load()` creates the tables and writes `_meta.load_log` (the reader `name` is the `file_format`). A sub-folder is treated as
part-files only when it looks like one table (Spark `part-…` names, hive `key=value/` folders, numbered chunks, or one file);
otherwise its files load one by one.

```python
from contextlib import contextmanager
from bearings.loaders import FileReader, register

class PipeReader(FileReader):
    name, label, extensions = "pipe", "Pipe-delimited", (".psv",)

    @contextmanager
    def relation(self, con, item, opts):
        yield f"read_csv({self.source_expr(item)}, delim='|', header=true)"

register(PipeReader())
```

`ingest.run()` chains load → description files → profile → relationships (only pairs touching the loaded schema) with a short write
connection per step; the app's **Add data** dialog calls it through `POST /api/load` (background job, polled on `/api/jobs/{id}`).
Uploads (`POST /api/load/upload`, raw body, one file per request) land in `data/uploads/<batch>/`; path loading and the folder
browser (`/api/load/ls`) only answer requests from the local machine unless `BEARINGS_ALLOW_REMOTE_PATHS=1`.

## 2. Remote connectors (`bearings/remote/connectors/`)

A connection profile in `~/.bearings/connections.toml` names its connector with `type` (profiles without one are Databricks, so
v0.2 files keep working). Settings are connector-specific and never secrets.

```toml
[dev]
type = "databricks"
host = "https://adb-1234567890.12.azuredatabricks.net"
warehouse_id = "4b9e1c0f2a7d6e53"
```

### Connector

| Group | Method | Used by |
|---|---|---|
| install / config | `installed()`, `require()`, `validate()`, `describe()`, `can_query()`, `public_info()`, `fields` | `remote add/list/types/test`, `/api/remote` |
| metadata | `whoami()`, `list_catalogs()`, `list_schemas(catalog)`, `fetch_schema(catalog, schema)`, `list_compute()` | `connect`, `attach`, `sync` (cached in `_meta.remote_*`) |
| SQL | `sql_connect(session_config)`, `session_settings(timeout)`, `set_timeout_sql(timeout)`, `is_reconnectable(msg)`, `clean_error(msg)` | pooled sessions in `remote/query.py` |
| versions | `version_sql(table_ref)` → query with a `version` column; `table_version(cur, ref)` | outdated-cache detection (`refresh`) |

`fetch_schema` returns `{table: {table_type, comment, updated_at, row_count, size_bytes, columns: [{column_name, ordinal, data_type,
nullable, comment}]}}`. The cursor from `sql_connect(...).cursor()` must support `execute(sql, params)`, `fetchone()`,
`fetchall_arrow()`, `fetchmany_arrow(n)` and `close()` – the Databricks SQL connector does natively; wrap other drivers to match.

### Dialect

All remote SQL (samples, key checks, lookups, value search, whole-table profile statistics, key fingerprints, pulls, key-consistent
samples, alias expansion in the SQL console) is written through the connector's `Dialect`:

| Method | ANSI default | Databricks |
|---|---|---|
| `quote(name)` / `table_ref(c, s, t)` | `"x"` | `` `x` `` |
| `param(name)` | `:name` | `:name` |
| `cast_string(e)` / `try_cast(e, t)` | `CAST(e AS VARCHAR)` / `CAST` | `CAST(e AS STRING)` / `try_cast` |
| `count_if(c)` | `count(CASE WHEN c THEN 1 END)` | `count_if(c)` |
| `approx_distinct(e)` | `count(DISTINCT e)` | `approx_count_distinct(e)` |
| `ilike(e, p)` | `lower(e) LIKE lower(p)` | `e ILIKE p` |
| `tablesample(pct, seed)` | `''` → falls back to `ORDER BY random()` | `TABLESAMPLE (p PERCENT) REPEATABLE (s)` |
| `random_order(seed)` | `random()` | `rand(seed)` |
| `hash_bucket(e, n)` | not supported → plain random samples | `pmod(xxhash64(CAST(e AS STRING)), n)` |
| `type_family(t)` | engine-neutral: string / numeric / temporal / bool / other | same |

### Adding a platform

1. Subclass `Connector` (and `Dialect` where the SQL differs); set `type`, `label`, `extra`, `compute_label`, `fields`.
2. `register(MyConnector)` in `connectors/__init__.py` (built-in) or from your own code.
3. Put its Python dependencies in an optional extra in `pyproject.toml`.

`tests/test_connectors.py` registers a fake connector that serves a DuckDB file with plain ANSI SQL and runs attach → profile →
sample → key check → lookup → value search → SQL console → pull through it – a template for a real one. Candidates: Microsoft
Fabric / Synapse SQL endpoints (pyodbc + Entra ID), Snowflake, PostgreSQL.
