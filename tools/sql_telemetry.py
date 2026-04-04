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
        "description": "GPU utilization, memory, temperature and power per host/GPU index.",
        "columns": ["id", "ts", "host", "gpu_index", "util_pct", "mem_used_gb", "mem_total_gb", "temp_c", "power_w"],
    },
    "telemetry_net": {
        "description": "Network throughput, packet-drop rate and latency per host/interface.",
        "columns": ["id", "ts", "host", "iface", "rx_mbps", "tx_mbps", "drop_pct", "latency_ms"],
    },
    "telemetry_cost": {
        "description": "Hourly cost samples per service and region.",
        "columns": ["id", "ts", "service", "region", "usd_per_hr", "units", "total_usd"],
    },
    "incidents": {
        "description": "Infrastructure incident log with severity, status and linked host/service.",
        "columns": ["id", "created_at", "resolved_at", "severity", "title", "host", "service", "status"],
    },
}

# Pre-built aggregate query templates ----------------------------------------
# Each template uses named :param style so they are safe against injection.

_AGG_QUERIES: dict[str, str] = {
    "gpu_avg_util_1h": (
        "SELECT host, AVG(util_pct) AS avg_util_pct, MAX(util_pct) AS max_util_pct, "
        "MIN(util_pct) AS min_util_pct "
        "FROM telemetry_gpu "
        "WHERE ts >= datetime('now', '-1 hour') "
        "GROUP BY host ORDER BY avg_util_pct DESC"
    ),
    "gpu_avg_util_24h": (
        "SELECT host, AVG(util_pct) AS avg_util_pct, MAX(util_pct) AS max_util_pct, "
        "MIN(util_pct) AS min_util_pct "
        "FROM telemetry_gpu "
        "WHERE ts >= datetime('now', '-24 hours') "
        "GROUP BY host ORDER BY avg_util_pct DESC"
    ),
    "net_avg_latency_1h": (
        "SELECT host, iface, AVG(latency_ms) AS avg_latency_ms, MAX(latency_ms) AS max_latency_ms, "
        "AVG(drop_pct) AS avg_drop_pct "
        "FROM telemetry_net "
        "WHERE ts >= datetime('now', '-1 hour') "
        "GROUP BY host, iface ORDER BY avg_latency_ms DESC"
    ),
    "cost_by_service_24h": (
        "SELECT service, region, SUM(total_usd) AS total_usd, AVG(usd_per_hr) AS avg_usd_per_hr "
        "FROM telemetry_cost "
        "WHERE ts >= datetime('now', '-24 hours') "
        "GROUP BY service, region ORDER BY total_usd DESC"
    ),
    "open_incidents": (
        "SELECT id, created_at, severity, title, host, service, status "
        "FROM incidents "
        "WHERE status != 'resolved' "
        "ORDER BY CASE severity WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, created_at DESC"
    ),
    "recent_incidents_24h": (
        "SELECT id, created_at, resolved_at, severity, title, host, service, status "
        "FROM incidents "
        "WHERE created_at >= datetime('now', '-24 hours') "
        "ORDER BY created_at DESC"
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

        ts_col = "created_at" if table == "incidents" else "ts"
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
            "All data is synthetic and for demo purposes only."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": (
                        "Return raw rows from one of the telemetry tables: "
                        "'telemetry_gpu', 'telemetry_net', 'telemetry_cost', 'incidents'."
                    ),
                    "enum": list(TELEMETRY_TABLES.keys()),
                },
                "aggregate": {
                    "type": "string",
                    "description": (
                        "Run a pre-built aggregate query. Available keys: "
                        + ", ".join(sorted(_AGG_QUERIES.keys()))
                        + ". Use 'list_aggregates' pseudo-value to see descriptions."
                    ),
                },
                "sql": {
                    "type": "string",
                    "description": (
                        "A raw SELECT statement scoped to the known telemetry tables. "
                        "Only SELECT is permitted; no DDL or DML."
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
