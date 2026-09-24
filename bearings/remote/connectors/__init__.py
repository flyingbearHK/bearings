"""Registry of remote-platform connectors (see `base.Connector`).

Built in: Databricks. A connection profile's `type` (default "databricks") picks the connector:

    [dev]
    type = "databricks"
    host = "https://adb-….azuredatabricks.net"
    warehouse_id = "…"

Adding a platform = a `Connector` subclass + `register(MyConnector)`; `attach`, `sync`, `profile`, `pull`,
`cache`, live queries and the app then work with it unchanged.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from .. import RemoteError
from .base import ConfigField, Connector, Dialect, type_family
from .databricks import DatabricksConnector

if TYPE_CHECKING:  # pragma: no cover
    from ..connections import Connection

DEFAULT_TYPE = "databricks"
_types: dict[str, type[Connector]] = {}
_instances: dict[tuple, Connector] = {}


def register(cls: type[Connector]) -> None:
    if not cls.type:
        raise ValueError("A connector needs a `type`")
    _types[cls.type] = cls


def types() -> dict[str, type[Connector]]:
    return dict(_types)


def connector_class(type_: str | None) -> type[Connector]:
    t = (type_ or DEFAULT_TYPE).lower()
    if t not in _types:
        raise RemoteError(f"Unknown connection type '{type_}' (known: {', '.join(sorted(_types))})")
    return _types[t]


def for_connection(conn: "Connection") -> Connector:
    """One connector instance per profile (and its settings): keeps sign-in state for the process lifetime."""
    key = (conn.name, conn.type, tuple(sorted((k, str(v)) for k, v in conn.settings.items())))
    inst = _instances.get(key)
    if inst is None:
        inst = _instances[key] = connector_class(conn.type)(conn)
    return inst


def for_name(name: str) -> Connector:
    from .. import connections as cx
    return for_connection(cx.get(name))


def dialect_for(conn_name: str | None) -> Dialect:
    """The SQL dialect of a named connection (the default type's when the profile is gone)."""
    from .. import connections as cx
    try:
        c = cx.load_all().get(conn_name or "")
    except Exception:
        c = None
    return connector_class(c.type if c else DEFAULT_TYPE).dialect


def platform(conn_name: str | None) -> dict:
    """{type, label, compute_label, version_label} for a connection name – for labels in the app."""
    from .. import connections as cx
    try:
        c = cx.load_all().get(conn_name or "")
    except Exception:
        c = None
    cls = connector_class(c.type if c else DEFAULT_TYPE)
    return {"type": cls.type, "label": cls.label, "compute_label": cls.compute_label, "version_label": cls.version_label}


def any_installed() -> bool:
    return any(cls.installed() for cls in _types.values())


def reset() -> None:
    """Forget connector instances (and their signed-in clients)."""
    _instances.clear()
    for cls in _types.values():
        if hasattr(cls, "reset"):
            cls.reset()


register(DatabricksConnector)

__all__ = ["ConfigField", "Connector", "Dialect", "DEFAULT_TYPE", "register", "types", "connector_class", "for_connection",
           "for_name", "dialect_for", "platform", "any_installed", "reset", "type_family"]
