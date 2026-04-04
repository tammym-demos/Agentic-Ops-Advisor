"""Tests for the local development scripts and data layer.

These tests are self-contained: they use temporary SQLite databases and do
not require any Azure configuration.
"""

from __future__ import annotations

import importlib
import os
import sqlite3
import sys
from pathlib import Path
from unittest import mock

import pytest

# Ensure repo root is on path
_REPO_ROOT = Path(__file__).parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# data/seed_telemetry.py tests
# ---------------------------------------------------------------------------


class TestSeedTelemetry:
    """Verify synthetic data generation."""

    def _fresh_conn(self, tmp_path: Path) -> sqlite3.Connection:
        db = tmp_path / "test.db"
        return sqlite3.connect(str(db))

    def test_create_schema_creates_all_tables(self, tmp_path: Path) -> None:
        from data.seed_telemetry import create_schema

        conn = self._fresh_conn(tmp_path)
        create_schema(conn)
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert tables == {"telemetry_gpu", "telemetry_net", "telemetry_cost", "incidents"}
        conn.close()

    def test_seed_inserts_rows_in_all_tables(self, tmp_path: Path) -> None:
        from data.seed_telemetry import create_schema, seed

        conn = self._fresh_conn(tmp_path)
        create_schema(conn)
        counts = seed(conn, days=7)
        conn.close()

        assert counts["telemetry_gpu"] > 0
        assert counts["telemetry_net"] > 0
        assert counts["telemetry_cost"] > 0
        assert counts["incidents"] > 0

    def test_seed_is_reproducible(self, tmp_path: Path) -> None:
        """Same seed value → same row counts."""
        from data.seed_telemetry import create_schema, seed

        conn1 = sqlite3.connect(str(tmp_path / "a.db"))
        conn2 = sqlite3.connect(str(tmp_path / "b.db"))
        create_schema(conn1)
        create_schema(conn2)
        counts1 = seed(conn1, days=7, seed_value=99)
        counts2 = seed(conn2, days=7, seed_value=99)
        conn1.close()
        conn2.close()

        assert counts1 == counts2

    def test_gpu_anomaly_is_present(self, tmp_path: Path) -> None:
        """GPU anomaly window should contain rows with utilisation < 25%."""
        from data.seed_telemetry import create_schema, seed

        conn = self._fresh_conn(tmp_path)
        create_schema(conn)
        seed(conn, days=30)

        rows = conn.execute(
            "SELECT utilization_pct FROM telemetry_gpu WHERE cluster='gpu-cluster-01' AND utilization_pct < 25"
        ).fetchall()
        conn.close()

        assert len(rows) > 0, "Expected planted GPU anomaly rows with utilisation < 25%"

    def test_network_anomaly_is_present(self, tmp_path: Path) -> None:
        """Network anomaly window should contain rows with latency > 100 ms."""
        from data.seed_telemetry import create_schema, seed

        conn = self._fresh_conn(tmp_path)
        create_schema(conn)
        seed(conn, days=30)

        rows = conn.execute(
            "SELECT latency_ms FROM telemetry_net WHERE site='eastus2-primary' AND latency_ms > 100"
        ).fetchall()
        conn.close()

        assert len(rows) > 0, "Expected planted network anomaly rows with latency > 100 ms"

    def test_open_incidents_exist(self, tmp_path: Path) -> None:
        from data.seed_telemetry import create_schema, seed

        conn = self._fresh_conn(tmp_path)
        create_schema(conn)
        seed(conn, days=30)

        rows = conn.execute("SELECT * FROM incidents WHERE status='open'").fetchall()
        conn.close()

        assert len(rows) >= 2, "Expected at least 2 open incidents"

    def test_seed_db_creates_file(self, tmp_path: Path) -> None:
        from data.seed_telemetry import seed_db

        db_path = str(tmp_path / "sub" / "telemetry.db")
        counts = seed_db(db_path, days=5)

        assert os.path.exists(db_path)
        assert counts["telemetry_gpu"] > 0


# ---------------------------------------------------------------------------
# tools/sql_telemetry.py tests
# ---------------------------------------------------------------------------


class TestSqlTelemetry:
    """Verify the SQL query tool surface works with a local SQLite database."""

    @pytest.fixture(autouse=True)
    def _patch_db_path(self, tmp_path: Path) -> None:
        """Seed a temporary database and point the tool at it."""
        from data.seed_telemetry import create_schema, seed

        db_path = str(tmp_path / "telemetry.db")
        conn = sqlite3.connect(db_path)
        create_schema(conn)
        seed(conn, days=30)
        conn.close()

        # Patch env so get_db_connection() uses the temp DB
        with mock.patch.dict(os.environ, {"DB_MODE": "sqlite", "SQLITE_DB_PATH": db_path}):
            # Reload module to pick up patched env
            import tools.sql_telemetry as m

            importlib.reload(m)
            yield
        importlib.reload(m)  # restore

    def test_query_gpu_utilization_returns_list(self) -> None:
        from tools.sql_telemetry import query_gpu_utilization

        results = query_gpu_utilization(hours_back=24)
        assert isinstance(results, list)
        if results:
            assert "cluster" in results[0]
            assert "avg_util" in results[0]

    def test_query_network_telemetry_returns_list(self) -> None:
        from tools.sql_telemetry import query_network_telemetry

        results = query_network_telemetry(hours_back=24)
        assert isinstance(results, list)
        if results:
            assert "site" in results[0]
            assert "avg_latency_ms" in results[0]

    def test_query_cost_trends_returns_list(self) -> None:
        from tools.sql_telemetry import query_cost_trends

        results = query_cost_trends(days_back=7)
        assert isinstance(results, list)
        if results:
            assert "cost_usd" in results[0]

    def test_query_incidents_open(self) -> None:
        from tools.sql_telemetry import query_incidents

        results = query_incidents(status="open")
        assert isinstance(results, list)
        assert all(r["status"] == "open" for r in results)

    def test_query_incidents_all(self) -> None:
        from tools.sql_telemetry import query_incidents

        results = query_incidents(status="all")
        assert isinstance(results, list)
        statuses = {r["status"] for r in results}
        assert "open" in statuses
        assert "resolved" in statuses

    def test_tool_definitions_valid(self) -> None:
        from tools.sql_telemetry import TOOL_DEFINITIONS

        assert len(TOOL_DEFINITIONS) >= 4
        for tool in TOOL_DEFINITIONS:
            assert tool["type"] == "function"
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_tool_callables_match_definitions(self) -> None:
        from tools.sql_telemetry import TOOL_CALLABLES, TOOL_DEFINITIONS

        defined_names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        callable_names = set(TOOL_CALLABLES.keys())
        assert defined_names == callable_names

    def test_missing_db_raises_file_not_found(self, tmp_path: Path) -> None:
        """get_db_connection should raise FileNotFoundError when DB is absent."""
        import tools.sql_telemetry as m

        with mock.patch.dict(
            os.environ,
            {"DB_MODE": "sqlite", "SQLITE_DB_PATH": str(tmp_path / "nonexistent.db")},
        ):
            importlib.reload(m)
            with pytest.raises(FileNotFoundError):
                with m.get_db_connection():
                    pass
        importlib.reload(m)


# ---------------------------------------------------------------------------
# scripts/setup_local_db.py tests
# ---------------------------------------------------------------------------


class TestSetupLocalDb:
    """Verify the setup script creates and verifies the database correctly."""

    def test_main_creates_and_verifies_db(self, tmp_path: Path) -> None:
        from scripts.setup_local_db import main

        db_path = str(tmp_path / "telemetry.db")
        exit_code = main(["--db", db_path, "--days", "7"])
        assert exit_code == 0
        assert os.path.exists(db_path)

    def test_main_idempotent_on_existing_db(self, tmp_path: Path) -> None:
        """Running setup twice on the same DB should exit 0 without re-seeding."""
        from scripts.setup_local_db import main

        db_path = str(tmp_path / "telemetry.db")
        assert main(["--db", db_path, "--days", "7"]) == 0
        assert main(["--db", db_path, "--days", "7"]) == 0

    def test_force_flag_recreates_db(self, tmp_path: Path) -> None:
        from scripts.setup_local_db import main

        db_path = str(tmp_path / "telemetry.db")
        assert main(["--db", db_path, "--days", "7"]) == 0
        mtime_before = os.path.getmtime(db_path)

        import time
        time.sleep(0.05)  # ensure mtime difference

        assert main(["--db", db_path, "--days", "7", "--force"]) == 0
        mtime_after = os.path.getmtime(db_path)
        assert mtime_after > mtime_before, "Expected DB to be recreated with --force"

    def test_step_verify_passes_for_seeded_db(self, tmp_path: Path) -> None:
        from data.seed_telemetry import create_schema, seed
        from scripts.setup_local_db import step_verify

        db_path = str(tmp_path / "telemetry.db")
        conn = sqlite3.connect(db_path)
        create_schema(conn)
        seed(conn, days=30)
        ok = step_verify(conn)
        conn.close()
        assert ok

    def test_step_verify_fails_for_empty_db(self, tmp_path: Path) -> None:
        from data.seed_telemetry import create_schema
        from scripts.setup_local_db import step_verify

        db_path = str(tmp_path / "telemetry.db")
        conn = sqlite3.connect(db_path)
        create_schema(conn)
        ok = step_verify(conn)
        conn.close()
        assert not ok
