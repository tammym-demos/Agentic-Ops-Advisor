"""SQL Telemetry Tool — queries synthetic infrastructure telemetry from SQLite (local) or Azure SQL."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone

import aiosqlite

# ---------------------------------------------------------------------------
# Schema + seed data helpers
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS telemetry_gpu (
    ts             TEXT NOT NULL,
    cluster        TEXT NOT NULL,
    node           TEXT NOT NULL,
    utilization_pct REAL NOT NULL,
    mem_pct        REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_net (
    ts              TEXT NOT NULL,
    site            TEXT NOT NULL,
    latency_ms      REAL NOT NULL,
    loss_pct        REAL NOT NULL,
    throughput_gbps REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_cost (
    ts             TEXT NOT NULL,
    cluster        TEXT NOT NULL,
    cost_usd       REAL NOT NULL,
    token_cost_usd REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    ts       TEXT NOT NULL,
    service  TEXT NOT NULL,
    symptom  TEXT NOT NULL,
    severity TEXT NOT NULL,
    status   TEXT NOT NULL
);
"""


def _seed_db(conn: sqlite3.Connection, days: int = 30) -> None:
    """Populate tables with synthetic data including planted anomalies."""
    import random

    random.seed(42)
    now = datetime.now(tz=timezone.utc)
    clusters = ["gpu-cluster-a", "gpu-cluster-b"]
    nodes = ["node-01", "node-02", "node-03"]
    sites = ["eastus2", "westus3"]

    gpu_rows = []
    net_rows = []
    cost_rows = []

    for h in range(days * 24):
        ts = (now - timedelta(hours=h)).isoformat()
        for cluster in clusters:
            for node in nodes:
                util = random.uniform(60, 85)
                mem = random.uniform(50, 75)
                # Plant a GPU utilization drop anomaly around 25h ago
                if 24 <= h <= 26 and cluster == "gpu-cluster-a":
                    util = random.uniform(10, 20)
                gpu_rows.append((ts, cluster, node, round(util, 2), round(mem, 2)))

        for site in sites:
            lat = random.uniform(5, 15)
            loss = random.uniform(0, 0.5)
            tput = random.uniform(8, 12)
            # Plant a latency spike anomaly around 48h ago
            if 47 <= h <= 49 and site == "eastus2":
                lat = random.uniform(200, 350)
                loss = random.uniform(5, 10)
            net_rows.append((ts, site, round(lat, 2), round(loss, 3), round(tput, 2)))

        for cluster in clusters:
            cost = random.uniform(80, 120)
            token_cost = random.uniform(10, 30)
            cost_rows.append((ts, cluster, round(cost, 2), round(token_cost, 2)))

    conn.executemany(
        "INSERT INTO telemetry_gpu VALUES (?,?,?,?,?)",
        gpu_rows,
    )
    conn.executemany(
        "INSERT INTO telemetry_net VALUES (?,?,?,?,?)",
        net_rows,
    )
    conn.executemany(
        "INSERT INTO telemetry_cost VALUES (?,?,?,?)",
        cost_rows,
    )

    # Seed incidents table
    incident_rows = [
        (
            (now - timedelta(hours=25)).isoformat(),
            "gpu-cluster-a",
            "GPU utilization dropped below 20%",
            "high",
            "open",
        ),
        (
            (now - timedelta(hours=48)).isoformat(),
            "network",
            "Latency spike >200ms in eastus2",
            "medium",
            "resolved",
        ),
        (
            (now - timedelta(hours=72)).isoformat(),
            "cost-tracker",
            "Token cost exceeded budget threshold",
            "low",
            "resolved",
        ),
    ]
    conn.executemany(
        "INSERT INTO incidents VALUES (?,?,?,?,?)",
        incident_rows,
    )
    conn.commit()


def init_db_sync(db_path: str = ":memory:") -> sqlite3.Connection:
    """Create and seed a SQLite database synchronously. Returns open connection."""
    conn = sqlite3.connect(db_path)
    conn.executescript(_DDL)
    _seed_db(conn)
    return conn


async def init_db(db_path: str = ":memory:") -> None:
    """Create and seed a SQLite database asynchronously (file-based path)."""
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(_DDL)
        await db.commit()

    # Use sync seeding for simplicity (seed is one-time setup)
    conn = sqlite3.connect(db_path)
    _seed_db(conn)
    conn.close()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

_DEFAULT_DB = os.environ.get("SQLITE_DB_PATH", "agentops.db")

_QUERIES: dict[str, str] = {
    "gpu": """
        SELECT cluster, node,
               AVG(utilization_pct) AS avg_util,
               MIN(utilization_pct) AS min_util,
               MAX(utilization_pct) AS max_util,
               COUNT(*) AS samples
        FROM telemetry_gpu
        WHERE ts >= datetime('now', '-{hours} hours')
        GROUP BY cluster, node
        ORDER BY avg_util ASC
    """,
    "network": """
        SELECT site,
               AVG(latency_ms) AS avg_latency,
               MAX(latency_ms) AS max_latency,
               AVG(loss_pct)   AS avg_loss,
               AVG(throughput_gbps) AS avg_tput,
               COUNT(*) AS samples
        FROM telemetry_net
        WHERE ts >= datetime('now', '-{hours} hours')
        GROUP BY site
        ORDER BY avg_latency DESC
    """,
    "cost": """
        SELECT cluster,
               SUM(cost_usd)       AS total_cost,
               SUM(token_cost_usd) AS total_token_cost,
               COUNT(*) AS samples
        FROM telemetry_cost
        WHERE ts >= datetime('now', '-{hours} hours')
        GROUP BY cluster
        ORDER BY total_cost DESC
    """,
    "incidents": """
        SELECT ts, service, symptom, severity, status
        FROM incidents
        WHERE ts >= datetime('now', '-{hours} hours')
        ORDER BY ts DESC
    """,
    "summary": """
        SELECT 'gpu' AS metric_type,
               COUNT(*) AS total_samples,
               AVG(utilization_pct) AS avg_value
        FROM telemetry_gpu
        WHERE ts >= datetime('now', '-{hours} hours')
        UNION ALL
        SELECT 'network', COUNT(*), AVG(latency_ms)
        FROM telemetry_net
        WHERE ts >= datetime('now', '-{hours} hours')
        UNION ALL
        SELECT 'cost', COUNT(*), AVG(cost_usd)
        FROM telemetry_cost
        WHERE ts >= datetime('now', '-{hours} hours')
    """,
}


async def query_telemetry(
    query_type: str,
    hours_back: int = 24,
    db_path: str | None = None,
) -> str:
    """Query telemetry data from SQLite and return JSON string.

    Args:
        query_type: One of "gpu", "network", "cost", "incidents", "summary".
        hours_back: How many hours of history to include. Defaults to 24.
        db_path: Path to SQLite database. Defaults to SQLITE_DB_PATH env var or "agentops.db".

    Returns:
        JSON-encoded list of result rows.
    """
    if query_type not in _QUERIES:
        return json.dumps(
            {"error": f"Unknown query_type '{query_type}'. Choose from: {list(_QUERIES)}"}
        )

    effective_path = db_path or _DEFAULT_DB
    sql = _QUERIES[query_type].format(hours=hours_back)

    try:
        async with aiosqlite.connect(effective_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sql) as cursor:
                rows = await cursor.fetchall()
                return json.dumps([dict(row) for row in rows])
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Sync wrapper for FunctionTool (Azure AI Agent Service dispatches sync)
# ---------------------------------------------------------------------------

def query_telemetry_sync(query_type: str, hours_back: int = 24) -> str:
    """Synchronous wrapper around query_telemetry for FunctionTool registration."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(query_telemetry(query_type, hours_back))
    finally:
        loop.close()
