"""Azure Databricks / Unity Catalog connector.

- Metadata: Unity Catalog REST API through the Databricks SDK (`tables.list` needs no running warehouse).
- SQL: the Databricks SQL connector on a SQL warehouse, Arrow results, Spark SQL dialect.
- Sign-in: browser OAuth through Entra ID (`auth_type = "external-browser"`); the SDK caches and refreshes
  the token in ~/.databricks/. A profile can instead reuse a Databricks CLI profile (`profile = "…"`).

Needs the optional extra:  uv sync --extra databricks
"""
from __future__ import annotations

import datetime as dt
import re

from .. import RemoteError
from .base import ConfigField, Connector, Dialect


class DatabricksDialect(Dialect):
    name = "databricks"
    string_type = "STRING"
    supports_key_sampling = True

    def quote(self, name: str) -> str:
        return "`" + str(name).replace("`", "``") + "`"

    def count_if(self, cond: str) -> str:
        return f"count_if({cond})"

    def approx_distinct(self, expr: str) -> str:
        return f"approx_count_distinct({expr})"

    def try_cast(self, expr: str, type_: str) -> str:
        return f"try_cast({expr} AS {type_})"

    def ilike(self, expr: str, pattern: str) -> str:
        return f"{expr} ILIKE {pattern}"

    def tablesample(self, pct: float, seed: int | None = None) -> str:
        # `(n ROWS)` in Spark just takes the first n rows, so always a percentage
        return f" TABLESAMPLE ({pct} PERCENT)" + (f" REPEATABLE ({int(seed)})" if seed is not None else "")

    def random_order(self, seed: int | None = None) -> str:
        return f"rand({int(seed) if seed is not None else ''})"

    def hash_bucket(self, expr: str, buckets: int) -> str:
        return f"pmod(xxhash64({self.cast_string(expr)}), {int(buckets)})"   # xxhash64 is deterministic on Databricks


def hostname(conn) -> str:
    return re.sub(r"^https?://", "", conn.host or "").rstrip("/")


def http_path(conn) -> str:
    if not conn.warehouse_id:
        raise RemoteError(f"Connection '{conn.name}' has no SQL warehouse. List them with `bearings remote warehouses {conn.name}`, "
                          f"then: bearings remote add {conn.name} --warehouse <id>")
    return f"/sql/1.0/warehouses/{conn.warehouse_id}"


# ------------------------------------------------------------------ client factories (tests replace these)
def _default_workspace_client(conn):
    from databricks.sdk import WorkspaceClient
    if conn.profile:
        return WorkspaceClient(profile=conn.profile, product="bearings")
    return WorkspaceClient(host=conn.host, auth_type=conn.auth_type or None, product="bearings")


def _default_sql_connect(conn, client, session_configuration: dict | None = None):
    from databricks import sql
    # reuse the SDK's (cached, refreshed) credentials, so there is only one browser sign-in
    return sql.connect(server_hostname=client.config.host.replace("https://", "").rstrip("/") if client.config.host else hostname(conn),
                       http_path=http_path(conn), credentials_provider=lambda: client.config.authenticate,
                       user_agent_entry="bearings", session_configuration=session_configuration or None)


workspace_client_factory = _default_workspace_client
sql_connect_factory = _default_sql_connect
_clients: dict = {}   # (name, host, profile, auth_type) -> WorkspaceClient: changing the warehouse keeps the sign-in


def _enum(v):
    return getattr(v, "value", v) if v is not None else None


def _ts(ms):
    if ms in (None, ""):
        return None
    try:
        return dt.datetime.fromtimestamp(int(ms) / 1000, tz=dt.timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def _first_line(e: Exception) -> str:
    return str(e).splitlines()[0] if str(e) else type(e).__name__


class DatabricksConnector(Connector):
    type = "databricks"
    label = "Databricks"
    extra = "databricks"
    compute_label = "SQL warehouse"
    version_label = "Delta"
    fields = (
        ConfigField("host", "Workspace URL, e.g. https://adb-123.12.azuredatabricks.net"),
        ConfigField("warehouse_id", "SQL warehouse id (needed for profiling, pull and live queries)"),
        ConfigField("profile", "Reuse a Databricks CLI profile from ~/.databrickscfg instead of host/auth_type"),
        ConfigField("auth_type", "SDK auth type; default external-browser (Entra ID sign-in)", default="external-browser"),
    )
    dialect = DatabricksDialect()

    @classmethod
    def installed(cls) -> bool:
        try:
            import databricks.sdk  # noqa: F401
            import databricks.sql  # noqa: F401
            return True
        except ImportError:
            return False

    def validate(self) -> None:
        if not self.conn.host and not self.conn.profile:
            raise RemoteError("Give the workspace URL (--host https://adb-….azuredatabricks.net) or a Databricks CLI --profile")

    def describe(self) -> str:
        return f"{self.conn.host or 'profile ' + self.conn.profile}   warehouse {self.conn.warehouse_id or '—'}"

    def can_query(self) -> bool:
        return bool(self.conn.warehouse_id)

    def public_info(self) -> dict:
        return {**super().public_info(), "host": self.conn.host, "warehouse_id": self.conn.warehouse_id, "profile": self.conn.profile}

    # ------------------------------------------------------------ metadata
    @property
    def client(self):
        """The SDK client (kept for the connector's lifetime, so the OAuth token stays in memory)."""
        c = self.conn
        key = (c.name, c.host, c.profile, c.auth_type)
        if key not in _clients:
            if workspace_client_factory is _default_workspace_client:
                self.require()
            _clients[key] = workspace_client_factory(c)
        return _clients[key]

    @staticmethod
    def reset() -> None:
        _clients.clear()

    def whoami(self) -> str:
        me = self.client.current_user.me()
        return me.user_name or me.display_name or "?"

    def list_catalogs(self) -> list[str]:
        return sorted(c.name for c in self.client.catalogs.list())

    def list_schemas(self, catalog: str) -> list[dict]:
        try:
            return [{"schema": s.name, "comment": s.comment} for s in self.client.schemas.list(catalog_name=catalog)
                    if s.name != "information_schema"]
        except Exception as e:
            raise RemoteError(f"Could not list schemas in catalog {catalog}: {_first_line(e)}", self.label) from e

    def fetch_schema(self, catalog: str, schema: str) -> dict[str, dict]:
        out: dict[str, dict] = {}
        try:
            tables = list(self.client.tables.list(catalog_name=catalog, schema_name=schema))
        except Exception as e:  # SDK raises NotFound / PermissionDenied / auth errors
            raise RemoteError(f"Could not list tables in {catalog}.{schema}: {_first_line(e)}", self.label) from e
        for t in tables:
            props = t.properties or {}
            cols = []
            for i, c in enumerate(sorted(t.columns or [], key=lambda c: (c.position if c.position is not None else 1_000_000))):
                cols.append({"column_name": c.name, "ordinal": (c.position + 1) if c.position is not None else i + 1,
                             "data_type": (c.type_text or _enum(c.type_name) or "").upper(),
                             "nullable": c.nullable, "comment": c.comment or None})
            num = props.get("spark.sql.statistics.numRows")
            out[t.name] = {"table_type": _enum(t.table_type), "comment": t.comment or None,
                           "updated_at": _ts(t.updated_at), "row_count": int(num) if str(num or "").isdigit() else None,
                           "size_bytes": None, "columns": cols}
        return out

    def list_compute(self) -> list[dict]:
        try:
            whs = list(self.client.warehouses.list())
        except Exception as e:
            raise RemoteError(f"Could not list SQL warehouses: {_first_line(e)}", self.label) from e
        return [{"id": w.id, "name": w.name or "", "state": _enum(w.state) or "",
                 "kind": "serverless" if w.enable_serverless_compute else (_enum(w.warehouse_type) or "classic").lower(),
                 "size": w.cluster_size or "", "serverless": bool(w.enable_serverless_compute)} for w in whs]

    # ------------------------------------------------------------ SQL
    def sql_connect(self, session_configuration: dict | None = None):
        if sql_connect_factory is _default_sql_connect:
            self.require()
        if session_configuration:
            return sql_connect_factory(self.conn, self.client, session_configuration)
        return sql_connect_factory(self.conn, self.client)

    def session_settings(self, timeout_s: int) -> dict:
        return {"STATEMENT_TIMEOUT": str(int(timeout_s))}

    def set_timeout_sql(self, timeout_s: int) -> str | None:
        return f"SET STATEMENT_TIMEOUT = {int(timeout_s)}"

    def is_reconnectable(self, msg: str) -> bool:
        return super().is_reconnectable(msg) and not re.search(
            r"PARSE_SYNTAX|UNRESOLVED|TABLE_OR_VIEW_NOT_FOUND|INSUFFICIENT_PERMISSIONS|DIVIDE_BY_ZERO|CAST", msg)

    def clean_error(self, msg: str) -> str:
        m = re.search(r"\[([A-Z_]+(?:\.[A-Z_]+)?)\]\s*(.+?)(?:\sSQLSTATE|\n|$)", msg)
        return f"[{m.group(1)}] {m.group(2)}" if m else (msg.splitlines()[0] if msg else "Databricks error")

    def version_sql(self, table_ref: str) -> str | None:
        return f"DESCRIBE HISTORY {table_ref} LIMIT 1"
