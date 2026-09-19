# Design: Remote mode for Azure Databricks

Status: **Phases 1–3 implemented** (metadata sync, re-sync, orphaned annotations, pull; remote profiling, key fingerprints, relationships and value search on remote tables; live sample / key check / lookup / value search / SQL console on the warehouse) · Branch: `feature/databricks-remote` · 2026-09-19

## 1. Goal

Keep every local feature exactly as it is, and add Azure Databricks as a second kind of **source**. A remote schema behaves like a local one in the app. Its **metadata and profiles are cached in DuckDB**, so name search, profiles, annotations, exports and name-based relationships work offline. Only the actions that need **rows** go to Databricks.

Non-goals: writing to Databricks; bypassing Unity Catalog governance; one live query that joins a local table to a remote one.

## 2. Principles

1. **Metadata local, data remote.** Sync once, search locally; hit the warehouse only for rows.
2. **Opt-in.** Remote code sits behind the `databricks` extra (`uv sync --extra databricks`) and is off by default, so the README's "no outbound calls" still holds for local-only users.
3. **Governed access.** Every data query goes through a Databricks **SQL warehouse** as the signed-in user. Unity Catalog permissions, row filters and column masks apply, and queries are audited. We do **not** read Delta files directly from ADLS (DuckDB `delta`/`uc_catalog` extensions), because that skips row filters and masks.
4. **Same UI, same `_meta` tables.** Remote profiles go into `_meta.column_profile` / `table_profile`, so the UI doesn't need a separate path.
5. **Cost-aware.** No action scans remote data unless the user asks for it. Every remote query has a timeout, a row cap and a cancel option.

## 3. Where each feature runs

| Feature | Local schema | Remote schema |
|---|---|---|
| Name / fuzzy search, comments, tags, CDM | DuckDB catalog | Same (synced metadata) |
| Profile view and flags | `_meta` | `_meta` (profiled once, remotely) |
| Annotations, Excel/JSON/MD export, workshop mode | local | local (unchanged) |
| Relationships: name similarity | local | local |
| Relationships: value overlap | DuckDB | local key fingerprints (§7); remote join only on request |
| Sample, key lookup, key check, manual overlap | DuckDB | warehouse (pass-through) |
| Value search | DuckDB | fingerprints/top values first, then explicit **Search remotely** |
| SQL console | DuckDB | engine selector: DuckDB or Databricks |

## 4. Authentication and connections

- **Browser OAuth (U2M) through Entra ID:** `databricks-sdk` with `auth_type="external-browser"`, and `databricks-sql-connector` with `auth_type="databricks-oauth"`. The SDK caches and refreshes tokens in its own cache (`~/.databricks/`). **Tokens are never stored in DuckDB, the annotations file or the repo.**
- **Named connection profiles**, one per workspace, in `~/.bearings/connections.toml` (outside the repo):
  ```toml
  [prod]
  host = "https://adb-1234567890.12.azuredatabricks.net"
  warehouse_id = "abcd1234"        # serverless SQL warehouse preferred (fast cold start)
  ```
  Databricks CLI profiles (`~/.databrickscfg`) can be reused with `profile = "..."`.
- **Network:** client workspaces may use Private Link or IP access lists, so VPN may be required. `bearings remote test <profile>` checks auth, UC API reachability and the warehouse, each step on its own.

## 5. Data model (additions to `_meta`)

```sql
CREATE TABLE _meta.remote_sources (      -- one row per attached remote schema
  alias VARCHAR PRIMARY KEY,             -- local schema name used everywhere in the app, e.g. 'opera_dbx'
  connection VARCHAR,                    -- profile name in connections.toml
  catalog VARCHAR, schema VARCHAR,       -- Unity Catalog location
  attached_at TIMESTAMP, synced_at TIMESTAMP);

CREATE TABLE _meta.remote_tables (
  alias VARCHAR, table_name VARCHAR, table_type VARCHAR,   -- MANAGED / EXTERNAL / VIEW
  comment VARCHAR, row_count BIGINT, size_bytes BIGINT,
  remote_updated_at TIMESTAMP, synced_at TIMESTAMP, dropped BOOLEAN DEFAULT false);

CREATE TABLE _meta.remote_columns (
  alias VARCHAR, table_name VARCHAR, column_name VARCHAR, ordinal INTEGER,
  data_type VARCHAR, nullable BOOLEAN, comment VARCHAR);

CREATE TABLE _meta.sync_log (             -- change history, shown after each sync and exportable
  alias VARCHAR, synced_at TIMESTAMP, change VARCHAR,     -- table_added, table_dropped, column_added,
  table_name VARCHAR, column_name VARCHAR,                -- column_dropped, type_changed, comment_changed
  old_value VARCHAR, new_value VARCHAR);

CREATE TABLE _meta.key_fingerprint (      -- §7
  schema_name VARCHAR, table_name VARCHAR, column_name VARCHAR,
  distinct_values VARCHAR[],               -- exact set when <= cap, else NULL
  minhash UBIGINT[], approx_distinct BIGINT, captured_at TIMESTAMP);

ALTER TABLE _meta.table_profile ADD COLUMN stale BOOLEAN DEFAULT false;
```

**Naming:** every remote schema gets a **local alias** (default `<schema>_dbx`, user can change it) so it never clashes with a local schema. The app and annotations use the alias; the full `connection.catalog.schema` path lives in `remote_sources`.

## 6. Metadata sync and re-sync

- **Uses the Unity Catalog REST API** (`WorkspaceClient.tables.list(catalog, schema)`), not SQL on `information_schema`. It returns columns, types, comments and `updated_at` **without a running SQL warehouse**, so there's no cold start or warehouse cost and a sync takes seconds.
- **Full diff, cheap write:** `tables.list` returns every table with its columns in one paged call, so each sync diffs the whole schema (no reliance on `updated_at`, which is stored for display). The write replaces the alias' rows in one short transaction using Arrow bulk inserts, so the web app's read connections are blocked only briefly. Row counts come from table statistics (`spark.sql.statistics.numRows`) when present.
- **Change summary** after each sync, also written to `_meta.sync_log`: tables and columns added or dropped, type changes, comment changes.
- **Effects of a change:**
  - Profiles of changed tables are marked `stale`, and the UI offers **Re-profile changed**. Re-profiling never runs automatically because it costs warehouse time.
  - Relationships involving changed or dropped columns are flagged.
  - **Annotations are never deleted.** Annotations whose column no longer exists are listed as *orphaned*, with a remap suggestion based on fuzzy name match (e.g. `guest_email` → `email_address`).
  - Dropped tables are kept with `dropped=true` until the user removes them, so their annotations aren't lost.
- **UI:** a **↻ Sync** button for each catalog (syncs all attached schemas under it) and for each schema, in the Schema dropdown. A "synced 2h ago" badge. On startup, a quick check that shows "3 tables changed" without applying anything. Syncs run as background jobs with progress; the server only locks DuckDB per request, so the app stays usable.
- **Discover:** sync also lists schemas in the catalog that aren't attached yet, so they can be ticked into scope.

## 7. Remote profiling and key fingerprints

- **Profile:** one aggregate query per table (columns chunked like `profiler.py` does locally): `count(*)`, `count_if(c IS NULL)`, `count_if(trim(c) = '')`, `approx_count_distinct(c)`, min/max, `percentile_approx`, length stats, then a second pass for top values and patterns (`regexp_replace` digit/letter masks). Big tables use `TABLESAMPLE (n ROWS)`. Results are written to the same `_meta` profile tables, with `sampled_rows` set when sampled.
- **Fingerprints:** during profiling, for candidate key columns (`*_id`, `*_code`, `*_ref`, `*_no`, or flagged `PK?`/`unique*`), store the exact distinct set when it's ≤ 100k values, otherwise a MinHash signature. This lets **value-overlap relationship discovery and many value searches run locally** at no warehouse cost, including across local and remote schemas.

### 7a. As built (phase 2)

- Sample path instead of pure push-down: the sample runs through the *same* profiler as local tables (identical flags, patterns, histograms), then whole-table numbers replace the sample's where it matters – `count(*)`, `count(col)`, blank counts, min/max and `approx_count_distinct` in one query per 25 columns; `count(DISTINCT …)` only for columns whose approximate distinct is ≥ 95% of non-null (so key detection is exact); and a complete fingerprint also gives an exact distinct count. Tables up to the sample size are read whole, so everything is exact.
- Fingerprints: `_meta.key_fingerprint` (per column: distinct count, stored, complete) + `_meta.key_values` (one row per value, VARCHAR). Key-like = string / integer column whose name ends in id/key/code/no/ref… or whose distinct ≥ 98% of non-null. Cap 500,000 values; a larger target key is stored partially (`complete=false`), which can only under-state overlap.
- `relationships.overlap()` takes each side from the local table when it has rows, else from `key_values`; pairs with a remote side and no fingerprint are skipped and counted.
- Value search on remote tables: exact/contains match on `key_values` plus the stored top values, labelled "cached".

## 8. Pass-through queries (engine layer)

A small engine interface behind the endpoints that touch data (`sample`, live `profile`, `uniqueness`, `lookup`, `overlap`, `search_values`, `sql`):

```python
class Engine(Protocol):
    def query(self, sql: str, params: list | None = None, limit: int = 1000,
              timeout_s: int = 60) -> Result: ...          # columns, types, rows, elapsed_ms, sql
    def fq(self, schema_alias: str, table: str) -> str: ... # alias -> `catalog`.`schema`.`table`

class LocalEngine(Engine):       # today's DuckDB behaviour, moved behind the interface
class DatabricksEngine(Engine):  # databricks-sql-connector, Arrow results, per-profile connection pool
```

- `engine_for(alias)` looks up `_meta.remote_sources`. A request is sent to one engine; if the scope includes both kinds, the API runs one query per engine and merges the results (lookup across tables, value search).
- **Dialect:** generate SQL once in DuckDB style and use `sqlglot.transpile(sql, read="duckdb", write="databricks")` for remote. Hand-written exceptions: `USING SAMPLE n ROWS` → `TABLESAMPLE (n ROWS)`, and quoting.
- **Guardrails:** row cap (the same 1000/10000 limits as now), per-query timeout, a cancel endpoint (`cursor.cancel()`), a per-session cap on how many tables a remote value search can hit, and the same read-only regex on the SQL console. Workshop-mode PII masking applies to remote samples too.
- **Value search on remote:** (1) local top values and fingerprints; (2) if no hit, the UI offers **Search remotely** on type- and pattern-compatible string columns only, one query per table with ORs across its columns and `LIMIT 1` per column.
- **Latency:** serverless warehouses cold-start in seconds, classic ones in minutes. Remote calls are async in the UI with a spinner, elapsed time and cancel. The last N remote results are cached in memory for the session.

### 8a. As built (phase 3)

- SQL is written directly in Databricks dialect for the few operations that need it, rather than transpiling the DuckDB SQL with sqlglot: fewer moving parts, and the parameters stay bound (`:p0`…) instead of being inlined. `sqlglot` stays in the extra for a later "translate my DuckDB query" feature.
- API endpoints read the catalog with a short DuckDB read connection, release it, then call the warehouse, so a slow remote query never blocks a sync or profile write.
- Read-only guard: SELECT/WITH/DESCRIBE/SHOW/EXPLAIN only, one statement, no DML/DDL keywords (catches `WITH … INSERT`). Unity Catalog permissions still decide what is visible.

### 8b. Speed and setup (after first real use)

Live queries were noticeably slower than local ones: warehouse cold start (~18 s), HK ↔ East US 2 round trips, and a few expensive query shapes. Changes:
- warm-up on `serve` start and when a remote table is opened (`/api/remote/warm`, state shown in the header);
- sample: `TABLESAMPLE (p PERCENT) … LIMIT n` sized from the row count (fallback to `ORDER BY rand()` for small tables or heavy filters) instead of sorting the table;
- lookup: rows and total in one statement (`count(*) OVER ()`);
- live value search: tables in parallel over the 3 pooled sessions;
- 10-minute result cache for lookups, key checks and value search;
- `bearings pull -s <alias> --max-rows N` and **⤓ Copy to local**: small tables become local (profiled right away), big ones stay live.

Setup went from ~8 commands to one: `bearings connect` (workspace → sign-in → warehouse → catalog → schemas → attach → profile + relate → optional local copies; scriptable with flags and `-y`), and `bearings refresh` (sync → re-profile stale → relate).

### 8c. Local first (cache + Remote on demand)

Decision (after trying live queries from Hong Kong against East US 2): run everything locally by default, go to Databricks only when asked.
- `_meta.remote_cache(alias, table_name, cached_rows, total_rows, complete, cached_at)`; `remote_sources.cache_max_rows` (per schema; default 300,000 / `BEARINGS_CACHE_MAX_ROWS`).
- `bearings cache`: tables ≤ N rows whole (**● cached**), bigger ones as an N-row random sample (**◐ remote/cached**); not cached = **☁ remote**. `connect` caches by default; `refresh` re-caches cached tables whose source changed.
- A sampled cache keeps the whole-table profile from Databricks (exact counts, keys); only complete caches are re-profiled locally. Dropping a cache keeps profile, key fingerprints and relationships (they describe the remote table).
- API: sample / uniqueness / lookup / value search take `remote`; responses carry `source` = local | cached | sample | remote (+ cached/total rows for samples). Value-search hits in a sample are flagged `partial`.
- UI: storage chips in lists and lookups, cache status line in the table header, **⚡ Remote** toggle (sample + key check) and next to **Show rows**, source notes under results.

### 8d. PII masking, data freshness, join-consistent samples

- **PII masking** (`remote/pii.py`, `remote_sources.mask_pii`, on by default in `connect`): PII-flagged / PII-tagged / PII-named columns are replaced in the cache by `pii_` + first 16 hex of sha256(per-database salt ‖ value) (e-mails keep `@domain`); the same function scrubs stored top values / min / max and key fingerprints. Deterministic per database → joins, duplicates and overlaps survive; lookups hash typed values for masked columns. Once masked, a column stays masked on re-cache (`remote_cache.masked_columns`). Turning it on masks existing caches in place.
- **Freshness**: `remote_cache.source_version` = `DESCRIBE HISTORY … LIMIT 1` at cache time; `check_freshness` compares with the current version (3 in parallel), sets `latest_version`/`checked_at` and marks the profile stale; `refresh` then re-profiles (samples, on the warehouse) and re-caches the changed tables only. Views / non-Delta tables have no version and are only refreshed on schema change or `--recache`.
- **Join-consistent samples**: `plan_key_samples` builds groups from discovered relationships (confidence ≥ 0.8) between tables that are too big to cache whole: the parent is sampled on its key, children on the FK, all with `pmod(xxhash64(CAST(key AS STRING)), 1e6) < ppm` and one ppm per group sized so the biggest member fits the cache size. A child whose parent is sampled on another column falls back to random. Recorded in `remote_cache.sample_method`.

## 9. `bearings pull`: materialize a remote table locally

```bash
bearings pull opera_dbx.reservation --rows 500000 [--where "arrival_date >= '2026-01-01'"] [--as pms]
```

This streams `fetchmany_arrow()` batches into a temporary Parquet file, then creates the DuckDB table from it (so the write lock is held only briefly), copies the Unity Catalog comments into `_meta.comments`, and logs it in `load_log` with `source=databricks://…`. A random sample uses `TABLESAMPLE (p PERCENT) … LIMIT n`, with `p` sized from `count(*)` (Delta metadata), because Spark's `TABLESAMPLE (n ROWS)` just takes the first n rows. `--first` takes the first n; `--where` filters instead of sampling. After a pull, every existing feature works on the table, and local ⋈ remote joins become local joins. It replaces the manual "export Parquet to a Volume, then download" steps in the README.

## 10. Scope UI

```
Schema ▾
  Local
    ☑ pms              DuckDB
    ☐ crm
  Databricks · prod
    └ lakehouse                        ↻
        ☑ bronze_opera   (opera_dbx)     ↻  synced 2h ago
        ☐ silver_guest   (guest_dbx)     ↻  3 changes
    + attach schema…
```

- Local and remote schemas can be ticked together. Everything that runs on metadata covers the full scope.
- Remote tables carry a small cloud badge in lists. Actions that will hit the warehouse show a ⚡ marker on the button.
- A single live SQL query can't join across engines. The SQL tab shows which engine it's using and suggests `pull` when a local ⋈ remote join is attempted.

## 11. CLI

```bash
bearings remote add prod --host https://adb-… --warehouse abcd1234   # writes ~/.bearings/connections.toml
bearings remote login prod          # browser sign-in (Entra ID)
bearings remote test  prod
bearings remote schemas prod --catalog lakehouse                  # list what's available
bearings attach prod lakehouse.bronze_opera --as opera_dbx        # sync metadata
bearings sync [--catalog lakehouse | -s opera_dbx] [--dry-run]         # incremental re-sync + change summary
bearings profile -s opera_dbx [--sample-rows 2000000] [--only-stale]     # runs on the warehouse
bearings relate -s pms -s opera_dbx      # uses fingerprints for remote columns
bearings pull opera_dbx.reservation --rows 500000
bearings detach opera_dbx [--annotations]
```

`info`, `report`, `drop` and `reset` understand remote aliases. `reset -s opera_dbx` clears the cached metadata and profiles but never touches Databricks.

## 12. Phasing

| Phase | Scope | Result |
|---|---|---|
| **1: Metadata + pull** ✅ | connections/auth, `remote add/login/test/schemas`, `attach`, `sync` (UC API, change log, orphaned annotations + `remap`), remote tables in `catalog.build`, `pull`, `detach`; UI: grouped scope picker with ↻ sync, change summary, remap buttons, remote badges | Search, annotations and export work on remote schemas; any table can be pulled locally for full features. Relationships on remote schemas need profiles, so they come with phase 2 |
| **2: Remote profiling** ✅ | `bearings profile -s/-t <remote>` and ⚡ in the UI (background job): count → sample into in-memory DuckDB → the local profiler; exact whole-table aggregates + exact distinct for near-unique columns; key fingerprints in `_meta.key_values`; `relate`, overlap check and value search read fingerprints for remote sides; `--only-stale` | Profile drawer, key detection, relationships (remote↔remote and local↔remote) and value search on remote schemas without pulling |
| **3: Pass-through** ✅ | `bearings/remote/query.py`: pooled warehouse sessions (3 per connection, STATEMENT_TIMEOUT 120 s, reconnect once), Databricks-dialect sample (`ORDER BY rand()`, TABLESAMPLE first on >2M rows), key check, lookup (named `:p` parameters), live value search, SQL console with engine picker and alias expansion; API routes by table kind; UI ⚡ markers | Live data questions answered against the source. Not done: cancel button (timeouts instead); overlap check stays on fingerprints |
| **4: Polish** | Scope UI tree, sync badges, startup change check, sync-log export, docs + screenshots | Release as v0.2.0 |

## 13. Code touch points

- `db.py`: new `_meta` DDL (§5); `user_tables()` unions local and `remote_tables` (not dropped).
- `catalog.build()`: read columns from `information_schema.columns` **plus** `_meta.remote_columns`; add `"source_kind": "local" | "databricks"` and `"remote": {...}` to each table.
- New `bearings/remote/`: `connections.py` (profiles, auth), `sync.py` (UC API, diff, sync_log), `engine.py` (Engine, LocalEngine, DatabricksEngine, sqlglot), `profile_sql.py`, `fingerprint.py`, `pull.py`.
- `api.py`: route the data endpoints through `engine_for()`; new `/api/remote/*` (connections, attach, sync jobs + status, cancel).
- `cli.py`: `remote`, `attach`, `sync`, `pull`, `detach` commands.
- `web/`: scope tree, sync buttons/badges, ⚡ markers, engine selector in the SQL tab, orphaned-annotation remap dialog.
- Tests: mock `WorkspaceClient.tables.list` and the SQL connector with fixtures that return demo-shaped metadata; sync diff tests (add/drop/rename/type change); sqlglot transpile snapshots. No live workspace is needed in CI.

## 14. Open questions

- Which warehouse size/type is available on client workspaces (serverless vs classic)? This affects the latency UX.
- Should fingerprints (which are real key values) count as client data on disk? They are stored under `data/` (git-ignored) like the DuckDB file. Consider a `--no-fingerprints` option for strict engagements.
- Should views be profiled (possibly expensive) or only synced?
