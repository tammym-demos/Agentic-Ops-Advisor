"""SQL telemetry tool surface for Agentic Ops Advisor.

Supports two database backends selected via the DB_MODE environment variable:
  - ``sqlite``  (default / local dev): reads from ``data/telemetry.db``
  - Any other value is treated as a pyodbc connection string for Azure SQL.

All queries return plain Python dicts so they can be serialised to JSON and
handed back to the LLM as tool results.

NOTE: All data queried here is synthetic. This module never touches production
systems.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Generator

# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_SQLITE_PATH = os.path.join(_REPO_ROOT, "data", "telemetry.db")


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

@contextmanager
def get_db_connection() -> Generator[Any, None, None]:
    """Yield a database connection (SQLite or Azure SQL).

    The connection is closed automatically when the context manager exits.
    Uses ``DB_MODE`` env var to select the backend.
    """
    mode = os.environ.get("DB_MODE", "sqlite").strip().lower()

    if mode == "sqlite":
        db_path = os.environ.get("SQLITE_DB_PATH", _DEFAULT_SQLITE_PATH)
        if not os.path.exists(db_path):
            raise FileNotFoundError(
                f"SQLite database not found at {db_path}. "
                "Run `python scripts/setup_local_db.py` first."
            )
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    else:
        # Azure SQL via pyodbc
        try:
            import pyodbc  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError("pyodbc is required for Azure SQL mode. Install it with `pip install pyodbc`.") from exc
        conn = pyodbc.connect(mode)
        try:
            yield conn
        finally:
            conn.close()


def _rows_to_dicts(cursor: Any) -> list[dict]:
    """Convert cursor results to a list of plain dicts."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# ---------------------------------------------------------------------------
# Query functions (tool surface)
# ---------------------------------------------------------------------------

def query_gpu_utilization(hours_back: int = 24) -> list[dict]:
    """Return GPU utilisation metrics for the last *hours_back* hours.

    Includes average, min, and max per (cluster, node) window so the LLM can
    spot anomalies quickly.

    Args:
        hours_back: Look-back window in hours (default 24).

    Returns:
        List of dicts with keys: cluster, node, avg_util, min_util, max_util,
        avg_mem, sample_count.
    """
    sql = """
        SELECT
            cluster,
            node,
            ROUND(AVG(utilization_pct), 2)  AS avg_util,
            ROUND(MIN(utilization_pct), 2)  AS min_util,
            ROUND(MAX(utilization_pct), 2)  AS max_util,
            ROUND(AVG(mem_pct), 2)          AS avg_mem,
            COUNT(*)                         AS sample_count
        FROM telemetry_gpu
        WHERE ts >= datetime('now', :window)
        GROUP BY cluster, node
        ORDER BY avg_util ASC
    """
    with get_db_connection() as conn:
        cur = conn.execute(sql, {"window": f"-{hours_back} hours"})
        return _rows_to_dicts(cur)


def query_gpu_utilization_timeseries(hours_back: int = 24, cluster: str | None = None) -> list[dict]:
    """Return raw hourly GPU utilisation timeseries.

    Args:
        hours_back: Look-back window in hours.
        cluster: Optional cluster filter.

    Returns:
        List of dicts with keys: ts, cluster, node, utilization_pct, mem_pct.
    """
    params: dict[str, Any] = {"window": f"-{hours_back} hours"}
    cluster_filter = ""
    if cluster:
        cluster_filter = "AND cluster = :cluster"
        params["cluster"] = cluster

    sql = f"""
        SELECT ts, cluster, node, utilization_pct, mem_pct
        FROM telemetry_gpu
        WHERE ts >= datetime('now', :window)
        {cluster_filter}
        ORDER BY ts, cluster, node
    """
    with get_db_connection() as conn:
        cur = conn.execute(sql, params)
        return _rows_to_dicts(cur)


def query_network_telemetry(hours_back: int = 24) -> list[dict]:
    """Return network telemetry summary for the last *hours_back* hours.

    Args:
        hours_back: Look-back window in hours (default 24).

    Returns:
        List of dicts with keys: site, avg_latency_ms, max_latency_ms,
        avg_loss_pct, avg_throughput_gbps, sample_count.
    """
    sql = """
        SELECT
            site,
            ROUND(AVG(latency_ms), 3)       AS avg_latency_ms,
            ROUND(MAX(latency_ms), 3)       AS max_latency_ms,
            ROUND(AVG(loss_pct), 3)         AS avg_loss_pct,
            ROUND(AVG(throughput_gbps), 3)  AS avg_throughput_gbps,
            COUNT(*)                         AS sample_count
        FROM telemetry_net
        WHERE ts >= datetime('now', :window)
        GROUP BY site
        ORDER BY avg_latency_ms DESC
    """
    with get_db_connection() as conn:
        cur = conn.execute(sql, {"window": f"-{hours_back} hours"})
        return _rows_to_dicts(cur)


def query_network_timeseries(hours_back: int = 96, site: str | None = None) -> list[dict]:
    """Return raw hourly network timeseries (useful for spike detection).

    Args:
        hours_back: Look-back window in hours (default 96 to cover 4 days).
        site: Optional site filter.

    Returns:
        List of dicts with keys: ts, site, latency_ms, loss_pct, throughput_gbps.
    """
    params: dict[str, Any] = {"window": f"-{hours_back} hours"}
    site_filter = ""
    if site:
        site_filter = "AND site = :site"
        params["site"] = site

    sql = f"""
        SELECT ts, site, latency_ms, loss_pct, throughput_gbps
        FROM telemetry_net
        WHERE ts >= datetime('now', :window)
        {site_filter}
        ORDER BY ts, site
    """
    with get_db_connection() as conn:
        cur = conn.execute(sql, params)
        return _rows_to_dicts(cur)


def query_cost_trends(days_back: int = 7) -> list[dict]:
    """Return daily cost per cluster for the last *days_back* days.

    Args:
        days_back: Look-back window in days (default 7).

    Returns:
        List of dicts with keys: ts, cluster, cost_usd, token_cost_usd.
    """
    sql = """
        SELECT ts, cluster, cost_usd, token_cost_usd
        FROM telemetry_cost
        WHERE ts >= datetime('now', :window)
        ORDER BY ts DESC, cluster
    """
    with get_db_connection() as conn:
        cur = conn.execute(sql, {"window": f"-{days_back} days"})
        return _rows_to_dicts(cur)


def query_incidents(status: str = "open") -> list[dict]:
    """Return incidents filtered by status.

    Args:
        status: One of ``"open"``, ``"resolved"``, or ``"all"`` (default ``"open"``).

    Returns:
        List of dicts with keys: ts, service, symptom, severity, status.
    """
    if status == "all":
        sql = "SELECT ts, service, symptom, severity, status FROM incidents ORDER BY ts DESC"
        params: dict[str, str] = {}
    else:
        sql = "SELECT ts, service, symptom, severity, status FROM incidents WHERE status = :status ORDER BY ts DESC"
        params = {"status": status}

    with get_db_connection() as conn:
        cur = conn.execute(sql, params)
        return _rows_to_dicts(cur)


# ---------------------------------------------------------------------------
# Tool definitions for LLM function-calling
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "query_gpu_utilization",
            "description": (
                "Query GPU utilisation and memory statistics aggregated per (cluster, node) "
                "for a given look-back window. Use this to detect GPU underutilisation, "
                "overheating risks, or workload imbalances."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hours_back": {
                        "type": "integer",
                        "description": "Number of hours to look back (default 24).",
                        "default": 24,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_gpu_utilization_timeseries",
            "description": (
                "Return raw hourly GPU utilisation timeseries for detailed anomaly inspection. "
                "Use when you need to see the exact timestamps of a drop or spike."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hours_back": {
                        "type": "integer",
                        "description": "Number of hours to look back (default 24).",
                        "default": 24,
                    },
                    "cluster": {
                        "type": "string",
                        "description": "Optional cluster name to filter (e.g. 'gpu-cluster-01').",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_network_telemetry",
            "description": (
                "Query network telemetry (latency, packet loss, throughput) aggregated per site "
                "for a given look-back window. Use to detect connectivity issues or SLO violations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hours_back": {
                        "type": "integer",
                        "description": "Number of hours to look back (default 24).",
                        "default": 24,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_network_timeseries",
            "description": (
                "Return raw hourly network telemetry timeseries for spike detection and "
                "change-correlation analysis. Default look-back is 96 h to cover recent days."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hours_back": {
                        "type": "integer",
                        "description": "Number of hours to look back (default 96).",
                        "default": 96,
                    },
                    "site": {
                        "type": "string",
                        "description": "Optional site filter (e.g. 'eastus2-primary').",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_cost_trends",
            "description": (
                "Return daily infrastructure cost per cluster for a given look-back window. "
                "Use to identify cost spikes and correlate with incidents or changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_back": {
                        "type": "integer",
                        "description": "Number of days to look back (default 7).",
                        "default": 7,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_incidents",
            "description": (
                "Return current or historical incidents. Use to check whether a symptom "
                "is already tracked, find related open tickets, and understand severity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["open", "resolved", "all"],
                        "description": "Filter by incident status (default 'open').",
                        "default": "open",
                    }
                },
                "required": [],
            },
        },
    },
]

# Map tool name → callable (used by the local runner)
TOOL_CALLABLES: dict[str, Any] = {
    "query_gpu_utilization": query_gpu_utilization,
    "query_gpu_utilization_timeseries": query_gpu_utilization_timeseries,
    "query_network_telemetry": query_network_telemetry,
    "query_network_timeseries": query_network_timeseries,
    "query_cost_trends": query_cost_trends,
    "query_incidents": query_incidents,
}
