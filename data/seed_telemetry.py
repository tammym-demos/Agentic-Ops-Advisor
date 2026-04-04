"""Seed script — creates and populates the local SQLite telemetry database.

All data is **synthetic**. Run directly:

    python data/seed_telemetry.py [--db-path data/telemetry.db]
"""

from __future__ import annotations

import argparse
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

DDL = """
CREATE TABLE IF NOT EXISTS telemetry_gpu (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,           -- ISO-8601 UTC
    host        TEXT    NOT NULL,
    gpu_index   INTEGER NOT NULL DEFAULT 0,
    util_pct    REAL    NOT NULL,           -- 0-100
    mem_used_gb REAL    NOT NULL,
    mem_total_gb REAL   NOT NULL,
    temp_c      REAL    NOT NULL,
    power_w     REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_net (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    host        TEXT    NOT NULL,
    iface       TEXT    NOT NULL DEFAULT 'eth0',
    rx_mbps     REAL    NOT NULL,
    tx_mbps     REAL    NOT NULL,
    drop_pct    REAL    NOT NULL DEFAULT 0.0,
    latency_ms  REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS telemetry_cost (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT    NOT NULL,
    service     TEXT    NOT NULL,
    region      TEXT    NOT NULL DEFAULT 'eastus2',
    usd_per_hr  REAL    NOT NULL,
    units       REAL    NOT NULL DEFAULT 1.0,
    total_usd   REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL,
    resolved_at TEXT,
    severity    TEXT    NOT NULL CHECK(severity IN ('P1','P2','P3','P4')),
    title       TEXT    NOT NULL,
    host        TEXT,
    service     TEXT,
    status      TEXT    NOT NULL DEFAULT 'open' CHECK(status IN ('open','resolved','investigating'))
);
"""

# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

HOSTS = ["gpu-node-01", "gpu-node-02", "gpu-node-03", "cpu-node-01"]
SERVICES = ["training-job", "inference-api", "data-pipeline", "monitoring"]
REGIONS = ["eastus2", "westus2", "northeurope"]

_RNG = random.Random(42)  # deterministic seed


def _ts(offset_minutes: int = 0) -> str:
    """Return an ISO-8601 UTC timestamp offset by *offset_minutes* from now."""
    t = datetime.now(tz=timezone.utc) - timedelta(minutes=offset_minutes)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _seed_gpu(conn: sqlite3.Connection, rows: int = 500) -> None:
    data = []
    for i in range(rows):
        host = _RNG.choice(HOSTS[:3])  # GPU hosts only
        data.append(
            (
                _ts(rows - i),
                host,
                _RNG.randint(0, 3),
                round(_RNG.uniform(30, 100), 1),
                round(_RNG.uniform(10, 79), 1),
                80.0,
                round(_RNG.uniform(40, 90), 1),
                round(_RNG.uniform(150, 400), 0),
            )
        )
    conn.executemany(
        "INSERT INTO telemetry_gpu (ts, host, gpu_index, util_pct, mem_used_gb, mem_total_gb, temp_c, power_w) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        data,
    )


def _seed_net(conn: sqlite3.Connection, rows: int = 300) -> None:
    data = []
    for i in range(rows):
        host = _RNG.choice(HOSTS)
        data.append(
            (
                _ts(rows - i),
                host,
                _RNG.choice(["eth0", "eth1"]),
                round(_RNG.uniform(100, 10000), 1),
                round(_RNG.uniform(50, 5000), 1),
                round(_RNG.uniform(0, 2), 3),
                round(_RNG.uniform(0.5, 50), 2),
            )
        )
    conn.executemany(
        "INSERT INTO telemetry_net (ts, host, iface, rx_mbps, tx_mbps, drop_pct, latency_ms) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        data,
    )


def _seed_cost(conn: sqlite3.Connection, rows: int = 200) -> None:
    data = []
    for i in range(rows):
        svc = _RNG.choice(SERVICES)
        region = _RNG.choice(REGIONS)
        rate = round(_RNG.uniform(0.5, 12.0), 4)
        units = round(_RNG.uniform(1, 8), 1)
        data.append(
            (
                _ts((rows - i) * 60),  # hourly samples spread over ~200 hours
                svc,
                region,
                rate,
                units,
                round(rate * units, 4),
            )
        )
    conn.executemany(
        "INSERT INTO telemetry_cost (ts, service, region, usd_per_hr, units, total_usd) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        data,
    )


def _seed_incidents(conn: sqlite3.Connection) -> None:
    incidents = [
        ("P1", "GPU OOM on gpu-node-02 — training job crashed", "gpu-node-02", "training-job", "resolved", 180, 60),
        ("P2", "High network drop rate on cpu-node-01", "cpu-node-01", "data-pipeline", "resolved", 300, 120),
        ("P2", "Inference API latency spike (p99 > 5 s)", None, "inference-api", "resolved", 500, 90),
        ("P3", "Cost anomaly: training-job spend +40 % vs baseline", None, "training-job", "investigating", 120, None),
        ("P1", "GPU thermal throttle on gpu-node-01 (temp > 88 °C)", "gpu-node-01", "training-job", "open", 30, None),
        ("P4", "Monitoring agent missed heartbeat for 10 min", None, "monitoring", "resolved", 1440, 5),
    ]
    for sev, title, host, svc, status, created_ago_min, resolved_ago_min in incidents:
        created = _ts(created_ago_min)
        resolved = _ts(resolved_ago_min) if resolved_ago_min is not None else None
        conn.execute(
            "INSERT INTO incidents (created_at, resolved_at, severity, title, host, service, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (created, resolved, sev, title, host, svc, status),
        )


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------


def seed(db_path: str | Path = "data/telemetry.db", *, drop_existing: bool = False) -> None:
    """Create and populate the SQLite telemetry database.

    Args:
        db_path: Path to the SQLite file to create/overwrite.
        drop_existing: When *True*, drop existing tables before re-seeding.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        if drop_existing:
            for tbl in ("telemetry_gpu", "telemetry_net", "telemetry_cost", "incidents"):
                conn.execute(f"DROP TABLE IF EXISTS {tbl}")

        conn.executescript(DDL)
        _seed_gpu(conn)
        _seed_net(conn)
        _seed_cost(conn)
        _seed_incidents(conn)
        conn.commit()
        print(f"[seed_telemetry] Database seeded at {db_path.resolve()}")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the synthetic telemetry SQLite database.")
    parser.add_argument("--db-path", default="data/telemetry.db", help="Path to the SQLite file")
    parser.add_argument("--drop", action="store_true", help="Drop existing tables before seeding")
    args = parser.parse_args()
    seed(db_path=args.db_path, drop_existing=args.drop)
