"""Named Databricks connection profiles (~/.bearings/connections.toml) and client factories.

A profile holds no secrets: sign-in is browser OAuth through Entra ID (`auth_type="external-browser"`),
and the Databricks SDK caches/refreshes the token in its own cache (~/.databricks/). A profile can
instead point at an existing Databricks CLI profile in ~/.databrickscfg (`profile = "..."`).
"""
from __future__ import annotations

import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import RemoteError, require_extra

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
    name: str
    host: str = ""
    warehouse_id: str = ""
    profile: str = ""                       # optional ~/.databrickscfg profile to reuse instead of host/auth_type
    auth_type: str = "external-browser"     # browser sign-in (Entra ID); anything the SDK accepts works
    extra: dict = field(default_factory=dict)

    @property
    def hostname(self) -> str:
        return re.sub(r"^https?://", "", self.host).rstrip("/")

    @property
    def http_path(self) -> str:
        if not self.warehouse_id:
            raise RemoteError(f"Connection '{self.name}' has no SQL warehouse. List them with `bearings remote warehouses {self.name}`, "
                              f"then: bearings remote add {self.name} --warehouse <id>")
        return f"/sql/1.0/warehouses/{self.warehouse_id}"


def _toml_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def load_all() -> dict[str, Connection]:
    p = config_path()
    if not p.exists():
        return {}
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    out = {}
    for name, d in data.items():
        if not isinstance(d, dict):
            continue
        known = {k: d[k] for k in ("host", "warehouse_id", "profile", "auth_type") if k in d}
        extra = {k: v for k, v in d.items() if k not in known}
        out[name] = Connection(name=name, extra=extra, **known)
    return out


def save_all(conns: dict[str, Connection]) -> Path:
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Bearings – Databricks connection profiles. No secrets here: sign-in is browser OAuth.", ""]
    for c in sorted(conns.values(), key=lambda c: c.name):
        lines.append(f"[{c.name}]")
        d = asdict(c)
        for k in ("host", "warehouse_id", "profile", "auth_type"):
            if d[k]:
                lines.append(f"{k} = {_toml_value(d[k])}")
        for k, v in (c.extra or {}).items():
            lines.append(f"{k} = {_toml_value(v)}")
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
    try:
        p.chmod(0o600)
    except OSError:  # pragma: no cover
        pass
    return p


def get(name: str) -> Connection:
    conns = load_all()
    if name not in conns:
        known = ", ".join(sorted(conns)) or "none yet"
        raise RemoteError(f"No connection called '{name}' (known: {known}). Add one: bearings remote add {name} --host https://adb-….azuredatabricks.net --warehouse <id>")
    return conns[name]


def upsert(name: str, **fields) -> Connection:
    if not NAME_RE.match(name):
        raise RemoteError("Connection names may only use letters, digits, '-' and '_'")
    conns = load_all()
    c = conns.get(name) or Connection(name=name)
    for k, v in fields.items():
        if v is not None:
            setattr(c, k, v)
    if not c.host and not c.profile:
        raise RemoteError("Give the workspace URL (--host https://adb-….azuredatabricks.net) or a Databricks CLI --profile")
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


# ------------------------------------------------------------------ clients (tests replace these factories)
_clients: dict = {}


def _default_workspace_client(conn: Connection):
    require_extra()
    from databricks.sdk import WorkspaceClient
    if conn.profile:
        return WorkspaceClient(profile=conn.profile, product="bearings")
    return WorkspaceClient(host=conn.host, auth_type=conn.auth_type or None, product="bearings")


def _default_sql_connect(conn: Connection, client, session_configuration: dict | None = None):
    require_extra()
    from databricks import sql
    # reuse the SDK's (cached, refreshed) credentials, so there is only one browser sign-in
    return sql.connect(server_hostname=client.config.host.replace("https://", "").rstrip("/") if client.config.host else conn.hostname,
                       http_path=conn.http_path, credentials_provider=lambda: client.config.authenticate,
                       user_agent_entry="bearings", session_configuration=session_configuration or None)


workspace_client_factory = _default_workspace_client
sql_connect_factory = _default_sql_connect


def workspace_client(conn: Connection):
    """One cached SDK client per connection (keeps the OAuth token in memory for the server's lifetime)."""
    key = (conn.name, conn.host, conn.profile, conn.auth_type)
    if key not in _clients:
        _clients[key] = workspace_client_factory(conn)
    return _clients[key]


def sql_connect(conn: Connection, session_configuration: dict | None = None):
    if session_configuration:
        return sql_connect_factory(conn, workspace_client(conn), session_configuration)
    return sql_connect_factory(conn, workspace_client(conn))


def reset_clients():
    _clients.clear()
