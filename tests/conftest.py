"""Shared pytest fixtures for unit and integration tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from agent.config import AgentConfig
from tools.sql_telemetry import _DDL, _seed_db


# ---------------------------------------------------------------------------
# SQLite database fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    """Return the path to a temporary, seeded SQLite database file."""
    db_file = tmp_path / "test_agentops.db"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(_DDL)
    _seed_db(conn, days=3)  # 3 days of data is enough for tests
    conn.close()
    return str(db_file)


@pytest.fixture
def in_memory_db() -> sqlite3.Connection:
    """Return an open, seeded in-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(_DDL)
    _seed_db(conn, days=2)
    return conn


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_config(tmp_db_path: str) -> AgentConfig:
    """Return a test AgentConfig pointing at the temp SQLite DB."""
    return AgentConfig.for_testing(sqlite_db_path=tmp_db_path)


@pytest.fixture
def test_config_work_iq_off(tmp_db_path: str) -> AgentConfig:
    """Return a test AgentConfig with Work IQ disabled."""
    return AgentConfig.for_testing(sqlite_db_path=tmp_db_path, enable_work_iq=False)


@pytest.fixture
def test_config_mcp_on(tmp_db_path: str) -> AgentConfig:
    """Return a test AgentConfig with MCP enabled."""
    return AgentConfig.for_testing(sqlite_db_path=tmp_db_path, enable_mcp=True)


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
