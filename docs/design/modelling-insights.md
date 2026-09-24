# Design: Modelling insights (EDA for data modellers)

Status: **Implemented in v0.4.0** (phases 1–3: F1–F5, ER diagram builder, code lists, subtypes, attribute comparison, duplicates, outliers, DQ rules) · Branch: `feature/modelling-insights` · 2026-09-24

> **Implementation notes (v0.4.0)** – where the build differs from the proposal below:
> - **UI:** besides the header strip (grain + history + sparkline), the table view has a new **Insights** tab (key <kbd>5</kbd>) rather than only a card on the schema view – there was too much to show (grain actions, time table, entities, notes with exception rows).
> - **Remote:** F2–F5 run on the **local cache** (labelled when it's a sample); `connect` and `refresh` compute them after caching. The "⚡ Confirm on Databricks" re-scoring isn't built yet; links between tables that aren't cached show cardinality "—".
> - **Thresholds** are constants in `bearings/insights.py` (`FD_MIN_STRENGTH`, `NEAR_GRAIN`, `GRAIN_MAX_COLS`, `DEFAULT_SAMPLE`), not `_meta.settings` yet.
> - **Hide** is stored in the annotations file (`dismissed_insights`), so it survives rebuilding the database; hiding one dependency hides the whole link between the two column groups.
> - **Dependents** may have up to max(2 × d(X), d(X) + 20) distinct values, so misspelt variants (more distinct values than the key) are still scored.
> - **Relationship discovery** no longer proposes DECIMAL / DOUBLE columns as foreign keys (unless id-like by name): a flattened copy of a table otherwise "links" its amounts.
> - **Demo:** the hierarchy is shown with region and brand in `dwh.stay_flat` (room type → hotel → region / brand) instead of hotels sharing a country, so the coincidental `nationality_code → country_code` link stays in the demo.
> - Also in v0.4.0: the version is shown next to "by Flyingbear", and samples are 30 / 200 rows.
>
> **Phase 3 (also in v0.4.0)** – built, except profile history / drift (dropped: no use case):
> - **ER diagram builder:** pick the entities (from the filtered relationships, or around one table 1–2 hops out), drawn in the app with Mermaid + the ELK layered layout (lines routed around the boxes), ↓ / → direction, and exports: `.mmd` (layout in the front matter), `.svg`, and an editable **draw.io** file with the same positions (`POST /api/erd` returns the entity/link model).
> - **Code lists** (`bearings/codes.py`): columns with 2–200 values, all values captured by `insights` into `_meta.code_values`; similar lists by shared values (containment ≥ 50 %); value-by-value comparison with fuzzy suggestions; **Code lists** tab, Excel sheet.
> - **Optional attributes and subtypes** (`insights.optional_attributes`): *X is filled only when Y ∈ S* (≥ 98 % of filled rows in S, S a minority, Y a code list of ≤ 20 values; blanks and placeholders count as empty) → `_meta.conditional_fill`; columns filled on the same rows (Jaccard ≥ 0.95) → `_meta.optional_groups`; a group whose columns share one rule is shown as a possible subtype. Breakdown per value: `GET /api/table/{s}/{t}/breakdown`.
> - **Attribute comparison** (`bearings/compare.py`): join on a relationship, pair columns by name (synonyms: given/first, family/last, residence/nationality/country…) and by agreeing values on a 5,000-row sample, then count agree / differ / only one side on up to 200,000 joined rows, after normalising case, spaces, date formats and placeholders.
> - **Near-duplicates** (`bearings/duplicates.py`): roles from names and flags (e-mail, phone, birth date, first / last / full name, postcode); blocking on normalised e-mail, phone, full name, birth date + surname start (blocks > 50 rows skipped); weighted score of exact matches and Jaro-Winkler; clusters by union-find. On demand only (**Quality** tab, `bearings duplicates`).
> - **Outliers** (profiler): Tukey far-out fences at 3 × IQR, count and most extreme values; negative counts; flags `outliers`, `negatives`.
> - **DQ rules** (`bearings/dqrules.py`): not null / not empty, allowed values, format regex from the value shape, valid date (Spark format), not negative, range (outlier fences), not in the future, unique / grain, foreign key, filled-when (DQX `filter`, GX `row_condition`). `error` when the rule passes on every row today, `warn` when it describes a problem found. Exports checked against the tools: DQX YAML passes `DQEngineCore.validate_checks`; GX suites load with `gx.ExpectationSuite(**json)` (GX 1.x); Purview gets a CSV / Excel sheet with the Purview rule type (Empty/blank fields, Unique values, Duplicate rows, String format match, Data type match, Table lookup, Custom) – Purview has no rule import file. **Quality** tab, **Annotations → ⤓ DQ rules**, `bearings dq-rules`, Excel sheet.
> - **Demo:** corporate guests (subtype), realistic CRM duplicates, refunds and mistyped amounts in folio charges.

## 1. Goal

Bearings already profiles **one column at a time**: null %, distinct count, top values, patterns, histograms and flags. It also finds FK → key links. Modelling insights add the analysis a data modeller does next, when **several columns or tables are looked at together**:

| Question in the workshop | Feature |
|---|---|
| "Is this column really 5 % empty? What type should it be?" | **F1** Disguised nulls and type hints |
| "One customer has how many consents? Is the link optional?" | **F2** Relationship cardinality and optionality (+ ER diagram) |
| "What is one row of this table?" | **F3** Grain discovery |
| "How much history do we have? Is the extract complete?" | **F4** Time coverage |
| "Which columns belong together? Is there a hierarchy hidden in this extract?" | **F5** Dependencies and candidate entities |

Non-goals: generic statistical EDA (correlation matrices, pair plots, an embedded ydata-profiling report). Those take time to run, don't work on remote tables and don't answer modelling questions.

## 2. Principles

1. **SQL only.** Every check is a DuckDB query that can also go through the remote `Dialect` to run on a Databricks SQL warehouse, like the profiler. No pandas and no rows loaded into Python.
2. **Stored in `_meta`, shown where people already look.** Findings go into `_meta.*` tables. They then show up as flags, in the table header, on the Relationships tab, in the Excel report and in the Markdown specs, not in a separate "EDA" screen.
3. **Suggestions, confirmed by a person.** Each finding is a hypothesis. Confirming it writes an annotation (tag, CDM entity or attribute, note), the same way the Relationships tab already asks people to review what discovery suggests.
4. **Plain language for the room.** Every finding has a one-line sentence a business stakeholder can check, such as *"Each row is one CustomerId + Channel"*.
5. **Bounded cost.** Hard caps on columns and combinations tested, sampling above `--sample-rows`, and nothing runs on a warehouse unless the user names the remote table (`-s`, `-t`, `--remote`). This matches remote profiling.

## 3. Where it runs

| Feature | Runs in | Stored in | Triggered by |
|---|---|---|---|
| F1 | `profiler.py` (extra pass on string and temporal columns) | new `_meta.column_profile` columns + flags | `bearings profile` |
| F2 | `relationships.py` (after links are found) | new `_meta.relationships` columns | `bearings relate`; the manual overlap check |
| F3, F4, F5 | new `bearings/insights.py` | `_meta.table_profile.grain`, `_meta.time_profile`, `_meta.dependencies` | new `bearings insights` (also chained in `ingest.run`, `connect`, `refresh`) |

`bearings insights [-s schema] [-t table] [--only F3,F5] [--sample-rows N]` runs after `profile`, because it uses the column profile to choose candidate columns cheaply.

---

## 4. F1: Disguised nulls and type hints

**Why:** exports are full of `N/A`, `-`, `0`, `1900-01-01` and `9999-12-31`. Loads with `--all-varchar` keep dates and numbers as text. Null % on its own understates how empty a column is, and the target data type becomes guesswork.

**What:** for string columns, add one query per 25-column chunk (the existing chunking):

```sql
SELECT count(x),
       count(*) FILTER (WHERE upper(trim(x)) IN ('', 'N/A', 'NA', 'NULL', 'NONE', '-', '--', '?', 'UNKNOWN', 'TBD', '#N/A', 'NIL', '1900-01-01', '9999-12-31')),
       count(TRY_CAST(x AS BIGINT)), count(TRY_CAST(x AS DOUBLE)),
       count(coalesce(TRY_CAST(x AS DATE), TRY_STRPTIME(x, '%d/%m/%Y'), TRY_STRPTIME(x, '%Y%m%d'), TRY_STRPTIME(x, '%d-%b-%Y'))),
       count(*) FILTER (WHERE upper(x) IN ('Y','N','YES','NO','T','F','TRUE','FALSE')),
       count(*) FILTER (WHERE x ~ '^0[0-9]+$')              -- leading zeros: keep as text
FROM src
```

For temporal columns, count sentinel dates (`<= 1900-01-01`, `>= 9999-01-01`). For numeric columns ending in `_id`, `_code` or `_ref`, count `0` and `-1` (a common "no parent" value).

- New `column_profile` fields: `placeholder_count`, `placeholder_values` (JSON, top 5 with counts), `type_hint` (JSON: `{"type": "DATE", "share": 1.0, "formats": {"%Y-%m-%d": 0.75, "%d/%m/%Y": 0.25}}`), `leading_zero_count`.
- New flags: `placeholders`, `type_hint`, `leading_zeros`. `mixed_format` stays; `type_hint` explains it.
- **Effective null %** = (nulls + blanks + placeholders) / rows, shown next to null % in the schema view and profile drawer.
- Remote: Databricks has `try_cast` and `try_to_date(x, fmt)`, which becomes a `Dialect.try_date(expr, fmt)` method. The query runs on the profiling sample.

**Prototype on demo data:** `folio_charge.posting_date_txt` and `customer.BirthDate` both parse 100 % as dates, in two formats. `guest.email_address` has 140 placeholder values; all are blanks, which `has_blanks` already catches. The demo has no `N/A` or `1900-01-01` values, so plant a few (§10).

---

## 5. F2: Relationship cardinality and optionality

**Why:** the Relationships tab says *that* A links to B and how much the values overlap. An ERD also needs *how*: 1:1 or 1:N, mandatory or optional, and how dirty the link is.

**What:** one query per discovered link (also run by the manual overlap check):

```sql
WITH ch AS (SELECT fk k, count(*) n FROM child  WHERE fk IS NOT NULL GROUP BY 1),
     pa AS (SELECT pk k, count(*) n FROM parent WHERE pk IS NOT NULL GROUP BY 1)
SELECT (SELECT max(n) FROM pa)                                                    AS parent_max,          -- > 1: target not unique → N:M
       (SELECT max(n) FROM ch)                                                    AS child_max,           -- 1 → 1:1, > 1 → 1:N
       (SELECT avg(n) FROM ch)                                                    AS child_avg,
       (SELECT 100.0 * count(*) FILTER (WHERE ch.k IS NULL) / count(*) FROM pa LEFT JOIN ch USING (k)) AS parent_no_child_pct,
       (SELECT 100.0 * count(*) FILTER (WHERE fk IS NULL) / count(*) FROM child)  AS fk_null_pct,
       (SELECT count(*) FROM child c WHERE fk IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM parent p WHERE p.pk = c.fk))              AS orphan_rows
```

- New `relationships` columns: `cardinality` (`1:1` / `1:N` / `N:M`), `child_avg`, `child_max`, `parent_no_child_pct`, `fk_null_pct`, `orphan_rows`.
- Plain-language line: *"Each customer has 0–3 marketing consents (2.4 on average); every consent has a customer."*
- **ER diagram export.** With cardinality known, the scope can be exported as a Mermaid `erDiagram`: parent side `||` when the FK is mandatory, `|o` when optional; child side `|{` when every parent has children, `o{` otherwise, `o|` for 1:1. `GET /api/erd.mmd?schemas=…` plus an **⤓ ERD** button on the Relationships tab. By default only reviewed or high-confidence links are included. A diagram of the source system comes almost for free and is a good first workshop slide.
- Remote: runs on the warehouse when both tables are remote and named. On cached samples it runs locally with a note ("from the keyed sample"). Keyed samples (§ remote design) keep `orphan_rows` meaningful. `parent_no_child_pct` is shown as approximate on a sample.

**Prototype on demo data** (all 10 discovered links, 0.2 s in total):

| Link | Result | What it tells the modeller |
|---|---|---|
| `loyalty_account.CustomerId → customer` | **1:1**, 29.3 % of customers have none | optional 1:1 extension, a subtype or extension table |
| `marketing_consent.CustomerId → customer` | 1:N, avg 2.41, max 3 | one row per channel (see F3) |
| `folio_charge.reservation_id → reservation` | 1:N, avg 3.0, 0 orphans | clean child table |
| `folio_charge.resv_ref → reservation` | 1:N, **105 orphan rows** | legacy FK, needs a DQ rule |
| `reservation.room_type_id → room_type` | 1:N, 50 % of room types never booked | reference data larger than its use |
| `customer.PmsGuestCode → guest.guest_code` | 1:N, **max 2**, FK optional (5.8 % null) | a cross-reference that should be 1:1 → CRM duplicates |
| `guest.nationality_code → property.country_code` | 1:N, **1,600 orphan rows**, 800 guests per property | coincidental match: country, not property |

---

## 6. F3: Grain discovery

**Why:** "What is one row?" is the first question about every table. At the moment the user has to guess column combinations and try them with **Check key**.

**Algorithm** (tables without a `candidate_pk` or `unique` column):

1. Candidates: columns with no nulls, excluding measures (`DOUBLE`, `DECIMAL`), long text (`avg_len > 50`) and constants. Ordered by distinct count, descending. Keep the top 8, where names ending in `_id`, `_code`, `_no`, `_date` or `_type` are ranked first.
2. Test pairs, then triples: `SELECT count(*) FROM (SELECT DISTINCT a, b FROM src)` against the row count.
   - **Pruning:** skip a combination when the product of its distinct counts is below the row count (it can't be unique), and skip supersets of combinations already found.
   - Worst case 28 + 56 = 84 small queries. Stop at the first level that finds a key.
3. **Near-grain:** when no combination is unique but one reaches ≥ 99.9 %, report it with the number of duplicate rows ("CustomerId + Channel, except 12 duplicate rows"). A key with a few duplicates is a DQ finding, not a modelling one.
4. Big tables: search on the sample, then confirm the winner on the whole table (local) or with one warehouse query (remote, when named). A grain found only on a sample says so, like **Check key** does today.

- Stored: `table_profile.grain` (JSON list of combinations), `grain_dup_rows`, `grain_on_sample`.
- UI: a **Grain** line in the table header (*"One row per CustomerId + Channel"*) with **Check key** and **Tag as key** (writes the `key` tag to those columns).
- Remote: `SELECT count(*) FROM (SELECT DISTINCT …)` works unchanged on Databricks.

**Prototype on demo data:** `crm.marketing_consent` (17,448 rows, no single key) → **CustomerId + Channel**. The other seven tables have a single-column key.

---

## 7. F4: Time coverage

**Why:** "Is this extract complete?", "How much history is there?" and "Does the data stop in March?" come up in every discovery phase and decide what can be modelled and backfilled.

**What:** for every `DATE` or `TIMESTAMP` column, and every text column with an F1 date `type_hint`:

```sql
WITH m AS (SELECT date_trunc('month', d) mo, count(*) n FROM src WHERE d IS NOT NULL GROUP BY 1)
SELECT min(mo), max(mo), count(*) AS months_present,
       <months in range(min, max) missing from m> AS empty_months,
       <rows with d > current_date>              AS future_rows,
       list(struct_pack(mo, n) ORDER BY mo)      AS series      -- capped at 240 points
FROM m
```

- New `_meta.time_profile(schema_name, table_name, column_name, first_month, last_month, months_present, empty_months, future_rows, sentinel_rows, series, profiled_at)`.
- **Primary date column** per table: the heuristic prefers names like `business_date`, `posting`, `arrival`, `transaction`, `order` or `created` that cover the most months. Header line: *"History: Jan 2025 – Oct 2026 · 22 months · no gaps · 368 future arrivals"* with a small monthly sparkline (reuse `Charts.jsx`).
- Gaps are only flagged for event-like columns (≥ 24 distinct months and a median of ≥ 10 rows a month). Otherwise `property.opening_date` would report "108 empty months".
- A column with only 1–2 months (e.g. `last_modified_ts`) is labelled *"change timestamp, not a business date"*.

**Prototype on demo data:** `reservation.arrival_date` covers Jan 2025 – Oct 2026, 22 months with no gaps and 368 future rows (bookings on the books). `last_modified_ts` covers 2 months (a load or change stamp). `property.opening_date` has 10 values across 10 years and is correctly **not** an event column.

---

## 8. F5: Dependencies and candidate entities (the headline feature)

**Why:** source extracts, especially reporting or "flat" exports, repeat attributes of other things on every row: hotel name, country, currency and region on every stay. Finding **X → Y (Y is determined by X)** shows:

- **candidate entities**: a determinant and its dependents, e.g. *Property (property_code): property_name, local_currency, time_zone*
- **hierarchies**: chains of determinants, e.g. *room type → property → region*
- **code ↔ description pairs**: `charge_type ↔ gl_account`, `room_type_code ↔ room_type_desc`
- **redundant FKs**: `reservation.room_type_id → property_id`, so `property_id` can be derived through room type
- **dirty masters**: a dependency that holds for 99 % of rows, where the exceptions are the DQ issues

This moves Bearings from describing columns to proposing a model, which is where it helps a workshop most.

### 8.1 Algorithm (per table, on at most `--sample-rows` rows)

1. **Candidates** from the column profile:
   - *determinants X*: 2 ≤ distinct ≤ non-null / 2 (values repeat, on average ≥ 2 rows each), not temporal, not a measure (float or decimal, or a distinct ratio > 0.5 without a key-like name)
   - *dependents Y*: distinct > 1, not a measure, not `constant` / `all_null`, top-value share < 95 %, and distinct(Y) ≤ distinct(X) × 1.1 (slack for dirty data)
   - caps: 30 determinants × 40 dependents
2. **Scoring: one query per determinant** for all its dependents at once, using `GROUPING SETS`:
   ```sql
   WITH g AS (SELECT x, y1, y2, …, count(*) n, grouping(y1, y2, …) gid
              FROM src WHERE x IS NOT NULL
              GROUP BY GROUPING SETS ((x, y1), (x, y2), …)),
        m AS (SELECT gid, x, max(n) top, sum(n) tot FROM g GROUP BY ALL)
   SELECT gid, sum(top) / sum(tot) AS strength,      -- share of rows that agree with their group's majority value
          sum(tot) - sum(top)       AS exceptions
   FROM m GROUP BY gid
   ```
   **Strength is row-based** (the share of rows agreeing with the majority Y for their X), not "share of X values with exactly one Y". In the prototype, 1 % of typo'd hotel names gave a row strength of **99.11 % (266 exception rows)** but a group-based strength of **0 %**: every hotel had at least one bad row. The row-based measure keeps dirty but real dependencies.
3. **Accept** at strength ≥ 0.98 (setting `insights.fd_min_strength`): `exact` at 1.0, otherwise `approx` with an exception count.
4. **Equivalences:** X → Y and Y → X means one attribute with several spellings (code = description = sort key). They are merged into one class.
5. **Transitive reduction:** drop A → C when A → B and B → C are both present, so hierarchies read as chains.
6. **Cross-check with `_meta.relationships`:**
   - X is an FK to table T and the dependents Y also exist in T → *"denormalised copy of T's attributes"*
   - X → Z where Z is another FK → *"redundant FK (derivable through X)"*
7. **Name candidate entities** from the determinant (`property_code` → *Property*). Suggested CDM entities come from existing annotations when the determinant is already mapped.

### 8.2 Storage, UI, CLI

- `_meta.dependencies(schema_name, table_name, determinant, dependent, strength, exceptions, kind, on_sample, found_at)`, where `kind` ∈ `exact | approx | equivalent`. Candidate entities and hierarchies are derived at read time: they're cheap, and if they were stored they would go stale as annotations change.
- **Table view → "Structure" card:**
  ```
  Candidate entities in ext.stay_flat
  ▸ Property   property_code = property_name = country_code = local_currency = time_zone   → region_name
  ▸ Room type  room_type_code = room_type_desc
  ⚠ property_name_dirty depends on property_code for 99.1 % of rows (266 exceptions)   [Show exceptions]
  ```
  Actions: **Map to CDM entity…** (writes the CDM entity to every column in the group), **Show exceptions** (rows whose Y is not the majority value for their X, as SQL the user can open), **Hide** (stored as a note, so it doesn't come back).
- CLI: `bearings insights --only F5 -t pms.reservation` prints the same tree.
- Excel report: a **Dependencies** sheet. Markdown spec: a **Candidate entities** section per table.

### 8.3 Noise and limits (lessons from the prototype)

- **Synthetic data creates false dependencies.** The demo generator builds columns from `i % k`, so `pms.reservation` shows chains that don't exist in real data (`guest_id → travel_agent_id → room_type_id → property_id → market_segment`, `nights = channel_code`). Real sources have fewer of these, but low-cardinality columns will still line up by chance. Mitigations: the top-value-share and group-size guards in step 1; ranking by `determinant is key-like` × number of dependents; and **Hide**. The demo generator must be fixed before F5 can be demoed (§10).
- **Genuine findings in the demo:** `charge_type = gl_account` (a code list mapped 1:1 to GL accounts), `room_type_code = room_type_desc = size_sqm → max_occupancy`, and `reservation.room_type_id → property_id` (a redundant FK: the room type already implies the hotel).
- **Planted flat extract** (reservation ⋈ property ⋈ room type, random facts, 1 % dirty names; 30,000 rows): found *Property* (code = name = country = currency = time zone), the **property → region** hierarchy, *Room type* (code = description) and the dirty name at 99.11 %, and nothing else. It took **0.07 s**.
- In the demo every property has its own country, so `country_code` merges into Property. With real data (several hotels per country) the same algorithm returns **property → country → region** as a chain.
- Single-column determinants only in v1. Composite determinants (`property_code + room_type_code → rack_rate`) can come later, limited to pairs that include the F3 grain columns.

### 8.4 Remote

The scoring query works on Databricks unchanged (`GROUPING SETS`, `grouping()`, `GROUP BY ALL`). By default F5 runs on the **local cache or sample** (label: "found on 300,000 of 3.2 M rows"). **⚡ Confirm on Databricks** re-scores only the accepted dependencies on the whole table, one query per determinant. PII-masked columns keep their dependencies, because the salted hash is the same in every row.

---

## 9. API and UI summary

| Endpoint | Returns |
|---|---|
| `GET /api/table/{s}/{t}/profile` | + F1 fields per column; + `grain`, `time` (primary date column) in the table header |
| `GET /api/table/{s}/{t}/insights` | grain, time profiles for all date columns, dependencies, candidate entities, hierarchies |
| `GET /api/relationships` | + cardinality fields |
| `GET /api/erd.mmd?schemas=` | Mermaid `erDiagram` for the scope |
| `POST /api/insights` | background job (same job mechanism as `/api/load`), polled on `/api/jobs/{id}` |

UI changes stay inside existing screens: new flags and an effective-null bar (schema view, profile drawer), a header strip with Grain, History and a sparkline (TableDetail), a Structure card (TableDetail), a Cardinality column and **⤓ ERD** (Relationships tab). Workshop mode shows the plain-language sentences in larger type.

## 10. Demo data changes (needed for tests and demos)

- Replace the `i % k` formulas for independent attributes in `pms.reservation` with `random()` (seeded), so F5 doesn't report artefacts.
- Add a third source, **`dwh.stay_flat`**: a flattened reporting extract joining reservation, property and room type, with a `region_name` column, about 1 % typo'd property names, and a few `N/A` / `1900-01-01` placeholders. It demos F1, F4 and F5 and is realistic: many engagements start from BI extracts.
- Give properties that share a country (e.g. two in HK) so *property → country → region* appears as a chain.
- Update "Things to try in the demo" in the README.

## 11. Tests

`tests/test_insights.py` runs on the demo database:

- F1: `posting_date_txt` has type hint `DATE` with two formats; the planted `N/A` values are counted; effective null % > null %.
- F2: `loyalty_account → customer` is 1:1 and optional; `resv_ref` has 105 orphan rows; `PmsGuestCode` child_max = 2.
- F3: `marketing_consent` grain = `[CustomerId, Channel]`; the pruning skips impossible combinations (assert the query count).
- F4: `arrival_date` has no gaps and future_rows > 0; `opening_date` is not flagged for gaps.
- F5: `stay_flat` → Property class, property → region, dirty name as `approx`; after the generator fix, `reservation` has no `nights = channel_code`.
- Remote: the fake Databricks in `tests/test_remote.py` gets the new `Dialect.try_date` and checks the generated SQL.

## 12. Phases

| Phase | Scope | Why this order |
|---|---|---|
| **1: v0.4** | F1, F2 (+ ERD export), F3 | Extends existing code (`profiler.py`, `relationships.py`, Check key); no new screens; biggest immediate workshop value |
| **2: v0.5** | F5, F4, demo generator changes | F5 is the headline feature but needs the demo fix and noise tuning on real data first |
| **3: backlog** | code-list explorer and cross-system code comparison; conditional profile ("null % of X by Y"); co-null patterns (subtypes); cross-system attribute comparison on confirmed keys; profile history and drift across `refresh`; DQ rule suggestions exported for Databricks DQX / Purview Data Quality / Great Expectations; near-duplicate detection; numeric outliers | Each builds on F1–F5 results |

## 13. Open questions

1. Should `insights` run automatically at the end of `profile` / `connect`, or only on request? Proposal: F1 and F2 automatically (cheap); F3–F5 automatically for local tables under 1 M rows, and on request otherwise.
2. Thresholds (`fd_min_strength` 0.98, near-grain 99.9 %, candidate caps): make them settings in `_meta.settings`, and tune them on the first real engagement.
3. Should **Map to CDM entity** from a candidate entity also create the CDM entity itself (with attributes named after the columns), or only map to existing ones?
4. F5 exceptions show real row values. In workshop mode, mask PII columns in the exception grid the same way as in samples.
