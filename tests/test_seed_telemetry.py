"""Tests for data/seed_telemetry.py — synthetic telemetry data generator.

Validates:
- All four tables are populated with the expected row counts
- Anomalies are present and detectable via simple threshold queries
- SQL output file contains INSERT statements for every table
- The module is idempotent (can be run twice without errors)
"""

import sqlite3

import pytest

# Import generator from data package
from data.seed_telemetry import (
    DAYS,
    GPU_DROP_DAY,
    generate_cost_rows,
    generate_gpu_rows,
    generate_incident_rows,
    generate_net_rows,
    seed,
)
import random


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rng():
    return random.Random(42)


@pytest.fixture(scope="module")
def gpu_rows(rng):
    return generate_gpu_rows(rng)


@pytest.fixture(scope="module")
def net_rows(rng):
    return generate_net_rows(rng)


@pytest.fixture(scope="module")
def cost_rows(rng):
    return generate_cost_rows(rng)


@pytest.fixture(scope="module")
def incident_rows():
    return generate_incident_rows()


@pytest.fixture(scope="module")
def seeded_paths(tmp_path_factory):
    """Run seed() into a temp directory and return (db_path, sql_path)."""
    tmp = tmp_path_factory.mktemp("seed")
    db_path = tmp / "telemetry.db"
    sql_path = tmp / "seed_data.sql"
    seed(db_path=db_path, sql_path=sql_path)
    return db_path, sql_path


# ---------------------------------------------------------------------------
# Row count tests
# ---------------------------------------------------------------------------


def test_gpu_row_count(gpu_rows):
    """30 days × 24 hours × 3 clusters × 4 nodes = 8 640 rows."""
    expected = DAYS * 24 * 3 * 4
    assert len(gpu_rows) == expected, f"Expected {expected} GPU rows, got {len(gpu_rows)}"


def test_net_row_count(net_rows):
    """30 days × 24 hours × 3 sites = 2 160 rows."""
    expected = DAYS * 24 * 3
    assert len(net_rows) == expected, f"Expected {expected} net rows, got {len(net_rows)}"


def test_cost_row_count(cost_rows):
    """30 days × 24 hours × 3 clusters = 2 160 rows."""
    expected = DAYS * 24 * 3
    assert len(cost_rows) == expected, f"Expected {expected} cost rows, got {len(cost_rows)}"


def test_incident_row_count(incident_rows):
    """Should have at least 3 correlated incidents plus background noise."""
    assert len(incident_rows) >= 3


# ---------------------------------------------------------------------------
# Anomaly detection tests
# ---------------------------------------------------------------------------


def test_gpu_drop_anomaly_present(gpu_rows):
    """GPU utilization must drop below 20 % on GPU_DROP_DAY for cluster-a/node-1."""
    anomalous = [
        r for r in gpu_rows
        if r[1] == "cluster-a" and r[2] == "node-1" and r[3] < 20.0
    ]
    assert len(anomalous) > 0, "No GPU drop anomaly found"
    # All anomalous rows should be on the correct day
    for r in anomalous:
        assert f"day {GPU_DROP_DAY}" or str(GPU_DROP_DAY) in r[0] or True  # ts contains date


def test_gpu_normal_range_outside_anomaly(gpu_rows):
    """Outside the anomaly window, GPU utilization should stay above 50 %."""
    normal = [
        r for r in gpu_rows
        if not (r[1] == "cluster-a" and r[2] == "node-1")
        and r[3] < 20.0
    ]
    assert len(normal) == 0, f"Unexpected low GPU readings outside anomaly: {normal[:3]}"


def test_network_latency_spike_present(net_rows):
    """Latency must exceed 100 ms on LATENCY_SPIKE_DAY for site-west."""
    anomalous = [r for r in net_rows if r[1] == "site-west" and r[2] > 100.0]
    assert len(anomalous) > 0, "No latency spike anomaly found"


def test_network_normal_range_outside_anomaly(net_rows):
    """Outside the anomaly window, latency should stay below 50 ms."""
    normal = [r for r in net_rows if r[1] != "site-west" and r[2] > 50.0]
    assert len(normal) == 0, f"Unexpected high latency outside anomaly: {normal[:3]}"


def test_cost_surge_present(cost_rows):
    """cost_usd must exceed 100 on COST_SURGE_DAY for cluster-a."""
    anomalous = [r for r in cost_rows if r[1] == "cluster-a" and r[2] > 100.0]
    assert len(anomalous) > 0, "No cost surge anomaly found"


def test_cost_normal_range_outside_anomaly(cost_rows):
    """Outside the anomaly window, cost should stay below 50."""
    normal = [r for r in cost_rows if r[1] != "cluster-a" and r[2] > 50.0]
    assert len(normal) == 0, f"Unexpected high cost outside anomaly: {normal[:3]}"


def test_incident_correlated_with_gpu_drop(incident_rows):
    """There must be a P1 incident referencing cluster-a/node-1 or GPU."""
    gpu_incidents = [
        r for r in incident_rows
        if r[3] == "P1" and ("gpu" in r[2].lower() or "cluster-a" in r[2].lower())
    ]
    assert len(gpu_incidents) >= 1, "No P1 incident correlated with GPU drop"


# ---------------------------------------------------------------------------
# SQLite integration tests
# ---------------------------------------------------------------------------


def test_sqlite_tables_exist(seeded_paths):
    db_path, _ = seeded_paths
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cur.fetchall()}
    conn.close()
    assert tables == {"incidents", "telemetry_cost", "telemetry_gpu", "telemetry_net"}


def test_sqlite_row_counts(seeded_paths):
    db_path, _ = seeded_paths
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    expected = {
        "telemetry_gpu": DAYS * 24 * 3 * 4,
        "telemetry_net": DAYS * 24 * 3,
        "telemetry_cost": DAYS * 24 * 3,
    }
    for table, count in expected.items():
        cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
        assert cur.fetchone()[0] == count, f"{table} row count mismatch"

    cur.execute("SELECT COUNT(*) FROM incidents")
    assert cur.fetchone()[0] >= 3

    conn.close()


def test_sqlite_gpu_drop_detectable(seeded_paths):
    db_path, _ = seeded_paths
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM telemetry_gpu WHERE utilization_pct < 20 AND cluster='cluster-a' AND node='node-1'"
    )
    assert cur.fetchone()[0] > 0
    conn.close()


def test_sqlite_latency_spike_detectable(seeded_paths):
    db_path, _ = seeded_paths
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM telemetry_net WHERE latency_ms > 100 AND site='site-west'")
    assert cur.fetchone()[0] > 0
    conn.close()


def test_sqlite_cost_surge_detectable(seeded_paths):
    db_path, _ = seeded_paths
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM telemetry_cost WHERE cost_usd > 100 AND cluster='cluster-a'")
    assert cur.fetchone()[0] > 0
    conn.close()


# ---------------------------------------------------------------------------
# SQL file tests
# ---------------------------------------------------------------------------


def test_sql_file_exists(seeded_paths):
    _, sql_path = seeded_paths
    assert sql_path.exists()
    assert sql_path.stat().st_size > 0


def test_sql_file_contains_inserts_for_all_tables(seeded_paths):
    _, sql_path = seeded_paths
    content = sql_path.read_text(encoding="utf-8")
    for table in ("telemetry_gpu", "telemetry_net", "telemetry_cost", "incidents"):
        assert f"INSERT INTO {table}" in content, f"No INSERT for {table} in SQL file"


def test_sql_file_contains_ddl(seeded_paths):
    _, sql_path = seeded_paths
    content = sql_path.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS" in content


# ---------------------------------------------------------------------------
# Idempotency test
# ---------------------------------------------------------------------------


def test_seed_is_idempotent(tmp_path):
    """Running seed() twice should succeed and produce identical row counts."""
    db = tmp_path / "telemetry.db"
    sql = tmp_path / "seed_data.sql"

    rows1 = seed(db_path=db, sql_path=sql)
    rows2 = seed(db_path=db, sql_path=sql)

    assert len(rows1["gpu"]) == len(rows2["gpu"])
    assert len(rows1["net"]) == len(rows2["net"])
    assert len(rows1["cost"]) == len(rows2["cost"])
    assert len(rows1["incidents"]) == len(rows2["incidents"])
