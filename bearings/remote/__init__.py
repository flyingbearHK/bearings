"""Remote mode: Azure Databricks / Unity Catalog as a source.

Metadata (tables, columns, comments) is synced into DuckDB `_meta.remote_*` so search, annotations and
exports work locally and offline. Rows stay in Databricks; `bearings pull` copies a sample into DuckDB.

Everything that talks to Databricks needs the optional extra:  uv sync --extra databricks
"""


import logging

# the SQL connector logs a warning for every slow CloudFetch chunk (results downloaded from the workspace's
# storage account) – normal over a long distance, and noisy in the middle of `bearings cache` output
logging.getLogger("databricks.sql").setLevel(logging.ERROR)


class RemoteError(RuntimeError):
    """A user-facing problem with a remote source (missing extra, unknown connection, auth, network…)."""


def require_extra():
    try:
        import databricks.sdk  # noqa: F401
        import databricks.sql  # noqa: F401
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise RemoteError("Remote mode needs the Databricks extra. Install it with:  uv sync --extra databricks") from e
