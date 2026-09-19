"""Generate a realistic-looking (entirely fictional) hotel dataset to play with.

Two "source systems" exported the way Databricks would export them:
  pms/  – property-management system (Parquet; reservation is a folder of part-files)
  crm/  – customer / loyalty system (CSV, with its own naming conventions)
plus comments.csv shaped like an information_schema.columns export.

Deliberate data-quality issues so profiling, key checks and relationship
discovery have something to find: nulls, blanks, mixed phone/date formats,
orphan FK values, a constant column, a column that is always null, duplicate
customers across systems and legacy reference columns with non-matching names.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

PROPERTIES = [
    ("HKG", "Harbour View Hotel Hong Kong", "HK", "Asia/Hong_Kong", "HKD", 501),
    ("TYO", "Garden Tower Tokyo", "JP", "Asia/Tokyo", "JPY", 179),
    ("LON", "Park Lane House London", "GB", "Europe/London", "GBP", 181),
    ("PAR", "Rive Gauche Palace Paris", "FR", "Europe/Paris", "EUR", 138),
    ("NYC", "Central Park Tower New York", "US", "America/New_York", "USD", 244),
    ("BKK", "Riverside Residence Bangkok", "TH", "Asia/Bangkok", "THB", 331),
    ("SIN", "Marina Bay Suites Singapore", "SG", "Asia/Singapore", "SGD", 510),
    ("GVA", "Lakeside Grand Geneva", "CH", "Europe/Zurich", "CHF", 189),
    ("DXB", "Desert Pearl Dubai", "AE", "Asia/Dubai", "AED", 250),
    ("MAC", "Cotai Lights Macau", "MO", "Asia/Macau", "MOP", 213),
]


def generate(out: Path, scale: float = 1.0, seed: float = 0.42, echo=print) -> dict:
    out = Path(out)
    pms, crm = out / "exports" / "pms", out / "exports" / "crm"
    (pms / "reservation").mkdir(parents=True, exist_ok=True)
    crm.mkdir(parents=True, exist_ok=True)
    n_guest = max(200, int(8000 * scale))
    n_res = max(500, int(30000 * scale))
    n_chg = max(1000, int(90000 * scale))

    con = duckdb.connect()
    con.execute(f"SELECT setseed({seed})")
    con.execute("CREATE TABLE p AS SELECT * FROM (VALUES " + ",".join(
        f"({i + 1}, 'P{c}', '{n}', '{cc}', '{tz}', '{cur}', {rooms})" for i, (c, n, cc, tz, cur, rooms) in enumerate(PROPERTIES)) +
        ") t(property_id, property_code, property_name, country_code, time_zone, local_currency, room_count)")

    # ---------------- PMS ----------------
    con.execute("""CREATE TABLE property AS SELECT *, DATE '2001-01-01' + (property_id * 397)::INT AS opening_date,
                     'ACTIVE' AS status, NULL::VARCHAR AS brand_segment FROM p""")
    con.execute("""CREATE TABLE room_type AS
      SELECT row_number() OVER (ORDER BY p.property_id, v.ord)::INT AS room_type_id, p.property_id, v.code AS room_type_code,
             v.descr AS room_type_desc, v.occ AS max_occupancy, v.size AS size_sqm
      FROM p, (VALUES (1,'DLX','Deluxe Room',2,45),(2,'PRM','Premier Harbour Room',3,52),(3,'STE','Executive Suite',3,90),
                      (4,'PRS','Presidential Suite',4,260)) v(ord, code, descr, occ, size)""")
    con.execute(f"""CREATE TABLE guest AS SELECT
        i AS guest_id,
        'G' || lpad(i::VARCHAR, 8, '0') AS guest_code,
        CASE WHEN random() < 0.03 THEN NULL ELSE ['Mr','Ms','Mrs','Dr','Mx'][1 + (i*5) % 5] END AS salutation,
        ['Amy','Ben','Chloe','Daniel','Emma','Felix','Grace','Henry','Ivy','Jack','Kenji','Lina','Mei','Noah','Olivia','Pierre'][1 + (i*7) % 16] AS first_name,
        ['Chan','Wong','Smith','Tanaka','Dupont','Lee','Garcia','Muller','Nguyen','Rossi','Kim','Silva'][1 + (i*11) % 12] AS last_name,
        CASE WHEN random() < 0.12 THEN NULL WHEN random() < 0.02 THEN ''
             ELSE lower(['amy','ben','chloe','dan','emma','felix','grace','henry','ivy','jack','kenji','lina','mei','noah','olivia','pierre'][1 + (i*7) % 16]) || '.' || i || '@example.com' END AS email_address,
        CASE WHEN random() < 0.25 THEN NULL
             WHEN i % 3 = 0 THEN '+852 ' || (90000000 + i)::VARCHAR
             WHEN i % 3 = 1 THEN '(852) ' || (60000000 + i)::VARCHAR
             ELSE '852' || (50000000 + i)::VARCHAR END AS mobile_phone,
        DATE '1950-01-01' + ((i * 97) % 20000)::INT AS date_of_birth,
        ['HK','CN','GB','US','JP','SG','FR','AU','AE','TH'][1 + (i*3) % 10] AS nationality_code,
        ['EN','ZH','JA','FR','AR'][1 + i % 5] AS preferred_language,
        CASE WHEN random() < 0.6 THEN TRUE ELSE FALSE END AS vip_flag,
        TIMESTAMP '2014-01-01 00:00:00' + to_seconds((i * 37717) % 360000000) AS created_ts,
        'OPERA' AS source_system
      FROM range(1, {n_guest + 1}) t(i)""")
    con.execute(f"""CREATE TABLE reservation AS SELECT
        i AS reservation_id,
        'CNF' || (1000000 + i)::VARCHAR AS confirmation_no,
        1 + (i * 13) % {n_guest} AS guest_id,
        1 + i % 10 AS property_id,
        1 + ((i % 10) * 4) + (i % 4) AS room_type_id,
        DATE '2025-01-01' + (i % 640)::INT AS arrival_date,
        DATE '2025-01-01' + (i % 640)::INT + (1 + i % 6)::INT AS departure_date,
        1 + i % 6 AS nights,
        1 + i % 3 AS adults, (i % 5 = 0)::INT AS children,
        CASE WHEN i % 11 = 0 THEN 'CXL' WHEN i % 23 = 0 THEN 'NSH' WHEN DATE '2025-01-01' + (i % 640)::INT > DATE '2026-06-30' THEN 'RSV' ELSE 'CHO' END AS status_code,
        ['WEB','GDS','DIRECT','OTA','CORP','WHOLESALE'][1 + i % 6] AS channel_code,
        ['BAR','CORP','PKG','GRP','LEIS'][1 + (i*7) % 5] AS market_segment,
        ['BAR','BAR','ADV14','MEMBER','CORPNEG','PKG_BF'][1 + (i*3) % 6] AS rate_plan_code,
        round(1800 + random() * 9000, 2)::DECIMAL(14,2) AS room_revenue,
        round(random() * 3000, 2)::DECIMAL(14,2) AS other_revenue,
        CASE WHEN random() < 0.65 THEN NULL ELSE ['Late checkout','High floor','Anniversary','Airport pickup','Feather-free pillows'][1 + i % 5] END AS special_requests,
        CASE WHEN i % 29 = 0 THEN NULL ELSE 'TA' || lpad(((i * 17) % 400)::VARCHAR, 5, '0') END AS travel_agent_id,
        TIMESTAMP '2026-09-01 00:00:00' - to_seconds(i * 131) AS last_modified_ts
      FROM range(1, {n_res + 1}) t(i)""")
    con.execute(f"""CREATE TABLE folio_charge AS SELECT
        i AS charge_id,
        1 + (i * 7) % {n_res} AS reservation_id,
        CASE WHEN i % 853 = 0 THEN 99000000 + i ELSE 1 + (i * 7) % {n_res} END AS resv_ref,
        ['ROOM','F&B','SPA','LAUNDRY','MINIBAR','PARKING','TELEPHONE'][1 + i % 7] AS charge_type,
        ['1000','2000','3100','3200','4000','5000','6000'][1 + i % 7] AS gl_account,
        round(random() * 1200, 2) AS amount,
        CASE WHEN i % 4 = 0 THEN strftime(DATE '2025-01-01' + (i % 640)::INT, '%d/%m/%Y')
             ELSE strftime(DATE '2025-01-01' + (i % 640)::INT, '%Y-%m-%d') END AS posting_date_txt,
        NULL::VARCHAR AS void_reason
      FROM range(1, {n_chg + 1}) t(i)""")

    for t in ("property", "room_type", "guest"):
        con.execute(f"COPY {t} TO '{pms / (t + '.parquet')}' (FORMAT parquet)")
    parts = 3
    for k in range(parts):
        con.execute(f"COPY (SELECT * FROM reservation WHERE reservation_id % {parts} = {k}) "
                    f"TO '{pms / 'reservation' / f'part-{k:05d}.snappy.parquet'}' (FORMAT parquet)")
    con.execute(f"COPY folio_charge TO '{pms / 'folio_charge.csv'}' (HEADER)")

    # ---------------- CRM (different conventions: CamelCase, text ids, duplicates) ----------------
    n_cust = int(n_guest * 0.9)
    con.execute(f"""CREATE TABLE customer AS SELECT
        'C-' || lpad(i::VARCHAR, 7, '0') AS CustomerId,
        CASE WHEN i % 17 = 0 THEN NULL ELSE 'G' || lpad(i::VARCHAR, 8, '0') END AS PmsGuestCode,
        ['Amy','Ben','Chloe','Daniel','Emma','Felix','Grace','Henry','Ivy','Jack','Kenji','Lina','Mei','Noah','Olivia','Pierre'][1 + (i*7) % 16] AS GivenName,
        upper(['Chan','Wong','Smith','Tanaka','Dupont','Lee','Garcia','Muller','Nguyen','Rossi','Kim','Silva'][1 + (i*11) % 12]) AS FamilyName,
        CASE WHEN random() < 0.1 THEN NULL ELSE lower(['amy','ben','chloe','dan','emma','felix','grace','henry','ivy','jack','kenji','lina','mei','noah','olivia','pierre'][1 + (i*7) % 16]) || '.' || i || '@example.com' END AS EmailAddr,
        ['HK','CN','GB','US','JP','SG','FR','AU','AE','TH'][1 + (i*3) % 10] AS CountryOfResidence,
        CASE WHEN i % 3 = 0 THEN strftime(DATE '1950-01-01' + ((i * 97) % 20000)::INT, '%d/%m/%Y')
             ELSE strftime(DATE '1950-01-01' + ((i * 97) % 20000)::INT, '%Y-%m-%d') END AS BirthDate,
        DATE '2016-01-01' + (i % 3500)::INT AS CreatedOn
      FROM range(1, {n_cust + 1}) t(i)
      UNION ALL   -- duplicate customer records (same guest captured twice)
      SELECT 'C-9' || lpad(i::VARCHAR, 6, '0'), 'G' || lpad(i::VARCHAR, 8, '0'), 'Amy', 'CHAN', NULL, 'HK', '1980-05-05', DATE '2024-02-02'
      FROM range(1, {max(10, n_cust // 100)}) t(i)""")
    con.execute("""CREATE TABLE loyalty_account AS SELECT
        'LA' || lpad(row_number() OVER ()::VARCHAR, 7, '0') AS LoyaltyAccountNo,
        CustomerId,
        CASE WHEN random() < 0.08 THEN 'Diamond' WHEN random() < 0.25 THEN 'Gold' WHEN random() < 0.5 THEN 'Silver' ELSE 'Classic' END AS TierName,
        (random() * 250000)::INT AS PointsBalance,
        CreatedOn + 30 AS EnrolledOn,
        CASE WHEN random() < 0.05 THEN 'SUSPENDED' ELSE 'ACTIVE' END AS AccountStatus
      FROM customer WHERE random() < 0.7""")
    con.execute("""CREATE TABLE marketing_consent AS SELECT
        CustomerId, ch.channel AS Channel,
        random() < 0.55 AS OptIn,
        CreatedOn + (random() * 400)::INT AS ConsentDate,
        'WEB_FORM' AS CaptureSource
      FROM customer, (VALUES ('EMAIL'), ('SMS'), ('POST')) ch(channel) WHERE random() < 0.8""")
    for t in ("customer", "loyalty_account", "marketing_consent"):
        con.execute(f"COPY {t} TO '{crm / (t + '.csv')}' (HEADER)")

    comments = [
        ("pms", "reservation", "", "Booking header from the PMS – one row per stay"),
        ("pms", "reservation", "confirmation_no", "Confirmation number shown to the guest"),
        ("pms", "reservation", "room_revenue", "Room revenue net of tax in property local currency"),
        ("pms", "reservation", "market_segment", "Revenue-management market segment"),
        ("pms", "guest", "", "Guest profile as captured at the property"),
        ("pms", "guest", "guest_code", "Guest profile identifier used across PMS interfaces"),
        ("pms", "guest", "vip_flag", "VIP status for arrival handling"),
        ("pms", "folio_charge", "resv_ref", "Legacy reservation reference from the old POS interface"),
        ("pms", "folio_charge", "posting_date_txt", "Business date the charge was posted (text, mixed formats)"),
        ("pms", "property", "local_currency", "ISO 4217 currency of the property"),
        ("crm", "customer", "", "CRM golden customer record"),
        ("crm", "customer", "PmsGuestCode", "Cross-reference to the PMS guest profile"),
        ("crm", "loyalty_account", "TierName", "Loyalty programme tier"),
        ("crm", "marketing_consent", "OptIn", "Consent to receive marketing on the channel"),
    ]
    with open(out / "comments.csv", "w", encoding="utf-8") as f:
        f.write("table_schema,table_name,column_name,comment\n")
        for s, t, c, cm in comments:
            f.write(f'{s},{t},{c},"{cm}"\n')

    counts = {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
              for t in ("property", "room_type", "guest", "reservation", "folio_charge", "customer", "loyalty_account", "marketing_consent")}
    echo(f"  demo files written to {out}/exports (pms: parquet + csv, crm: csv) and {out}/comments.csv")
    return counts
