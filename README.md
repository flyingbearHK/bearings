<h1 align="center">🐻 Bearings</h1>
<p align="center"><b>Get your bearings in unfamiliar source data.</b><br>
A local data-modelling workbench: load CSV/Parquet exports into DuckDB, then search, profile, sample and relate them from a fast web UI.</p>
<p align="center">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/python-3.10%2B-blue">
  <img alt="DuckDB" src="https://img.shields.io/badge/engine-DuckDB-yellow">
  <img alt="Local-first" src="https://img.shields.io/badge/data-stays%20on%20your%20laptop-brightgreen">
</p>

![Search across source systems](docs/screenshots/search.png)

When you're dropped into a new data-modelling engagement, the first weeks go into "where is the guest ID?", "which of these 400 columns are always empty?" and "how do these two systems join?". Bearings answers those questions in seconds, **entirely on your machine**, so client data never leaves your laptop.

- **Search everything:** fuzzy, contains or exact search over table and column names, comments, tags and CDM mappings. Search *values* too: "which columns contain `G00000042`?"
- **Two-layer results:** tables on the left, matched columns next to them, and the full schema with the matches highlighted.
- **Profile at a glance:** null % and distinct counts, top values, value patterns, histograms, and flags for candidate keys, PII, mixed formats and constant columns.
- **Look up a key across tables:** type `reservationid=9401`, tick the tables, and see every matching row side by side.
- **Relationship discovery:** likely FK → key links from name similarity plus value overlap, including across source systems.
- **Annotate and export:** tag columns (PII, key…), map them to CDM entities and attributes, and export an Excel mapping workbook, JSON or Markdown specs.
- **Schema scope:** load each source system into its own schema and focus the whole app on one or several of them.
- **Workshop mode:** bigger text, and PII masked in samples, for screen-sharing with a room full of stakeholders.

| Look up a key across tables | Column profile | Discovered relationships |
|---|---|---|
| ![lookup](docs/screenshots/lookup.png) | ![profile](docs/screenshots/profile.png) | ![relationships](docs/screenshots/relationships.png) |

```
exports (csv/parquet) ──bearings load──▶ data/bearings.duckdb ──bearings profile / relate──▶ _meta.* ──bearings serve──▶ http://127.0.0.1:8765
                                                        annotations → data/bearings.annotations.sqlite (kept when you rebuild the DB)
```

## Install

Dependencies are managed with [uv](https://docs.astral.sh/uv/) (`pyproject.toml` + `uv.lock`, Python pinned in `.python-version`).

```bash
# macOS: brew install uv    ·    Linux/macOS: curl -LsSf https://astral.sh/uv/install.sh | sh    ·    Windows: winget install astral-sh.uv
git clone https://github.com/flyingbearhk/bearings.git
cd bearings
uv sync                    # creates .venv and installs the locked deps + the `bearings` command (alias: `dm`)
```

Run commands with `uv run bearings …` (as below), or `source .venv/bin/activate` once and drop the `uv run` prefix. `dm` is a short alias for `bearings`.

The web UI comes prebuilt in `bearings/static/`, so you only need Node if you want to change the UI.

## Quick start with sample data (5 minutes)

To try the tool before real exports arrive, `bearings demo` generates a **fictional hotel dataset** from two "source systems". It then loads, profiles and relates the data into a separate `data/demo.duckdb`, so your real database isn't touched.

```bash
uv sync                                   # first time only
uv run bearings demo                            # ~3 s: generate → load → comments → profile → relate
uv run bearings serve --db data/demo.duckdb     # open http://127.0.0.1:8765
```

| Schema | Table | Rows | Format | What's in it |
|---|---|---|---|---|
| `pms` | property | 10 | Parquet | Hotel master: code, name, country, currency, rooms (`brand_segment` is always null) |
| `pms` | room_type | 40 | Parquet | 4 room types per property |
| `pms` | guest | 8,000 | Parquet | Guest profiles with PII: names, email (nulls and blanks), phone in 3 formats, DOB |
| `pms` | reservation | 30,000 | Parquet **folder of 3 part-files** | Stays: dates, status, channel, segment, rate plan, revenue |
| `pms` | folio_charge | 90,000 | CSV | Charges; `resv_ref` is a legacy FK with orphans; `posting_date_txt` has mixed date formats |
| `crm` | customer | ~7,300 | CSV | CamelCase naming, text IDs, `PmsGuestCode` cross-reference, **duplicate customers** |
| `crm` | loyalty_account | ~5,100 | CSV | Tier and points per customer |
| `crm` | marketing_consent | ~17,400 | CSV | Opt-in per channel (`CaptureSource` is constant) |

Options: `--scale 5` makes about 5× more rows (useful for testing performance). `--files-only` writes only the export files, so you can practise the real `bearings load` / `bearings profile` / `bearings relate` steps yourself:

```bash
uv run bearings demo --files-only                       # → demo/exports/pms, demo/exports/crm, demo/comments.csv
uv run bearings load demo/exports/pms --schema pms --db data/play.duckdb
uv run bearings load demo/exports/crm --schema crm --db data/play.duckdb
uv run bearings comments demo/comments.csv --db data/play.duckdb
uv run bearings profile --db data/play.duckdb
uv run bearings relate --deep --db data/play.duckdb
uv run bearings serve --db data/play.duckdb
```

### Things to try in the demo

1. **Fuzzy name search.** Try `guest`. The table matches, and so do `reservation.guest_id`, `crm.customer.PmsGuestCode` (a different naming style) and `reservation.confirmation_no`, which matches through its comment. Then try `email`, `revenue`, `*_code` and `confirmation number`, which is found through the column comment.
2. **Two-layer results.** Click `PmsGuestCode` in the column list to open the `customer` schema with that row highlighted. Click **Sample 20**, then use **Columns → Matched first** to reorder the sample.
3. **Profiling.** Use the ▤ button on `pms.guest`. `mobile_phone` shows *mixed fmt* (three formats), `email_address` shows *PII email* and *blanks*, and `vip_flag` has an uneven true/false split. Also look at `folio_charge.posting_date_txt` (mixed date formats) and `property.brand_segment` (*all null*).
4. **Value search.** Switch to *Value* and search `G00000042` (exact). It turns up in both `pms.guest.guest_code` and `crm.customer.PmsGuestCode`, which is how you'd find cross-system keys. Clicking any top value in a profile drawer searches for that value everywhere.
5. **Relationships tab.** Includes the cross-system link `crm.customer.PmsGuestCode → pms.guest.guest_code`, and `folio_charge.resv_ref → reservation.reservation_id`, found by value overlap even though the names don't match. It also shows a coincidental match, `guest.nationality_code → property.country_code`, which is a good reminder to review what the discovery suggests. Use **Check a join manually** to see orphan `resv_ref` values.
6. **Key check.** In `crm.customer`, tick `PmsGuestCode` and click **Check key**. It's not unique, because the CRM has duplicate customers, and the check shows example duplicates. In `pms.reservation`, tick `guest_id` + `arrival_date`.
7. **Annotate.** Open `crm.customer.EmailAddr`, tag it `PII, contact`, and set CDM `Party` / `EmailAddress`. Do the same for `pms.guest.email_address`. Search `Party` to find both, then **⤓ Excel** exports the mapping workbook.
8. **Workshop mode.** Tick it in the header. The text gets bigger and PII columns are masked in samples.
9. **SQL tab.** Try `SUMMARIZE pms.reservation`, or:
   ```sql
   SELECT c.CustomerId, g.guest_code, g.email_address, c.EmailAddr
   FROM crm.customer c JOIN pms.guest g ON g.guest_code = c.PmsGuestCode
   WHERE coalesce(g.email_address,'') <> coalesce(c.EmailAddr,'') LIMIT 50
   ```

Start over at any time with `uv run bearings demo`, which rebuilds `data/demo.duckdb`. Demo annotations are kept in `data/demo.annotations.sqlite`, separate from your real ones.

## Workflow

```bash
# 1. Load. A file becomes one table; a folder of Spark part-files becomes one table named after the folder.
uv run bearings load ./exports/opera --schema pms          # --append to add files, --all-varchar to keep raw text (leading zeros)
uv run bearings load ./exports/crm   --schema crm

# 2. Optional: descriptions from Databricks (they become searchable)
uv run bearings comments ./exports/columns.csv             # needs table_name, column_name, comment [, table_schema]

# 3. Profile (standard profile → _meta.column_profile / table_profile)
uv run bearings profile                                    # all tables
uv run bearings profile -t pms.reservation --sample-rows 2000000   # big table: profile a random sample
uv run bearings profile --only-new                         # only tables that aren't profiled yet

# 4. Relationship discovery (name similarity + value overlap)
uv run bearings relate                                     # --deep also tests *_id/_code/_ref columns whose names don't match

# 5. Run the app
uv run bearings serve                                      # http://127.0.0.1:8765

# Other commands
uv run bearings info                                       # tables, row counts, profile status (-s pms to filter)
uv run bearings report -o catalog.xlsx                     # Tables / Columns (+profile, tags, CDM) / Relationships (-s pms to filter)
uv run bearings drop pms.folio_charge                      # remove one table (or a whole schema: bearings drop pms)
uv run bearings reset                                      # start fresh – see "Resetting the database" below
```

The server holds the database lock only for the length of each request, so you can run `bearings load`, `bearings profile` or `bearings relate` while `bearings serve` is running (in another terminal). Refresh the browser afterwards. A GUI client such as DBeaver that keeps the file open will block writes.

Use `--db path/to/other.duckdb` or `export BEARINGS_DB=...` to keep a separate database per engagement or domain.

### Several source systems: schemas and the schema scope

Load each source system into its own schema. The schema name becomes the first part of every table name (`pms.reservation`, `crm.customer`):

```bash
uv run bearings load ./exports/opera   --schema pms
uv run bearings load ./exports/crm     --schema crm
uv run bearings load ./exports/finance --schema fin
uv run bearings profile                         # or per system: bearings profile -s crm
uv run bearings relate -s pms                   # links inside one system
uv run bearings relate -s pms -s crm            # also cross-system links between pms and crm
```

In the app, the **Schema** dropdown in the header sets the **scope**. Tick one or more schemas, or click **only** next to one. After that, everything covers only those schemas:

- name and value search, the table list and filter lookups (`reservationid=9401`)
- the Relationships tab, which shows only links with both ends in scope
- the Annotations tab and the **Excel / JSON exports** (the file name includes the schema)
- the SQL tab's table list. The SQL console itself can still query any table.

The scope button turns yellow when a scope is active, so you can see results are filtered. The app remembers your choice. To open the app already scoped:

```bash
uv run bearings serve -s crm              # or -s pms -s crm
```

The CLI has the same filter: `bearings info -s crm`, `bearings report -s crm -o crm_catalog.xlsx`, `bearings profile -s crm`, `bearings relate -s crm`.

For fully separate engagements or clients, use **separate database files** instead of schemas: `--db data/client-a.duckdb` or `export BEARINGS_DB=data/client-a.duckdb`. Each database gets its own annotations file.

### Resetting the database (start fresh)

Stop `bearings serve` (Ctrl+C) first, or at least make sure no load is running. Every command asks for confirmation; add `-y` to skip it.

| Goal | Command |
|---|---|
| Wipe everything and **keep** your annotations (tags, CDM mappings, notes) | `uv run bearings reset` |
| Wipe everything **including** annotations | `uv run bearings reset --annotations` |
| Reset one source system only (drop the schema's tables, profile and relationships; compact the file) | `uv run bearings reset -s crm` (add `--annotations` to also remove its annotations) |
| Remove one table | `uv run bearings drop pms.folio_charge` |
| Remove one schema | `uv run bearings drop crm` |
| Reset the demo | `uv run bearings reset --db data/demo.duckdb --annotations`, or just `uv run bearings demo` again, which rebuilds it |
| Shrink the file after drops | `uv run bearings compact` (DuckDB doesn't give space back on its own) |

Annotations are kept by default because they're manual work. They're stored in `data/<db-name>.annotations.sqlite` and match on schema/table/column names, so when you reload the same tables they reappear automatically.

To reload a system from scratch:

```bash
uv run bearings reset -s pms -y
uv run bearings load ./exports/opera --schema pms && uv run bearings profile -s pms && uv run bearings relate -s pms
```

The manual way: stop the server and delete the files. `rm data/bearings.duckdb data/bearings.duckdb.wal` wipes the data; also delete `data/bearings.annotations.sqlite` to lose the annotations. `rm -rf demo/ data/demo.*` removes the demo.

### Getting data out of Databricks

```python
# Parquet (best: keeps types). Download the folder; each folder becomes one table.
spark.table("cat.schema.reservation").write.mode("overwrite").parquet("/Volumes/cat/schema/exports/reservation")
# Big tables: a sample is plenty for modelling
spark.table("cat.schema.folio").sample(0.05).write.parquet("/Volumes/.../folio")
```
```sql
-- Column comments → comments.csv
SELECT table_schema, table_name, column_name, comment FROM cat.information_schema.columns WHERE comment IS NOT NULL
UNION ALL
SELECT table_schema, table_name, '' AS column_name, comment FROM cat.information_schema.tables WHERE comment IS NOT NULL
```

## Using the app

| Feature | How |
|---|---|
| **Name search** | Search tables, columns, comments and tags. The **Exact · Contains · Fuzzy** control sets how strictly names must match:<br>• **Exact**: the whole name must match, ignoring case, `_` and spaces, so `reservationid` finds `reservation_id` / `ReservationId`. Names only.<br>• **Contains**: the text appears anywhere in the name or comment.<br>• **Fuzzy**: tolerates typos and also searches comments, tags and CDM mappings.<br>Wildcards (`*_dt`, `res*`) and `table.column` work in every mode. Your choice is remembered. |
| **Filter lookup across tables** | Type `column op value`, e.g. `reservationid=9401`, `guest_code=G1,G2` (a list), `arrival_date>=2026-01-01`, `status_code!=CXL` or `email~gmail` (contains). The left panes show only tables that have a matching column; the Exact/Contains/Fuzzy control decides how the column name is matched. Tick tables, or use the header box to **select all**, then click **Show rows** or press Enter. The right panel lists the matching rows from every selected table, one collapsible section each, with the filter column first, row counts, and **Open table** / **SQL** / **CSV** buttons. Also works after a *Value* search: tick tables and **Show rows** returns the full rows that contain the value. |
| **Two-layer results** | If only table names match, you get the table list. If columns match, tables are on the left and the matched columns (grouped by table) are on the right. |
| **Schema view** | Click a column or table to open the full schema. Matched columns are highlighted. **Fields** chooses and reorders the stats shown (null %, distinct, min/max, flags, tags, CDM, comment). |
| **Sample data** | **Sample 10/20/50** draws random rows. **Columns** lets you choose and drag-reorder columns (remembered per table). Presets: *Matched only* and *Matched first*. You can also require non-null values in the matched columns or add a SQL filter. |
| **Profile** | The **▤** button on any table or column. The table view shows tiles plus null and distinct bars. The column drawer shows stats, histogram, top values (click one to search for it everywhere), patterns and flags. Unprofiled tables can be computed live (the result isn't saved). |
| **Value search** | Switch to *Value* and press Enter to find which columns contain a code or ID. |
| **Key check** | Tick columns in the schema and click **Check key** to test whether that combination is unique and see example duplicates. |
| **Relationships** | Discovered FK → key pairs with overlap % and confidence. There's also a manual overlap checker between any two columns that lists orphan values. |
| **Annotations** | Tags (PII, key, …), CDM entity and attribute, and notes on any column. Annotations are searchable and export to **Excel** or JSON, and **Export .md** gives a per-table spec. |
| **SQL** | A read-only DuckDB console. Try `SUMMARIZE pms.guest`. Ctrl/⌘+Enter runs the query. |
| **Schema scope** | The **Schema** dropdown in the header limits the whole app to one or more source systems. See "Several source systems" above. |
| **Workshop mode** | Larger text, and PII-flagged or PII-tagged columns are masked in samples. |

Profile flags: `PK?` (unique and not null), `unique*` (unique but has nulls), `≥50% null`, `all null`, `constant`, `mixed fmt`, `blanks`, `PII email/phone`, `PII?` (the column name suggests personal data).

## Developing the UI (React + Vite)

```bash
cd web && npm install
npm run dev        # http://localhost:5173, proxies /api to bearings serve on :8765
npm run build      # rebuilds bearings/static/
```

## Layout

```
bearings/
  cli.py            `bearings` commands (typer)
  loader.py         CSV/Parquet → DuckDB, comments import
  profiler.py       standard column profile
  relationships.py  FK discovery
  catalog.py        catalog cache, name search (exact/contains/fuzzy), value search
  export.py         xlsx / json / markdown
  demo.py           fictional demo dataset generator
  db.py             connections, _meta schema, reset/drop/compact
  api.py            FastAPI (+ serves the built UI)
  static/           built UI
web/                React + Vite source
tests/              end-to-end smoke test on demo data
docs/screenshots/   README images (demo data)
```

## Privacy

Bearings is local-first. The server binds to `127.0.0.1`, makes no outbound calls, and everything it stores lives in `data/`, which `.gitignore` excludes together with CSV/Parquet/Excel files. The demo dataset is entirely fictional.

## Contributing

Issues and pull requests are welcome. Run the tests with `uv run pytest`, and rebuild the UI with `cd web && npm run build` before committing UI changes.

## License

[MIT](LICENSE) © 2026 Flyingbear
