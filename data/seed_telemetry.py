"""Synthetic telemetry data generator for Agentic Ops Advisor.

Generates 30 days of synthetic infrastructure telemetry data with planted anomalies.
Outputs to both SQLite (data/telemetry.db) and SQL INSERT statements (data/seed_data.sql).

Anomalies planted:
  - Day 18: GPU utilization drop  — cluster-a / node-1 collapses to <15 %
  - Day 22: Network latency spike — site-west latency exceeds 180 ms, packet loss spikes
  - Day 25: Cost surge            — cluster-a spend jumps 5-7x baseline
  - Day 18: Incident correlated with GPU drop (P1, resolved)

All data is synthetic. Do not use for production decisions.
"""

import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RANDOM_SEED = 42

# Dynamic base date so generated data ends near "now" (queries using datetime('now', ...) will return results)
# BASE_DATE = start of data generation, set so that last day ends ~today
DAYS = 30
BASE_DATE = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=DAYS - 1)

CLUSTERS = ["cluster-a", "cluster-b", "cluster-c"]
NODES_PER_CLUSTER = ["node-1", "node-2", "node-3", "node-4"]
SITES = ["site-east", "site-west", "site-central"]

# Anomaly trigger days (0-indexed from BASE_DATE)
GPU_DROP_DAY = 18
LATENCY_SPIKE_DAY = 22
COST_SURGE_DAY = 25

DATA_DIR = Path(__file__).parent
DB_PATH = DATA_DIR / "telemetry.db"
SQL_PATH = DATA_DIR / "seed_data.sql"

# Compat alias used by scripts/setup_local_db.py
DEFAULT_DB_PATH = str(DB_PATH)

# ---------------------------------------------------------------------------
# DDL
# ---------------------------------------------------------------------------

DDL = """\
CREATE TABLE IF NOT EXISTS telemetry_gpu (
    ts              TEXT NOT NULL,
    cluster         TEXT NOT NULL,
    node            TEXT NOT NULL,
    utilization_pct REAL NOT NULL,
    mem_pct         REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_net (
    ts              TEXT NOT NULL,
    site            TEXT NOT NULL,
    latency_ms      REAL NOT NULL,
    loss_pct        REAL NOT NULL,
    throughput_gbps REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_cost (
    ts              TEXT NOT NULL,
    cluster         TEXT NOT NULL,
    cost_usd        REAL NOT NULL,
    token_cost_usd  REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    ts       TEXT NOT NULL,
    service  TEXT NOT NULL,
    symptom  TEXT NOT NULL,
    severity TEXT NOT NULL,
    status   TEXT NOT NULL
);"""


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all telemetry tables (idempotent). Used by setup scripts."""
    conn.executescript(DDL)
    conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _randf(rng: random.Random, lo: float, hi: float) -> float:
    """Return a float rounded to 2 decimal places in [lo, hi]."""
    return round(rng.uniform(lo, hi), 2)


def _ts(day: int, hour: int = 0) -> str:
    return (BASE_DATE + timedelta(days=day, hours=hour)).isoformat()


# ---------------------------------------------------------------------------
# Row generators
# ---------------------------------------------------------------------------


def generate_gpu_rows(rng: random.Random) -> list[tuple]:
    """Hourly GPU metrics for every cluster/node pair over DAYS days.

    Anomaly: day GPU_DROP_DAY — cluster-a / node-1 drops to 5-15 % utilization.
    """
    rows = []
    for day in range(DAYS):
        for hour in range(24):
            ts = _ts(day, hour)
            for cluster in CLUSTERS:
                for node in NODES_PER_CLUSTER:
                    # Normal operating range
                    util = _randf(rng, 55.0, 90.0)
                    mem = _randf(rng, 40.0, 85.0)

                    # Plant anomaly: GPU utilization collapse
                    if day == GPU_DROP_DAY and cluster == "cluster-a" and node == "node-1":
                        util = _randf(rng, 5.0, 15.0)
                        mem = _randf(rng, 8.0, 22.0)

                    rows.append((ts, cluster, node, util, mem))
    return rows


def generate_net_rows(rng: random.Random) -> list[tuple]:
    """Hourly network metrics for every site over DAYS days.

    Anomaly: day LATENCY_SPIKE_DAY — site-west latency spikes to 180-320 ms
    with elevated packet loss and reduced throughput.
    """
    rows = []
    for day in range(DAYS):
        for hour in range(24):
            ts = _ts(day, hour)
            for site in SITES:
                # Normal operating range
                latency = _randf(rng, 5.0, 25.0)
                loss = _randf(rng, 0.0, 0.5)
                throughput = _randf(rng, 8.0, 10.0)

                # Plant anomaly: network latency spike
                if day == LATENCY_SPIKE_DAY and site == "site-west":
                    latency = _randf(rng, 180.0, 320.0)
                    loss = _randf(rng, 5.0, 15.0)
                    throughput = _randf(rng, 0.5, 2.0)

                rows.append((ts, site, latency, loss, throughput))
    return rows


def generate_cost_rows(rng: random.Random) -> list[tuple]:
    """Hourly cost metrics for every cluster over DAYS days.

    Anomaly: day COST_SURGE_DAY — cluster-a cost jumps 5-7x baseline.
    """
    rows = []
    for day in range(DAYS):
        for hour in range(24):
            ts = _ts(day, hour)
            for cluster in CLUSTERS:
                # Normal operating range
                cost = _randf(rng, 10.0, 30.0)
                token_cost = _randf(rng, 2.0, 8.0)

                # Plant anomaly: cost surge
                if day == COST_SURGE_DAY and cluster == "cluster-a":
                    cost = _randf(rng, 120.0, 200.0)
                    token_cost = _randf(rng, 40.0, 80.0)

                rows.append((ts, cluster, cost, token_cost))
    return rows


def generate_incident_rows() -> list[tuple]:
    """A small set of incidents, including three correlated with the planted anomalies."""
    rows = [
        # --- Correlated with GPU drop (day 18) ---
        (
            _ts(GPU_DROP_DAY, hour=2),
            "ml-training-service",
            "GPU utilization collapsed to <15% on cluster-a/node-1",
            "P1",
            "resolved",
        ),
        # --- Correlated with network latency spike (day 22) ---
        (
            _ts(LATENCY_SPIKE_DAY, hour=14),
            "api-gateway",
            "High latency detected on site-west (p99 > 250 ms)",
            "P2",
            "resolved",
        ),
        # --- Correlated with cost surge (day 25) ---
        (
            _ts(COST_SURGE_DAY, hour=8),
            "cost-monitor",
            "Unexpected cost surge: cluster-a spend 5x above baseline",
            "P2",
            "open",
        ),
        # --- Background incidents for realism ---
        (
            _ts(5, hour=9),
            "storage-service",
            "Disk I/O throttling on node-3 exceeding 90%",
            "P3",
            "resolved",
        ),
        (
            _ts(11, hour=16),
            "scheduler",
            "Job queue depth exceeded 500 for 30+ minutes",
            "P3",
            "resolved",
        ),
        (
            _ts(28, hour=3),
            "auth-service",
            "Elevated 5xx error rate (>2%) on auth endpoints",
            "P2",
            "investigating",
        ),
    ]
    return rows


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def write_sqlite(
    gpu_rows: list[tuple],
    net_rows: list[tuple],
    cost_rows: list[tuple],
    incident_rows: list[tuple],
    db_path: Path = DB_PATH,
) -> None:
    """Write all rows to a SQLite database, replacing any existing file."""
    if db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.executescript(DDL)
        cur.executemany("INSERT INTO telemetry_gpu VALUES (?,?,?,?,?)", gpu_rows)
        cur.executemany("INSERT INTO telemetry_net VALUES (?,?,?,?,?)", net_rows)
        cur.executemany("INSERT INTO telemetry_cost VALUES (?,?,?,?)", cost_rows)
        cur.executemany("INSERT INTO incidents VALUES (?,?,?,?,?)", incident_rows)
        conn.commit()
    finally:
        conn.close()

    print(f"  SQLite written → {db_path}")


def _sql_literal(value: object) -> str:
    """Render a Python value as a SQL literal (single-quote escaped strings)."""
    if isinstance(value, str):
        escaped = value.replace("'", "''")
        return f"'{escaped}'"
    return str(value)


def write_sql(
    gpu_rows: list[tuple],
    net_rows: list[tuple],
    cost_rows: list[tuple],
    incident_rows: list[tuple],
    sql_path: Path = SQL_PATH,
) -> None:
    """Write all rows to a plain SQL file with INSERT statements."""

    def inserts(table: str, rows: list[tuple]) -> list[str]:
        return [
            f"INSERT INTO {table} VALUES ({', '.join(_sql_literal(v) for v in row)});"
            for row in rows
        ]

    sections = [
        "-- Synthetic telemetry seed data for Agentic Ops Advisor",
        "-- Generated by data/seed_telemetry.py  (do not hand-edit)",
        "-- All data is synthetic. Do not use for production decisions.",
        "",
        DDL,
        "",
        *inserts("telemetry_gpu", gpu_rows),
        "",
        *inserts("telemetry_net", net_rows),
        "",
        *inserts("telemetry_cost", cost_rows),
        "",
        *inserts("incidents", incident_rows),
        "",
    ]

    sql_path.write_text("\n".join(sections), encoding="utf-8")
    print(f"  SQL written    → {sql_path}")


# ---------------------------------------------------------------------------
# Connection-based seeding (used by setup scripts)
# ---------------------------------------------------------------------------


def seed_connection(
    conn: sqlite3.Connection,
    days: int = DAYS,
    random_seed: int = RANDOM_SEED,
) -> dict[str, int]:
    """Seed synthetic data into an open connection. Returns {table_name: row_count}.

    Used by scripts/setup_local_db.py which manages
    its own connection lifecycle.
    """
    rng = random.Random(random_seed)
    gpu_rows = generate_gpu_rows(rng)
    net_rows = generate_net_rows(rng)
    cost_rows = generate_cost_rows(rng)
    incident_rows = generate_incident_rows()

    cur = conn.cursor()
    cur.executemany("INSERT INTO telemetry_gpu VALUES (?,?,?,?,?)", gpu_rows)
    cur.executemany("INSERT INTO telemetry_net VALUES (?,?,?,?,?)", net_rows)
    cur.executemany("INSERT INTO telemetry_cost VALUES (?,?,?,?)", cost_rows)
    cur.executemany("INSERT INTO incidents VALUES (?,?,?,?,?)", incident_rows)
    conn.commit()

    return {
        "telemetry_gpu": len(gpu_rows),
        "telemetry_net": len(net_rows),
        "telemetry_cost": len(cost_rows),
        "incidents": len(incident_rows),
    }


# ---------------------------------------------------------------------------
# File-based seeding (standalone CLI usage)
# ---------------------------------------------------------------------------


def seed(
    db_path: Path = DB_PATH,
    sql_path: Path = SQL_PATH,
    random_seed: int = RANDOM_SEED,
) -> dict[str, list[tuple]]:
    """Generate all synthetic rows, write outputs, and return a dict of row lists.

    Returns:
        dict with keys "gpu", "net", "cost", "incidents".
    """
    rng = random.Random(random_seed)

    gpu_rows = generate_gpu_rows(rng)
    net_rows = generate_net_rows(rng)
    cost_rows = generate_cost_rows(rng)
    incident_rows = generate_incident_rows()

    write_sqlite(gpu_rows, net_rows, cost_rows, incident_rows, db_path=db_path)
    write_sql(gpu_rows, net_rows, cost_rows, incident_rows, sql_path=sql_path)

    return {"gpu": gpu_rows, "net": net_rows, "cost": cost_rows, "incidents": incident_rows}


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Generating synthetic telemetry data…")
    rows = seed()
    print(f"  GPU rows:      {len(rows['gpu']):,}")
    print(f"  Net rows:      {len(rows['net']):,}")
    print(f"  Cost rows:     {len(rows['cost']):,}")
    print(f"  Incident rows: {len(rows['incidents'])}")
    print("Done.")
