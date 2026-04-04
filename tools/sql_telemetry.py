"""Agentic Ops Advisor — SQL Telemetry Tool.

Queries synthetic infrastructure telemetry (GPU, network, cost, incidents) from
SQLite (local dev) or Azure SQL (production).  All data is **synthetic** and for
demonstration purposes only.

Each public function wraps its work in an ``execute_tool`` OpenTelemetry span so
tool calls appear as child spans of the top-level ``invoke_agent`` span.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from typing import Any

from agent.tracing import execute_tool_span

logger = logging.getLogger(__name__)

_DB_PATH = os.getenv("SQLITE_DB_PATH", "data/telemetry.db")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def query_telemetry(query: str) -> dict[str, Any]:
    """Return synthetic telemetry matching *query*.

    Args:
        query: Natural-language query string (used to derive ``query_type``).

    Returns:
        A dict with keys ``query_type``, ``rows``, ``row_count``, and ``summary``.
    """
    query_type = _infer_query_type(query)
    with execute_tool_span("sql_telemetry", query_type=query_type) as span:
        rows = _fetch_rows(query_type)
        span.set_attribute("tool.row_count", len(rows))
        return {
            "query_type": query_type,
            "rows": rows,
            "row_count": len(rows),
            "summary": _summarize(query_type, rows),
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _infer_query_type(query: str) -> str:
    lower = query.lower()
    if any(kw in lower for kw in ("gpu", "compute", "utilization", "utilisation")):
        return "gpu_utilization"
    if any(kw in lower for kw in ("network", "bandwidth", "latency")):
        return "network"
    if any(kw in lower for kw in ("cost", "spend", "budget")):
        return "cost"
    if any(kw in lower for kw in ("incident", "alert", "error", "failure")):
        return "incidents"
    return "general"


def _fetch_rows(query_type: str) -> list[dict[str, Any]]:
    """Try to fetch rows from the local SQLite database; fall back to stubs."""
    try:
        return _fetch_from_sqlite(query_type)
    except Exception as exc:
        logger.debug("SQLite unavailable (%s) — returning stub data", exc)
        return _stub_rows(query_type)


def _fetch_from_sqlite(query_type: str) -> list[dict[str, Any]]:
    """Query the local SQLite telemetry database."""
    sql_map = {
        "gpu_utilization": "SELECT * FROM gpu_metrics ORDER BY timestamp DESC LIMIT 10",
        "network": "SELECT * FROM network_metrics ORDER BY timestamp DESC LIMIT 10",
        "cost": "SELECT * FROM cost_metrics ORDER BY timestamp DESC LIMIT 10",
        "incidents": "SELECT * FROM incidents ORDER BY timestamp DESC LIMIT 10",
        "general": "SELECT * FROM telemetry ORDER BY timestamp DESC LIMIT 10",
    }
    sql = sql_map.get(query_type, sql_map["general"])
    with sqlite3.connect(_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


def _stub_rows(query_type: str) -> list[dict[str, Any]]:
    """Return hard-coded synthetic rows (used when SQLite is unavailable)."""
    stubs: dict[str, list[dict[str, Any]]] = {
        "gpu_utilization": [
            {"node": "gpu-node-01", "utilization_pct": 87, "timestamp": "2025-01-01T00:00:00Z"},
            {"node": "gpu-node-02", "utilization_pct": 92, "timestamp": "2025-01-01T00:01:00Z"},
        ],
        "network": [
            {"interface": "eth0", "bandwidth_mbps": 950, "latency_ms": 1.2, "timestamp": "2025-01-01T00:00:00Z"},
        ],
        "cost": [
            {"resource": "gpu-cluster", "daily_cost_usd": 1234.56, "timestamp": "2025-01-01T00:00:00Z"},
        ],
        "incidents": [
            {"id": "INC-001", "severity": "P2", "description": "GPU memory OOM on node-03", "timestamp": "2025-01-01T00:00:00Z"},
        ],
        "general": [
            {"metric": "cpu_utilization", "value": 45.2, "timestamp": "2025-01-01T00:00:00Z"},
        ],
    }
    return stubs.get(query_type, stubs["general"])


def _summarize(query_type: str, rows: list[dict[str, Any]]) -> str:
    if not rows:
        return f"No {query_type} data available."
    return f"{len(rows)} {query_type} record(s) retrieved (synthetic demo data)."
