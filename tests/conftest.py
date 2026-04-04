"""Shared pytest fixtures for unit and integration tests."""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path

import pytest

from agent.config import Settings
from data.seed_telemetry import (
    DDL,
    generate_cost_rows,
    generate_gpu_rows,
    generate_incident_rows,
    generate_net_rows,
    seed,
)


# ---------------------------------------------------------------------------
# SQLite database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    """Return the path to a temporary, seeded SQLite database file."""
    db_file = tmp_path / "test_agentops.db"
    sql_file = tmp_path / "test_seed.sql"
    seed(db_path=db_file, sql_path=sql_file)
    return str(db_file)


@pytest.fixture
def in_memory_db() -> sqlite3.Connection:
    """Return an open, seeded in-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(DDL)
    rng = random.Random(42)
    conn.executemany("INSERT INTO telemetry_gpu VALUES (?,?,?,?,?)", generate_gpu_rows(rng)[:200])
    rng2 = random.Random(42)
    conn.executemany("INSERT INTO telemetry_net VALUES (?,?,?,?,?)", generate_net_rows(rng2)[:200])
    rng3 = random.Random(42)
    conn.executemany("INSERT INTO telemetry_cost VALUES (?,?,?,?)", generate_cost_rows(rng3)[:200])
    conn.executemany("INSERT INTO incidents VALUES (?,?,?,?,?)", generate_incident_rows())
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Settings / config fixtures
# ---------------------------------------------------------------------------

# Minimal env values for Settings.from_env() to succeed without real Azure credentials.
_TEST_ENV = {
    "AZURE_AI_PROJECT_CONNECTION_STRING": "https://test.openai.azure.com/;project=test",
    "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
}


@pytest.fixture
def test_settings() -> Settings:
    """Return a Settings instance suitable for unit tests (no real Azure credentials)."""
    return Settings(
        azure_ai_project_connection_string=_TEST_ENV["AZURE_AI_PROJECT_CONNECTION_STRING"],
        azure_openai_endpoint=_TEST_ENV["AZURE_OPENAI_ENDPOINT"],
        azure_openai_deployment="gpt-4.1",
        db_mode="sqlite",
        enable_work_iq=True,
        enable_mcp=False,
    )


@pytest.fixture
def test_settings_work_iq_off() -> Settings:
    """Return a Settings instance with Work IQ disabled."""
    return Settings(
        azure_ai_project_connection_string=_TEST_ENV["AZURE_AI_PROJECT_CONNECTION_STRING"],
        azure_openai_endpoint=_TEST_ENV["AZURE_OPENAI_ENDPOINT"],
        enable_work_iq=False,
        enable_mcp=False,
    )


@pytest.fixture
def minimal_settings() -> Settings:
    """Return a Settings instance with no Azure credentials (for error-path tests)."""
    return Settings(
        azure_ai_project_connection_string=None,
        azure_openai_endpoint=None,
    )


# ---------------------------------------------------------------------------
# Environment variable fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def env_work_iq_enabled(monkeypatch: pytest.MonkeyPatch):
    """Set ENABLE_WORK_IQ=true for the duration of a test."""
    monkeypatch.setenv("ENABLE_WORK_IQ", "true")
    yield


@pytest.fixture
def env_work_iq_disabled(monkeypatch: pytest.MonkeyPatch):
    """Set ENABLE_WORK_IQ=false for the duration of a test."""
    monkeypatch.setenv("ENABLE_WORK_IQ", "false")
    yield


@pytest.fixture
def env_mcp_enabled(monkeypatch: pytest.MonkeyPatch):
    """Set ENABLE_MCP=true for the duration of a test."""
    monkeypatch.setenv("ENABLE_MCP", "true")
    yield


@pytest.fixture
def env_mcp_disabled(monkeypatch: pytest.MonkeyPatch):
    """Set ENABLE_MCP=false for the duration of a test."""
    monkeypatch.setenv("ENABLE_MCP", "false")
    yield
