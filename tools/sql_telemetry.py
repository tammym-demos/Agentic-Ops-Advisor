"""SQL Telemetry Query Tool — queries synthetic infrastructure telemetry.

Dual-backend support:
  - DB_MODE=sqlite  → aiosqlite against data/telemetry.db  (default / local dev)
  - DB_MODE=azure_sql → pyodbc against Azure SQL (connection string from env)

Exposes:
  - ``TOOL_SCHEMA``      — Azure AI Agent Service function definition dict
  - ``query_telemetry``  — async function the agent calls directly
  - ``get_tool_definition`` — helper that returns the schema dict
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Telemetry table metadata (used for schema validation and help text)
# ---------------------------------------------------------------------------

TELEMETRY_TABLES = {
    "telemetry_gpu": {
        "description": "GPU utilization and memory per cluster/node.",
        "columns": ["ts", "cluster", "node", "utilization_pct", "mem_pct"],
    },
    "telemetry_net": {
        "description": "Network latency, packet loss and throughput per site.",
        "columns": ["ts", "site", "latency_ms", "loss_pct", "throughput_gbps"],
    },
    "telemetry_cost": {
        "description": "Hourly cost samples per cluster.",
        "columns": ["ts", "cluster", "cost_usd", "token_cost_usd"],
    },
    "incidents": {
        "description": "Infrastructure incident log with severity, status and linked service.",
        "columns": ["ts", "service", "symptom", "severity", "status"],
    },
}

# Pre-built aggregate query templates ----------------------------------------
# Each template uses named :param style so they are safe against injection.

_AGG_QUERIES: dict[str, str] = {
    "gpu_avg_util_1h": (
        "SELECT cluster, node, AVG(utilization_pct) AS avg_util_pct, MAX(utilization_pct) AS max_util_pct, "
        "MIN(utilization_pct) AS min_util_pct "
        "FROM telemetry_gpu "
        "WHERE ts >= datetime('now', '-1 hour') "
        "GROUP BY cluster, node ORDER BY avg_util_pct DESC"
    ),
    "gpu_avg_util_24h": (
        "SELECT cluster, node, AVG(utilization_pct) AS avg_util_pct, MAX(utilization_pct) AS max_util_pct, "
        "MIN(utilization_pct) AS min_util_pct "
        "FROM telemetry_gpu "
        "WHERE ts >= datetime('now', '-24 hours') "
        "GROUP BY cluster, node ORDER BY avg_util_pct DESC"
    ),
    "net_avg_latency_1h": (
        "SELECT site, AVG(latency_ms) AS avg_latency_ms, MAX(latency_ms) AS max_latency_ms, "
        "AVG(loss_pct) AS avg_loss_pct "
        "FROM telemetry_net "
        "WHERE ts >= datetime('now', '-1 hour') "
        "GROUP BY site ORDER BY avg_latency_ms DESC"
    ),
    "cost_by_service_24h": (
        "SELECT cluster, SUM(cost_usd) AS total_cost_usd, SUM(token_cost_usd) AS total_token_usd "
        "FROM telemetry_cost "
        "WHERE ts >= datetime('now', '-24 hours') "
        "GROUP BY cluster ORDER BY total_cost_usd DESC"
    ),
    "open_incidents": (
        "SELECT ts, service, symptom, severity, status "
        "FROM incidents "
        "WHERE status != 'resolved' "
        "ORDER BY CASE severity WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, ts DESC"
    ),
    "recent_incidents_24h": (
        "SELECT ts, service, symptom, severity, status "
        "FROM incidents "
        "WHERE ts >= datetime('now', '-24 hours') "
        "ORDER BY ts DESC"
    ),
}

# ---------------------------------------------------------------------------
# Safety: only allow SELECT statements
# ---------------------------------------------------------------------------

_SAFE_PATTERN = re.compile(r"^\s*SELECT\b", re.IGNORECASE)
_ALLOWED_TABLES = set(TELEMETRY_TABLES.keys())


def _validate_sql(sql: str) -> None:
    """Raise ValueError if *sql* is not a safe SELECT-only query."""
    if not _SAFE_PATTERN.match(sql):
        raise ValueError("Only SELECT statements are permitted.")
    # Rough check: ensure the query references only known tables
    lowered = sql.lower()
    found_table = any(tbl in lowered for tbl in _ALLOWED_TABLES)
    if not found_table:
        raise ValueError(
            f"Query must reference at least one of the known tables: {sorted(_ALLOWED_TABLES)}"
        )


# ---------------------------------------------------------------------------
# Backend execution
# ---------------------------------------------------------------------------

_DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "telemetry.db")


async def _run_sqlite(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    """Execute *sql* against the local SQLite database and return structured results."""
    try:
        import aiosqlite  # noqa: PLC0415 — optional dep check inside function
    except ImportError as exc:
        raise RuntimeError("aiosqlite is required for SQLite mode. Install it with: pip install aiosqlite") from exc

    db_path = os.environ.get("SQLITE_DB_PATH", _DEFAULT_DB_PATH)
    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(sql, params) as cursor:
            rows = await cursor.fetchall()
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            return {
                "columns": columns,
                "rows": [dict(row) for row in rows],
                "row_count": len(rows),
            }


def _run_azure_sql(sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
    """Execute *sql* against Azure SQL and return structured results."""
    try:
        import pyodbc  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError("pyodbc is required for Azure SQL mode. Install it with: pip install pyodbc") from exc

    conn_str = os.environ.get("DB_CONNECTION_STRING", "")
    if not conn_str:
        raise RuntimeError("DB_CONNECTION_STRING environment variable is not set for Azure SQL mode.")

    with pyodbc.connect(conn_str, timeout=30) as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        columns = [col[0] for col in cursor.description] if cursor.description else []
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------


async def query_telemetry(
    *,
    table: str | None = None,
    aggregate: str | None = None,
    sql: str | None = None,
    limit: int = 100,
    filters: dict[str, Any] | None = None,
) -> str:
    """Query infrastructure telemetry and return results as a JSON string.

    The Azure AI Agent Service will call this function with keyword arguments
    extracted from the user's request.

    Args:
        table:     One of ``telemetry_gpu``, ``telemetry_net``, ``telemetry_cost``,
                   ``incidents``.  Returns the *limit* most-recent rows.
        aggregate: Named aggregate query key (see ``list_aggregates`` output).
        sql:       Raw SELECT statement (restricted to known tables, SELECT only).
        limit:     Maximum rows returned for plain table queries (default 100, max 500).
        filters:   Optional key/value filters applied as WHERE clauses for plain
                   table queries (e.g. ``{"host": "gpu-node-01"}``).

    Returns:
        JSON string with keys ``columns``, ``rows``, ``row_count``, and ``meta``.
    """
    db_mode = os.environ.get("DB_MODE", "sqlite").lower()

    try:
        result = await _dispatch(
            db_mode=db_mode,
            table=table,
            aggregate=aggregate,
            sql=sql,
            limit=min(int(limit), 500),
            filters=filters or {},
        )
        result["meta"] = {
            "db_mode": db_mode,
            "disclaimer": "All data is synthetic — for demo purposes only.",
        }
        return json.dumps(result, default=str)
    except Exception as exc:  # noqa: BLE001
        logger.exception("query_telemetry failed")
        error_payload = {
            "error": str(exc),
            "meta": {
                "db_mode": db_mode,
                "disclaimer": "All data is synthetic — for demo purposes only.",
            },
        }
        return json.dumps(error_payload)


async def _dispatch(
    *,
    db_mode: str,
    table: str | None,
    aggregate: str | None,
    sql: str | None,
    limit: int,
    filters: dict[str, Any],
) -> dict[str, Any]:
    """Build the SQL string and dispatch to the correct backend."""

    # --- 1. Named aggregate ---
    if aggregate is not None:
        agg_key = aggregate.strip().lower()
        if agg_key not in _AGG_QUERIES:
            available = sorted(_AGG_QUERIES.keys())
            raise ValueError(f"Unknown aggregate '{agg_key}'. Available: {available}")
        final_sql = _AGG_QUERIES[agg_key]
        params: tuple[Any, ...] = ()

    # --- 2. Raw SQL ---
    elif sql is not None:
        _validate_sql(sql)
        final_sql = sql.strip()
        params = ()

    # --- 3. Plain table scan with optional filters ---
    elif table is not None:
        if table not in TELEMETRY_TABLES:
            raise ValueError(
                f"Unknown table '{table}'. Must be one of: {sorted(TELEMETRY_TABLES.keys())}"
            )
        where_clauses: list[str] = []
        param_values: list[Any] = []
        for col, val in filters.items():
            # Only allow column names that look safe (alphanumeric + underscore)
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col):
                raise ValueError(f"Invalid filter column name: '{col}'")
            where_clauses.append(f"{col} = ?")
            param_values.append(val)

        ts_col = "ts"
        order_dir = "DESC"
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        final_sql = f"SELECT * FROM {table} {where_sql} ORDER BY {ts_col} {order_dir} LIMIT ?"
        param_values.append(limit)
        params = tuple(param_values)

    else:
        raise ValueError("Provide at least one of: 'table', 'aggregate', or 'sql'.")

    # --- Dispatch to backend ---
    if db_mode == "sqlite":
        return await _run_sqlite(final_sql, params)
    elif db_mode == "azure_sql":
        # pyodbc is synchronous; wrap in executor in a real async context
        import asyncio  # noqa: PLC0415

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _run_azure_sql, final_sql, params)
    else:
        raise ValueError(f"Unsupported DB_MODE '{db_mode}'. Use 'sqlite' or 'azure_sql'.")


# ---------------------------------------------------------------------------
# Azure AI Agent Service tool schema
# ---------------------------------------------------------------------------

TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "query_telemetry",
        "description": (
            "Query synthetic infrastructure telemetry data stored in SQL. "
            "Covers GPU utilization, network throughput/latency, cost, and incidents. "
            "All data is synthetic and for demo purposes only. "
            "IMPORTANT: The ONLY valid tables are: telemetry_gpu, telemetry_net, "
            "telemetry_cost, incidents. Do NOT use any other table names."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": (
                        "Return raw rows from one of the telemetry tables. "
                        + " | ".join(
                            f"'{name}' ({', '.join(meta['columns'])})"
                            for name, meta in TELEMETRY_TABLES.items()
                        )
                    ),
                    "enum": list(TELEMETRY_TABLES.keys()),
                },
                "aggregate": {
                    "type": "string",
                    "description": (
                        "Run a pre-built aggregate query. Available keys: "
                        + ", ".join(
                            f"'{k}'" for k in sorted(_AGG_QUERIES.keys())
                        )
                        + ". gpu_avg_util_1h/24h: avg/max/min GPU util by cluster+node. "
                        "net_avg_latency_1h: avg/max latency + loss by site. "
                        "cost_by_service_24h: total cost/token cost by cluster. "
                        "open_incidents: unresolved incidents by severity. "
                        "recent_incidents_24h: all incidents in last 24 h. "
                        "Use 'list_aggregates' pseudo-value to see full SQL."
                    ),
                },
                "sql": {
                    "type": "string",
                    "description": (
                        "A raw SELECT statement scoped to the known telemetry tables. "
                        "Only SELECT is permitted; no DDL or DML. "
                        "CRITICAL — SQLite ONLY: Use datetime('now', '-24 hours') for time filters. "
                        "Do NOT use PostgreSQL syntax like NOW(), INTERVAL, or CURRENT_TIMESTAMP. "
                        "Example: SELECT * FROM telemetry_gpu WHERE ts >= datetime('now', '-24 hours')"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of rows to return for plain table queries (default 100, max 500).",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 500,
                },
                "filters": {
                    "type": "object",
                    "description": (
                        "Optional key/value pairs applied as equality WHERE filters for plain table queries. "
                        "Example: {\"host\": \"gpu-node-01\", \"severity\": \"P1\"}"
                    ),
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": [],
            "additionalProperties": False,
        },
    },
}


def get_tool_definition() -> dict[str, Any]:
    """Return the Azure AI Agent Service-compatible tool definition for this tool."""
    return TOOL_SCHEMA


# ---------------------------------------------------------------------------
# Utility: list available aggregate queries
# ---------------------------------------------------------------------------


def list_aggregates() -> dict[str, str]:
    """Return a mapping of aggregate query keys to their SQL for inspection."""
    return dict(_AGG_QUERIES)


# ---------------------------------------------------------------------------
# Sync convenience wrappers for run_local.py demo and agent modes
# ---------------------------------------------------------------------------

import asyncio as _asyncio  # noqa: E402


def _sync_query(*, aggregate: str | None = None, **kwargs: Any) -> dict[str, Any]:
    """Run query_telemetry synchronously and return a parsed dict."""
    result_str = _asyncio.run(query_telemetry(aggregate=aggregate, **kwargs))
    return json.loads(result_str)


def query_gpu_utilization(hours_back: int = 24) -> dict[str, Any]:
    """Sync wrapper: GPU utilization summary."""
    agg = "gpu_avg_util_1h" if hours_back < 24 else "gpu_avg_util_24h"
    return _sync_query(aggregate=agg)


def query_network_telemetry(hours_back: int = 24) -> dict[str, Any]:
    """Sync wrapper: network latency summary."""
    return _sync_query(aggregate="net_avg_latency_1h")


def query_cost_trends(days_back: int = 7) -> dict[str, Any]:
    """Sync wrapper: cost trends by cluster."""
    return _sync_query(aggregate="cost_by_service_24h")


def query_incidents(status: str = "open") -> dict[str, Any]:
    """Sync wrapper: incident list."""
    agg = "open_incidents" if status == "open" else "recent_incidents_24h"
    return _sync_query(aggregate=agg)


def _sync_query_telemetry(**kwargs: Any) -> dict[str, Any]:
    """Sync wrapper for the main query_telemetry function (used by agent mode)."""
    result_str = _asyncio.run(query_telemetry(**kwargs))
    return json.loads(result_str)


TOOL_CALLABLES: dict[str, Any] = {
    "query_telemetry": _sync_query_telemetry,
    "query_gpu_utilization": query_gpu_utilization,
    "query_network_telemetry": query_network_telemetry,
    "query_cost_trends": query_cost_trends,
    "query_incidents": query_incidents,
}

TOOL_DEFINITIONS: list[dict[str, Any]] = [TOOL_SCHEMA]
