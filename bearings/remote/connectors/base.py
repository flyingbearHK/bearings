"""The remote-source abstraction: what Bearings needs from a remote platform.

A remote source has two halves, and a connector provides both:

1. **Metadata** (`list_catalogs`, `list_schemas`, `fetch_schema`, `whoami`, `list_compute`) – read from the
   platform's catalog API; used by `attach` / `sync`, which cache it in DuckDB `_meta.remote_*`.
2. **SQL** (`sql_connect` + a `Dialect`) – live queries for samples, key checks, lookups, value search,
   profiling, `pull` / `cache` and the SQL console. The rest of Bearings writes its queries through the
   dialect, so it never hard-codes one engine's SQL.

The cursor returned by `sql_connect(...).cursor()` must offer the DB-API basics plus Arrow fetches:
`execute(sql, params: dict | None)`, `fetchone()`, `fetchall_arrow()`, `fetchmany_arrow(n)`, `close()`
(`params` use the dialect's `param()` placeholders). The Databricks SQL connector does this natively; a
connector for another engine wraps its driver to match.

To add a platform: subclass `Connector` (and `Dialect` where its SQL differs), then
`bearings.remote.connectors.register(MyConnector)`. See `databricks.py` for the reference implementation.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from .. import RemoteError

if TYPE_CHECKING:  # pragma: no cover
    from ..connections import Connection


@dataclass(frozen=True)
class ConfigField:
    """One setting of a connection profile (stored in ~/.bearings/connections.toml – never a secret)."""
    key: str
    help: str = ""
    required: bool = False
    default: str = ""


# ====================================================================== SQL dialect
class Dialect:
    """How to write SQL for one remote engine. The defaults are ANSI SQL; connectors override what differs."""

    name: ClassVar[str] = "ansi"
    string_type: ClassVar[str] = "VARCHAR"
    supports_key_sampling: ClassVar[bool] = False   # hash_bucket() available → join-consistent samples

    # ------------------------------------------------------------ names
    def quote(self, name: str) -> str:
        return '"' + str(name).replace('"', '""') + '"'

    def table_ref(self, catalog: str | None, schema: str | None, table: str) -> str:
        return ".".join(self.quote(x) for x in (catalog, schema, table) if x)

    def type_family(self, t: str) -> str:
        """string | numeric | temporal | bool | other, from the engine's type name."""
        return type_family(t)

    # ------------------------------------------------------------ expressions
    def param(self, name: str) -> str:
        """Placeholder for a named parameter in `cursor.execute(sql, {name: value})`."""
        return f":{name}"

    def cast_string(self, expr: str) -> str:
        return f"CAST({expr} AS {self.string_type})"

    def try_cast(self, expr: str, type_: str) -> str:
        return f"CAST({expr} AS {type_})"

    def count_if(self, cond: str) -> str:
        return f"count(CASE WHEN {cond} THEN 1 END)"

    def approx_distinct(self, expr: str) -> str:
        return f"count(DISTINCT {expr})"

    def ilike(self, expr: str, pattern: str) -> str:
        return f"lower({expr}) LIKE lower({pattern})"

    def blank_count(self, expr: str) -> str:
        return self.count_if(f"trim({expr}) = ''")

    # ------------------------------------------------------------ sampling
    def tablesample(self, pct: float, seed: int | None = None) -> str:
        """Clause after the table name for a random ~pct % sample ('' = not supported: callers fall back to
        ORDER BY random LIMIT n)."""
        return ""

    def random_order(self, seed: int | None = None) -> str:
        return "random()"

    def hash_bucket(self, expr: str, buckets: int) -> str:
        """Deterministic bucket 0..buckets-1 of a value (same on every table) – for join-consistent samples."""
        raise RemoteError(f"{self.name}: key-consistent sampling isn't supported")


_NON_SCALAR = re.compile(r"^(ARRAY|MAP|STRUCT|VARIANT|BINARY|BLOB|BYTEA|VARBINARY|INTERVAL|OBJECT|GEOGRAPHY|GEOMETRY|VOID|JSON|UNION|LIST)")
_NUMERIC = re.compile(r"^(TINYINT|SMALLINT|INT|INTEGER|BIGINT|HUGEINT|UBIGINT|UINTEGER|USMALLINT|UTINYINT|LONG|SHORT|BYTE|"
                      r"FLOAT|DOUBLE|REAL|DECIMAL|DEC|NUMERIC|NUMBER)")


def type_family(t: str) -> str:
    """Engine-neutral type family (covers Spark / Databricks, DuckDB and common ANSI names)."""
    u = (t or "").strip().upper()
    if _NON_SCALAR.match(u) or u.endswith("[]"):
        return "other"
    if u in ("BOOLEAN", "BOOL"):
        return "bool"
    if re.match(r"^(DATE|TIMESTAMP|DATETIME|TIME)", u):
        return "temporal"
    if re.match(r"^(STRING|VARCHAR|CHAR|TEXT|NVARCHAR|NCHAR|UUID)", u):
        return "string"
    if _NUMERIC.match(u):
        return "numeric"
    return "other"


# ====================================================================== connector
class Connector(ABC):
    """A remote platform Bearings can attach schemas from. One instance per connection profile."""

    type: ClassVar[str] = ""                 # stored as `type = "…"` in connections.toml
    label: ClassVar[str] = ""                # shown in the app and CLI ("Databricks")
    extra: ClassVar[str | None] = None       # `uv sync --extra <extra>` installs its dependencies
    compute_label: ClassVar[str] = "compute"             # what runs SQL ("SQL warehouse")
    version_label: ClassVar[str | None] = None           # table versioning shown next to cached copies ("Delta")
    fields: ClassVar[tuple[ConfigField, ...]] = ()
    dialect: ClassVar[Dialect] = Dialect()

    def __init__(self, conn: "Connection"):
        self.conn = conn

    # ------------------------------------------------------------ install / config
    @classmethod
    def installed(cls) -> bool:
        """True when the connector's Python dependencies are importable."""
        return True

    def require(self) -> None:
        if not self.installed():
            raise RemoteError(f"{self.label} support needs an extra. Install it with:  uv sync --extra {self.extra}")

    def validate(self) -> None:
        """Raise RemoteError when the profile can't work (called when it is saved)."""
        missing = [f.key for f in self.fields if f.required and not self.conn.get(f.key)]
        if missing:
            raise RemoteError(f"{self.label} connection '{self.conn.name}' needs: {', '.join(missing)}")

    def describe(self) -> str:
        """One line for `bearings remote list`."""
        return ", ".join(f"{f.key}={self.conn.get(f.key)}" for f in self.fields if self.conn.get(f.key))

    def can_query(self) -> bool:
        """Is the SQL side configured (e.g. a warehouse chosen)? Metadata sync works without it."""
        return True

    def public_info(self) -> dict:
        """What the app may show about the profile (no secrets – profiles hold none anyway)."""
        return {"name": self.conn.name, "type": self.type, "label": self.label, "compute_label": self.compute_label,
                "can_query": self.can_query(), "describe": self.describe()}

    # ------------------------------------------------------------ metadata
    @abstractmethod
    def whoami(self) -> str:
        """Sign in (if needed) and return the user name."""

    @abstractmethod
    def list_catalogs(self) -> list[str]: ...

    @abstractmethod
    def list_schemas(self, catalog: str) -> list[dict]:
        """[{schema, comment}] in a catalog."""

    @abstractmethod
    def fetch_schema(self, catalog: str, schema: str) -> dict[str, dict]:
        """{table: {table_type, comment, updated_at, row_count, size_bytes,
                    columns: [{column_name, ordinal, data_type, nullable, comment}]}}"""

    def list_compute(self) -> list[dict]:
        """[{id, name, state, kind, size}] of what can run SQL (empty when not applicable)."""
        return []

    # ------------------------------------------------------------ SQL
    @abstractmethod
    def sql_connect(self, session_configuration: dict | None = None):
        """A DB-API connection whose cursors support the Arrow fetches described in the module docstring."""

    def session_settings(self, timeout_s: int) -> dict:
        """Session configuration applied when a pooled connection opens."""
        return {}

    def set_timeout_sql(self, timeout_s: int) -> str | None:
        """Statement that changes the statement timeout on an open session (None: not supported)."""
        return None

    def is_reconnectable(self, msg: str) -> bool:
        """Does this error mean the session is gone (reopen and retry once) rather than a SQL error?"""
        return bool(re.search(r"session|connection|closed|expired|reset by peer|broken pipe|invalid.*handle", msg, re.I))

    def clean_error(self, msg: str) -> str:
        return msg.splitlines()[0] if msg else f"{self.label} error"

    def version_sql(self, table_ref: str) -> str | None:
        """A query whose result has a `version` column holding the table's current data version (e.g. Delta),
        used to tell whether a local copy is outdated. None: the platform has no table versions."""
        return None

    def table_version(self, cur, table_ref: str) -> int | None:
        sql = self.version_sql(table_ref)
        if not sql:
            return None
        try:
            cur.execute(sql)
            tbl = cur.fetchall_arrow()
            if tbl.num_rows and "version" in tbl.column_names:
                return int(tbl.column("version")[0].as_py())
        except Exception:  # views, non-versioned tables, no permission on history
            pass
        return None
