"""Remote mode: attach schemas from a remote platform as sources.

Metadata (tables, columns, comments) is synced into DuckDB `_meta.remote_*` so search, annotations and
exports work locally and offline. Rows stay remote; `bearings pull` / `cache` copy (a sample of) them into
DuckDB, and live queries run on the platform's SQL engine.

Platforms plug in as connectors (`bearings.remote.connectors`); Azure Databricks / Unity Catalog is built in
and needs the optional extra:  uv sync --extra databricks
"""


import logging

# the SQL connector logs a warning for every slow CloudFetch chunk (results downloaded from the workspace's
# storage account) – normal over a long distance, and noisy in the middle of `bearings cache` output
logging.getLogger("databricks.sql").setLevel(logging.ERROR)


class RemoteError(RuntimeError):
    """A user-facing problem with a remote source (missing extra, unknown connection, auth, network…).
    `platform` names where it came from ("Databricks") when a connector raised it."""

    def __init__(self, msg: str = "", platform: str | None = None):
        super().__init__(msg)
        self.platform = platform


def require_extra(type_: str = "databricks"):
    """Raise a clear RemoteError when a connector's optional dependencies aren't installed."""
    from .connectors import connector_class
    cls = connector_class(type_)
    if not cls.installed():  # pragma: no cover - depends on the environment
        raise RemoteError(f"Remote mode for {cls.label} needs an extra. Install it with:  uv sync --extra {cls.extra}")
