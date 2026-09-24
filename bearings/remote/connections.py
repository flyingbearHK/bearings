"""Named connection profiles (~/.bearings/connections.toml) – one table per profile, no secrets.

    [dev]
    type = "databricks"          # which connector (bearings.remote.connectors); default databricks
    host = "https://adb-….azuredatabricks.net"
    warehouse_id = "…"

The settings a profile holds depend on its connector (`Connector.fields`). Sign-in is done by the
connector (for Databricks: browser OAuth through Entra ID, token cached by the Databricks SDK).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import RemoteError
from . import connectors

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib  # type: ignore

NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def config_dir() -> Path:
    return Path(os.environ.get("BEARINGS_HOME") or Path.home() / ".bearings").expanduser()


def config_path() -> Path:
    return config_dir() / "connections.toml"


@dataclass
class Connection:
    """A profile: a name, a connector type and that connector's settings (`conn.host`, `conn.get("host")`)."""
    name: str
    type: str = connectors.DEFAULT_TYPE
    settings: dict = field(default_factory=dict)

    def _field(self, key: str):
        try:
            cls = connectors.connector_class(self.type)
        except RemoteError:
            return None
        return next((f for f in cls.fields if f.key == key), None)

    def get(self, key: str, default=""):
        v = self.settings.get(key)
        if v not in (None, ""):
            return v
        f = self._field(key)
        return f.default if f and f.default else default

    def __getattr__(self, key: str):
        # connector settings read like attributes (conn.host, conn.warehouse_id); unknown names still fail
        if key.startswith("_") or key in ("name", "type", "settings"):
            raise AttributeError(key)
        if key in self.settings or self._field(key) is not None:
            return self.get(key)
        raise AttributeError(f"'{self.type}' connection has no setting '{key}'")

    @property
    def connector(self) -> "connectors.Connector":
        return connectors.for_connection(self)


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


_parsed: dict = {"key": None, "data": {}}


def _read() -> dict:
    p = config_path()
    try:
        st = p.stat()
    except FileNotFoundError:
        return {}
    key = (str(p), st.st_mtime_ns, st.st_size)
    if _parsed["key"] != key:  # re-parse only when the file changed (it is read on every remote query)
        _parsed["data"] = tomllib.loads(p.read_text(encoding="utf-8"))
        _parsed["key"] = key
    return _parsed["data"]


def load_all() -> dict[str, Connection]:
    out = {}
    for name, d in _read().items():
        if not isinstance(d, dict):
            continue
        settings = {k: v for k, v in d.items() if k != "type"}
        out[name] = Connection(name=name, type=str(d.get("type") or connectors.DEFAULT_TYPE).lower(), settings=settings)
    return out


def save_all(conns: dict[str, Connection]) -> Path:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Bearings – remote connection profiles. No secrets here: sign-in is done by each platform's own login.", ""]
    for c in sorted(conns.values(), key=lambda c: c.name):
        lines.append(f"[{c.name}]")
        lines.append(f"type = {_toml_value(c.type)}")
        try:
            order = [f.key for f in connectors.connector_class(c.type).fields]
        except RemoteError:
            order = []
        for k in order + sorted(k for k in c.settings if k not in order):
            v = c.settings.get(k)
            if v not in (None, ""):
                lines.append(f"{k} = {_toml_value(v)}")
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
    try:
        p.chmod(0o600)
    except OSError:  # pragma: no cover
        pass
    _parsed["key"] = None
    return p


def get(name: str) -> Connection:
    conns = load_all()
    if name not in conns:
        known = ", ".join(sorted(conns)) or "none yet"
        raise RemoteError(f"No connection called '{name}' (known: {known}). Add one: bearings remote add {name} --host https://adb-….azuredatabricks.net --warehouse <id>")
    return conns[name]


def upsert(name: str, type: str | None = None, **fields) -> Connection:
    """Create or update a profile. `fields` are connector settings; None leaves a setting unchanged."""
    if not NAME_RE.match(name):
        raise RemoteError("Connection names may only use letters, digits, '-' and '_'")
    conns = load_all()
    c = conns.get(name) or Connection(name=name, type=(type or connectors.DEFAULT_TYPE).lower())
    if type and type.lower() != c.type:
        c = Connection(name=name, type=type.lower())   # switching platform: old settings don't apply
    connectors.connector_class(c.type)                 # unknown type → clear error
    for k, v in fields.items():
        if v is not None:
            c.settings[k] = v
    connectors.connector_class(c.type)(c).validate()
    conns[name] = c
    save_all(conns)
    return c


def remove(name: str) -> bool:
    conns = load_all()
    if name not in conns:
        return False
    del conns[name]
    save_all(conns)
    return True


# ------------------------------------------------------------------ compatibility helpers
def workspace_client(conn: Connection):
    """The platform's metadata client (Databricks: the SDK WorkspaceClient), cached per profile."""
    return getattr(conn.connector, "client", None)


def sql_connect(conn: Connection, session_configuration: dict | None = None):
    return conn.connector.sql_connect(session_configuration)


def reset_clients():
    connectors.reset()
