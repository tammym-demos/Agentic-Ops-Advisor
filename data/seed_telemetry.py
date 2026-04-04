"""Synthetic telemetry data generator for Agentic Ops Advisor (local dev).

All data is synthetic. This script creates and populates the SQLite database
at data/telemetry.db with 30 days of plausible infrastructure telemetry,
including a few planted anomalies that the agent's demo queries are designed
to surface.

Planted anomalies:
  - GPU utilisation drop on gpu-cluster-01 (~24 h ago)
  - Network latency spike on eastus2-primary (~72 h ago, 6 h duration)
  - Change event (network-policy rollout) ~73 h ago – correlates with spike
  - Open incident logged for each anomaly
"""

from __future__ import annotations

import math
import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(_HERE, "telemetry.db")

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------
DDL = """
CREATE TABLE IF NOT EXISTS telemetry_gpu (
    ts              TEXT    NOT NULL,
    cluster         TEXT    NOT NULL,
    node            TEXT    NOT NULL,
    utilization_pct REAL    NOT NULL,
    mem_pct         REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_net (
    ts              TEXT    NOT NULL,
    site            TEXT    NOT NULL,
    latency_ms      REAL    NOT NULL,
    loss_pct        REAL    NOT NULL,
    throughput_gbps REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_cost (
    ts              TEXT    NOT NULL,
    cluster         TEXT    NOT NULL,
    cost_usd        REAL    NOT NULL,
    token_cost_usd  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    ts              TEXT    NOT NULL,
    service         TEXT    NOT NULL,
    symptom         TEXT    NOT NULL,
    severity        TEXT    NOT NULL,
    status          TEXT    NOT NULL
);
"""

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------
CLUSTERS = ["gpu-cluster-01", "gpu-cluster-02"]
NODES = ["node-a", "node-b", "node-c"]
SITES = ["eastus2-primary", "eastus2-dr", "westus2-primary"]

# Normal operating ranges
NORMAL_GPU_UTIL = (62.0, 88.0)
NORMAL_GPU_MEM = (55.0, 82.0)
NORMAL_LATENCY_MS = (2.0, 9.0)
NORMAL_LOSS_PCT = (0.0, 0.3)
NORMAL_THROUGHPUT = (8.0, 12.0)
NORMAL_COST_USD = (1_100.0, 1_800.0)
NORMAL_TOKEN_COST_RATIO = (0.35, 0.55)  # fraction of total cost


def _jitter(value: float, pct: float = 0.08) -> float:
    """Add ±pct random noise to a value (clamped to ≥ 0)."""
    delta = value * pct * (2 * random.random() - 1)
    return max(0.0, value + delta)


def _rand_between(lo: float, hi: float) -> float:
    return lo + random.random() * (hi - lo)


# ---------------------------------------------------------------------------
# Data generators
# ---------------------------------------------------------------------------

def _generate_gpu_rows(now: datetime, days: int = 30) -> list[tuple]:
    """Generate hourly GPU telemetry rows with a planted utilisation drop."""
    rows: list[tuple] = []
    # Anomaly window: drop starts ~26 h ago, lasts until ~22 h ago (4 h window)
    anomaly_start = now - timedelta(hours=26)
    anomaly_end = now - timedelta(hours=22)

    start = now - timedelta(days=days)
    ts = start
    while ts <= now:
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        in_anomaly_window = anomaly_start <= ts <= anomaly_end

        for cluster in CLUSTERS:
            for node in NODES:
                if in_anomaly_window and cluster == "gpu-cluster-01":
                    # Planted anomaly: utilisation plummets (likely underutilised / workload paused)
                    util = _rand_between(10.0, 22.0)
                    mem = _rand_between(48.0, 62.0)
                else:
                    # Add gentle sinusoidal diurnal pattern (higher util during business hours)
                    hour = ts.hour
                    diurnal = 6.0 * math.sin(math.pi * (hour - 6) / 12) if 6 <= hour <= 18 else -4.0
                    util = _jitter(_rand_between(*NORMAL_GPU_UTIL) + diurnal)
                    mem = _jitter(_rand_between(*NORMAL_GPU_MEM))
                rows.append((ts_str, cluster, node, round(util, 2), round(mem, 2)))
        ts += timedelta(hours=1)
    return rows


def _generate_net_rows(now: datetime, days: int = 30) -> list[tuple]:
    """Generate hourly network telemetry rows with a planted latency spike."""
    rows: list[tuple] = []
    # Anomaly window: spike on eastus2-primary ~73 h ago, lasting 6 h
    anomaly_start = now - timedelta(hours=73)
    anomaly_end = now - timedelta(hours=67)

    start = now - timedelta(days=days)
    ts = start
    while ts <= now:
        ts_str = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
        in_anomaly_window = anomaly_start <= ts <= anomaly_end

        for site in SITES:
            if in_anomaly_window and site == "eastus2-primary":
                # Planted anomaly: high latency + packet loss (network policy rollout side-effect)
                latency = _rand_between(145.0, 260.0)
                loss = _rand_between(1.2, 4.8)
                throughput = _rand_between(1.5, 4.0)
            else:
                latency = _jitter(_rand_between(*NORMAL_LATENCY_MS))
                loss = _jitter(_rand_between(*NORMAL_LOSS_PCT))
                throughput = _jitter(_rand_between(*NORMAL_THROUGHPUT))
            rows.append((ts_str, site, round(latency, 3), round(loss, 3), round(throughput, 3)))
        ts += timedelta(hours=1)
    return rows


def _generate_cost_rows(now: datetime, days: int = 30) -> list[tuple]:
    """Generate daily cost rows per cluster."""
    rows: list[tuple] = []
    # Cost spike on the day of the network anomaly (correlated)
    anomaly_day = (now - timedelta(hours=73)).date()

    for day_offset in range(days):
        day = (now - timedelta(days=(days - 1 - day_offset))).date()
        ts_str = day.strftime("%Y-%m-%dT00:00:00Z")
        for cluster in CLUSTERS:
            base = _rand_between(*NORMAL_COST_USD)
            if day == anomaly_day:
                # Spike: retries and redundant traffic inflate cost ~40%
                base *= 1.38
            token_ratio = _rand_between(*NORMAL_TOKEN_COST_RATIO)
            rows.append((ts_str, cluster, round(base, 2), round(base * token_ratio, 2)))
    return rows


def _generate_incidents(now: datetime) -> list[tuple]:
    """Generate a small set of synthetic incidents."""
    return [
        # Open: GPU underutilisation on cluster-01 (planted, ~24 h ago)
        (
            (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gpu-cluster-01",
            "GPU utilisation dropped to <25% across all nodes — potential workload stall or scheduler issue",
            "high",
            "open",
        ),
        # Open: network latency on eastus2-primary (planted, ~72 h ago)
        (
            (now - timedelta(hours=72)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "network/eastus2-primary",
            "Latency spike >150 ms with 2-5% packet loss observed on eastus2-primary after network-policy rollout",
            "critical",
            "open",
        ),
        # Resolved: routine GPU memory pressure (older, resolved)
        (
            (now - timedelta(days=12)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gpu-cluster-02",
            "GPU memory pressure (>90%) on node-c during batch job overflow",
            "medium",
            "resolved",
        ),
        # Resolved: cost overrun (older, resolved)
        (
            (now - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "billing",
            "Token cost exceeded daily budget by 18% due to unthrottled eval runs",
            "low",
            "resolved",
        ),
        # Open: intermittent throughput degradation on westus2 (recent)
        (
            (now - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "network/westus2-primary",
            "Throughput dropped to <5 Gbps on westus2-primary (below SLO of 8 Gbps)",
            "medium",
            "open",
        ),
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_schema(conn: sqlite3.Connection) -> None:
    """Create all telemetry tables (idempotent)."""
    conn.executescript(DDL)
    conn.commit()


def seed(conn: sqlite3.Connection, *, days: int = 30, seed_value: int | None = 42) -> dict[str, int]:
    """Seed synthetic telemetry data.

    Args:
        conn: Open SQLite connection.
        days: How many days of historical data to generate.
        seed_value: Random seed for reproducibility (None for random).

    Returns:
        Dict of {table_name: row_count} for verification.
    """
    if seed_value is not None:
        random.seed(seed_value)

    now = datetime.now(tz=timezone.utc).replace(minute=0, second=0, microsecond=0)

    gpu_rows = _generate_gpu_rows(now, days=days)
    net_rows = _generate_net_rows(now, days=days)
    cost_rows = _generate_cost_rows(now, days=days)
    incident_rows = _generate_incidents(now)

    conn.executemany(
        "INSERT INTO telemetry_gpu (ts, cluster, node, utilization_pct, mem_pct) VALUES (?,?,?,?,?)",
        gpu_rows,
    )
    conn.executemany(
        "INSERT INTO telemetry_net (ts, site, latency_ms, loss_pct, throughput_gbps) VALUES (?,?,?,?,?)",
        net_rows,
    )
    conn.executemany(
        "INSERT INTO telemetry_cost (ts, cluster, cost_usd, token_cost_usd) VALUES (?,?,?,?)",
        cost_rows,
    )
    conn.executemany(
        "INSERT INTO incidents (ts, service, symptom, severity, status) VALUES (?,?,?,?,?)",
        incident_rows,
    )
    conn.commit()

    return {
        "telemetry_gpu": len(gpu_rows),
        "telemetry_net": len(net_rows),
        "telemetry_cost": len(cost_rows),
        "incidents": len(incident_rows),
    }


def seed_db(db_path: str = DEFAULT_DB_PATH, *, days: int = 30) -> dict[str, int]:
    """Create schema and seed the database at *db_path*.

    Returns:
        Dict of {table_name: row_count}.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        create_schema(conn)
        counts = seed(conn, days=days)
    finally:
        conn.close()
    return counts


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Seed synthetic telemetry into the local SQLite database.")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to SQLite database file")
    parser.add_argument("--days", type=int, default=30, help="Number of days of history to generate")
    args = parser.parse_args()

    print(f"Seeding {args.days} days of synthetic telemetry into {args.db} …")
    counts = seed_db(args.db, days=args.days)
    for table, n in counts.items():
        print(f"  {table}: {n:,} rows inserted")
    print("Done.")
