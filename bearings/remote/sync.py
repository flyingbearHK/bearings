"""Attach a remote schema and keep its metadata in sync with DuckDB `_meta.remote_*`.

Metadata comes from the connector's catalog API (Databricks: the Unity Catalog REST API, which doesn't
need a running SQL warehouse – no cold start, no warehouse cost). Network calls happen *before* the
DuckDB write lock is taken, so the web app stays usable while a sync runs.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from ..db import META, connect, has_meta, remote_aliases, ro, safe_name, user_tables
from . import RemoteError
from . import connections as cx

CHANGE_KINDS = ("table_added", "table_dropped", "table_restored", "column_added", "column_dropped",
                "type_changed", "comment_changed", "table_comment_changed")


# ------------------------------------------------------------------ reading the remote catalog (via the connector)
def fetch_schema(connector, catalog: str, schema: str) -> dict[str, dict]:
    """{table_name: {table_type, comment, updated_at, row_count, size_bytes, columns: [...]}} (see Connector.fetch_schema)."""
    return connector.fetch_schema(catalog, schema)


def list_catalogs(connector) -> list[str]:
    return connector.list_catalogs()


def list_schemas(connector, catalog: str) -> list[dict]:
    return connector.list_schemas(catalog)


# ------------------------------------------------------------------ local state
def stored_state(con, alias: str) -> dict[str, dict]:
    if not has_meta(con, "remote_tables"):
        return {}
    tabs = {r[0]: {"table_type": r[1], "comment": r[2], "updated_at": r[3], "dropped": bool(r[4]), "columns": []}
            for r in con.execute(f"SELECT table_name, table_type, comment, remote_updated_at, dropped FROM {META}.remote_tables WHERE alias=?",
                                 [alias]).fetchall()}
    for t, c, o, dtp, n, cm in con.execute(f"""SELECT table_name, column_name, ordinal, data_type, nullable, comment
                                              FROM {META}.remote_columns WHERE alias=? ORDER BY table_name, ordinal""", [alias]).fetchall():
        if t in tabs:
            tabs[t]["columns"].append({"column_name": c, "ordinal": o, "data_type": dtp, "nullable": n, "comment": cm})
    return tabs


def diff(old: dict[str, dict], new: dict[str, dict]) -> list[dict]:
    """Changes going from the stored metadata (`old`) to what Unity Catalog reports now (`new`)."""
    ch = []

    def add(kind, table, column=None, old_v=None, new_v=None):
        ch.append({"change": kind, "table_name": table, "column_name": column, "old_value": old_v, "new_value": new_v})

    for t in sorted(set(old) | set(new)):
        o, n = old.get(t), new.get(t)
        if o is None:
            add("table_added", t, new_v=f"{len(n['columns'])} column{'s' if len(n['columns']) != 1 else ''}")
            continue
        if n is None:
            if not o.get("dropped"):
                add("table_dropped", t)
            continue
        if o.get("dropped"):
            add("table_restored", t)
        if (o.get("comment") or None) != (n.get("comment") or None):
            add("table_comment_changed", t, old_v=o.get("comment"), new_v=n.get("comment"))
        oc = {c["column_name"].lower(): c for c in o["columns"]}
        nc = {c["column_name"].lower(): c for c in n["columns"]}
        for k in nc:
            if k not in oc:
                add("column_added", t, nc[k]["column_name"], new_v=nc[k]["data_type"])
        for k in oc:
            if k not in nc:
                add("column_dropped", t, oc[k]["column_name"], old_v=oc[k]["data_type"])
        for k in nc.keys() & oc.keys():
            if (oc[k]["data_type"] or "") != (nc[k]["data_type"] or ""):
                add("type_changed", t, nc[k]["column_name"], oc[k]["data_type"], nc[k]["data_type"])
            if (oc[k].get("comment") or None) != (nc[k].get("comment") or None):
                add("comment_changed", t, nc[k]["column_name"], oc[k].get("comment"), nc[k].get("comment"))
    return ch


def summarize(changes: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for c in changes:
        out[c["change"]] = out.get(c["change"], 0) + 1
    return out


# ------------------------------------------------------------------ writing
def _write(con, alias: str, new: dict[str, dict], changes: list[dict], now: dt.datetime):
    """Replace the alias' cached metadata in one short transaction (bulk inserts via Arrow keep the lock brief)."""
    import pyarrow as pa
    old = stored_state(con, alias)
    changed = {c["table_name"] for c in changes}
    tabs = pa.table({
        "alias": [alias] * len(new), "table_name": list(new), "table_type": [n["table_type"] for n in new.values()],
        "comment": [n["comment"] for n in new.values()], "row_count": pa.array([n["row_count"] for n in new.values()], pa.int64()),
        "size_bytes": pa.array([n["size_bytes"] for n in new.values()], pa.int64()),
        "remote_updated_at": pa.array([n["updated_at"] for n in new.values()], pa.timestamp("us")),
        "synced_at": pa.array([now] * len(new), pa.timestamp("us")), "dropped": [False] * len(new)})
    cl = [(t, c) for t, n in new.items() for c in n["columns"]]
    cols = pa.table({
        "alias": [alias] * len(cl), "table_name": [t for t, _ in cl], "column_name": [c["column_name"] for _, c in cl],
        "ordinal": pa.array([c["ordinal"] for _, c in cl], pa.int32()), "data_type": [c["data_type"] for _, c in cl],
        "nullable": pa.array([c["nullable"] for _, c in cl], pa.bool_()), "comment": pa.array([c["comment"] for _, c in cl], pa.string())})
    gone = pa.table({"alias": [alias] * len(set(old) - set(new)), "table_name": sorted(set(old) - set(new)),
                     "table_type": pa.array([old[t]["table_type"] for t in sorted(set(old) - set(new))], pa.string()),
                     "comment": pa.array([old[t]["comment"] for t in sorted(set(old) - set(new))], pa.string())})
    con.register("_new_tables", tabs)
    con.register("_new_columns", cols)
    con.register("_gone_tables", gone)
    con.execute("BEGIN TRANSACTION")
    try:
        con.execute(f"DELETE FROM {META}.remote_tables WHERE alias=?", [alias])
        con.execute(f"DELETE FROM {META}.remote_columns WHERE alias=? AND table_name NOT IN (SELECT table_name FROM _gone_tables)", [alias])
        con.execute(f"INSERT INTO {META}.remote_tables SELECT * FROM _new_tables")
        # dropped upstream: keep the rows (their annotations stay reachable), flagged dropped
        con.execute(f"""INSERT INTO {META}.remote_tables
                        SELECT alias, table_name, table_type, comment, NULL, NULL, NULL, ?, true FROM _gone_tables""", [now])
        con.execute(f"INSERT INTO {META}.remote_columns SELECT * FROM _new_columns")
        if changes:
            con.executemany(f"INSERT INTO {META}.sync_log VALUES (?,?,?,?,?,?,?)",
                            [[alias, now, c["change"], c["table_name"], c["column_name"],
                              None if c["old_value"] is None else str(c["old_value"]),
                              None if c["new_value"] is None else str(c["new_value"])] for c in changes])
            # a pulled local copy / its profile no longer matches the source
            for t in changed:
                con.execute(f"UPDATE {META}.table_profile SET stale=true WHERE schema_name=? AND table_name=?", [alias, t])
        con.execute(f"UPDATE {META}.remote_sources SET synced_at=? WHERE alias=?", [now, alias])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        for v in ("_new_tables", "_new_columns", "_gone_tables"):
            con.unregister(v)


def sync(db_path: Path, alias: str, dry_run: bool = False, echo=lambda *_: None) -> dict:
    """Re-read one attached schema from Unity Catalog; store what changed. Returns a summary."""
    with ro(db_path) as con:
        src = remote_aliases(con).get(alias)
        if not src:
            raise RemoteError(f"'{alias}' is not an attached remote schema. Attach it: bearings attach <connection> <catalog>.<schema> --as {alias}")
        old = stored_state(con, alias)
    conn = cx.get(src["connection"])
    echo(f"  reading {src['catalog']}.{src['schema']} from {conn.name}…")
    new = fetch_schema(conn.connector, src["catalog"], src["schema"])
    changes = diff(old, new)
    now = dt.datetime.now().replace(microsecond=0)
    if not dry_run:
        con = connect(db_path, read_only=False, retries=5)
        try:
            _write(con, alias, new, changes, now)
        finally:
            con.close()
    return {"alias": alias, "connection": conn.name, "catalog": src["catalog"], "schema": src["schema"],
            "tables": len(new), "changes": changes, "summary": summarize(changes), "synced_at": now.isoformat(),
            "dry_run": dry_run, "first_sync": not old}


def aliases_for(db_path: Path, aliases: list[str] | None = None, catalog: str | None = None, connection: str | None = None) -> list[str]:
    with ro(db_path) as con:
        src = remote_aliases(con)
    out = [a for a, s in src.items()
           if (not aliases or a in aliases) and (not catalog or s["catalog"] == catalog) and (not connection or s["connection"] == connection)]
    missing = [a for a in (aliases or []) if a not in src]
    if missing:
        raise RemoteError(f"Not attached: {', '.join(missing)}. Attached: {', '.join(src) or 'none'}")
    return out


def attach(db_path: Path, connection: str, catalog: str, schema: str, alias: str | None = None, echo=lambda *_: None) -> dict:
    """Register catalog.schema under a local alias (default <schema>_dbx) and run the first sync."""
    alias = safe_name(alias or f"{schema}_dbx")
    if alias in ("_meta", "main", "information_schema", "pg_catalog"):
        raise RemoteError(f"'{alias}' is reserved – pick another alias with --as")
    conn = cx.get(connection)
    db_path = Path(db_path)
    if db_path.exists():
        with ro(db_path) as con:
            if alias in remote_aliases(con):
                raise RemoteError(f"'{alias}' is already attached. Re-sync it with: bearings sync -s {alias}")
            if alias in {s for s, _ in user_tables(con)}:
                raise RemoteError(f"A local schema called '{alias}' already exists – pick another alias with --as")
    # fail before writing anything if the schema can't be read
    fetch_schema(conn.connector, catalog, schema)
    con = connect(db_path, read_only=False, retries=5)
    try:
        con.execute(f"INSERT INTO {META}.remote_sources (alias, connection, catalog, schema, attached_at) VALUES (?,?,?,?,?)",
                    [alias, conn.name, catalog, schema, dt.datetime.now().replace(microsecond=0)])
    finally:
        con.close()
    return sync(db_path, alias, echo=echo)


def detach(con, alias: str) -> None:
    """Forget a remote schema's cached metadata (never touches Databricks). Caller handles local tables/annotations."""
    if not has_meta(con, "remote_sources"):
        return
    for t in ("remote_tables", "remote_columns", "sync_log"):
        con.execute(f"DELETE FROM {META}.{t} WHERE alias=?", [alias])
    con.execute(f"DELETE FROM {META}.remote_sources WHERE alias=?", [alias])


def recent_changes(con, alias: str | None = None, limit: int = 200) -> list[dict]:
    if not has_meta(con, "sync_log"):
        return []
    sql = f"SELECT alias, synced_at, change, table_name, column_name, old_value, new_value FROM {META}.sync_log"
    params: list = []
    if alias:
        sql += " WHERE alias=?"
        params.append(alias)
    sql += f" ORDER BY synced_at DESC, alias, table_name, column_name LIMIT {int(limit)}"
    cols = ["alias", "synced_at", "change", "table_name", "column_name", "old_value", "new_value"]
    return [dict(zip(cols, r)) for r in con.execute(sql, params).fetchall()]


def dialect(src: dict):
    """SQL dialect of an attached source's connection."""
    from .connectors import dialect_for
    return dialect_for(src.get("connection"))


def remote_fq(src: dict, table: str) -> str:
    """Fully qualified, quoted remote name (e.g. `catalog`.`schema`.`table` on Databricks)."""
    return dialect(src).table_ref(src["catalog"], src["schema"], table)


__all__ = ["attach", "sync", "detach", "diff", "fetch_schema", "list_schemas", "list_catalogs", "recent_changes",
           "aliases_for", "remote_fq", "stored_state", "summarize", "CHANGE_KINDS"]
