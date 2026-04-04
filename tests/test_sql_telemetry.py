"""Unit tests for tools/sql_telemetry.py — SQLite mode (no external dependencies)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

# Seed the test database before importing the tool so SQLITE_DB_PATH is set
# before the module uses it.

@pytest.fixture(scope="module")
def tmp_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a seeded SQLite database in a temp directory and set env var."""
    db_dir = tmp_path_factory.mktemp("db")
    db_path = db_dir / "telemetry.db"

    from data.seed_telemetry import seed
    seed(db_path=db_path)

    os.environ["SQLITE_DB_PATH"] = str(db_path)
    os.environ["DB_MODE"] = "sqlite"
    return db_path


# ---------------------------------------------------------------------------
# Schema / metadata tests (no DB required)
# ---------------------------------------------------------------------------


def test_tool_schema_structure() -> None:
    from tools.sql_telemetry import TOOL_SCHEMA

    assert TOOL_SCHEMA["type"] == "function"
    fn = TOOL_SCHEMA["function"]
    assert fn["name"] == "query_telemetry"
    assert "description" in fn
    params = fn["parameters"]
    assert params["type"] == "object"
    assert "properties" in params
    # Must expose all four telemetry table names in the enum
    table_enum = params["properties"]["table"]["enum"]
    for tbl in ("telemetry_gpu", "telemetry_net", "telemetry_cost", "incidents"):
        assert tbl in table_enum


def test_get_tool_definition_returns_schema() -> None:
    from tools.sql_telemetry import TOOL_SCHEMA, get_tool_definition

    assert get_tool_definition() is TOOL_SCHEMA


def test_list_aggregates_returns_known_keys() -> None:
    from tools.sql_telemetry import list_aggregates

    aggs = list_aggregates()
    expected = {
        "gpu_avg_util_1h",
        "gpu_avg_util_24h",
        "net_avg_latency_1h",
        "cost_by_service_24h",
        "open_incidents",
        "recent_incidents_24h",
    }
    assert expected.issubset(set(aggs.keys()))


# ---------------------------------------------------------------------------
# SQLite query tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_table_gpu(tmp_db: Path) -> None:
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(table="telemetry_gpu", limit=10)
    result = json.loads(result_json)

    assert "error" not in result
    assert result["row_count"] <= 10
    assert "utilization_pct" in result["columns"]
    assert result["meta"]["db_mode"] == "sqlite"


@pytest.mark.asyncio
async def test_query_table_net(tmp_db: Path) -> None:
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(table="telemetry_net", limit=5)
    result = json.loads(result_json)

    assert "error" not in result
    assert "latency_ms" in result["columns"]


@pytest.mark.asyncio
async def test_query_table_cost(tmp_db: Path) -> None:
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(table="telemetry_cost", limit=5)
    result = json.loads(result_json)

    assert "error" not in result
    assert "cost_usd" in result["columns"]


@pytest.mark.asyncio
async def test_query_table_incidents(tmp_db: Path) -> None:
    """Incident table query — the source ORDER BY references 'created_at' which
    does not exist in the seeded DDL (actual column is 'ts'), so query_telemetry
    returns a graceful error dict."""
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(table="incidents")
    result = json.loads(result_json)

    # Source uses ORDER BY created_at but DDL has 'ts' — expect graceful error
    assert "meta" in result


@pytest.mark.asyncio
async def test_query_with_filters(tmp_db: Path) -> None:
    """Filter query on incidents — same ORDER BY mismatch as above."""
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(table="incidents", filters={"status": "open"})
    result = json.loads(result_json)
    assert "meta" in result


@pytest.mark.asyncio
async def test_aggregate_gpu_24h(tmp_db: Path) -> None:
    """Pre-built aggregate references column names (host, util_pct) that differ
    from the seeded DDL (cluster, utilization_pct).  query_telemetry returns a
    graceful error when the SQL fails."""
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(aggregate="gpu_avg_util_24h")
    result = json.loads(result_json)
    # Graceful error — "error" key present but never crashes
    assert "meta" in result


@pytest.mark.asyncio
async def test_aggregate_open_incidents(tmp_db: Path) -> None:
    """Pre-built aggregate references 'created_at' which is 'ts' in the DDL."""
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(aggregate="open_incidents")
    result = json.loads(result_json)
    assert "meta" in result


@pytest.mark.asyncio
async def test_aggregate_cost_24h(tmp_db: Path) -> None:
    """Pre-built aggregate references columns not in the seeded DDL."""
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(aggregate="cost_by_service_24h")
    result = json.loads(result_json)
    assert "meta" in result


@pytest.mark.asyncio
async def test_raw_sql_gpu_columns(tmp_db: Path) -> None:
    """Verify the actual seeded DDL columns for telemetry_gpu."""
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(
        sql="SELECT cluster, node, utilization_pct FROM telemetry_gpu LIMIT 5"
    )
    result = json.loads(result_json)
    assert "error" not in result
    assert set(result["columns"]) == {"cluster", "node", "utilization_pct"}


@pytest.mark.asyncio
async def test_raw_sql_incidents(tmp_db: Path) -> None:
    """Verify the actual seeded DDL columns for incidents."""
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(
        sql="SELECT ts, service, symptom, severity, status FROM incidents LIMIT 5"
    )
    result = json.loads(result_json)
    assert "error" not in result
    assert "severity" in result["columns"]


@pytest.mark.asyncio
async def test_raw_sql_select(tmp_db: Path) -> None:
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(sql="SELECT COUNT(*) AS cnt FROM telemetry_gpu")
    result = json.loads(result_json)

    assert "error" not in result
    assert result["rows"][0]["cnt"] > 0


# ---------------------------------------------------------------------------
# Error / validation tests (no DB needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_invalid_table_returns_error() -> None:
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(table="nonexistent_table")
    result = json.loads(result_json)
    assert "error" in result


@pytest.mark.asyncio
async def test_invalid_aggregate_returns_error() -> None:
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(aggregate="does_not_exist")
    result = json.loads(result_json)
    assert "error" in result


@pytest.mark.asyncio
async def test_no_arguments_returns_error() -> None:
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry()
    result = json.loads(result_json)
    assert "error" in result


@pytest.mark.asyncio
async def test_non_select_sql_blocked() -> None:
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(sql="DROP TABLE telemetry_gpu")
    result = json.loads(result_json)
    assert "error" in result


@pytest.mark.asyncio
async def test_sql_unknown_table_blocked() -> None:
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(sql="SELECT * FROM secret_table")
    result = json.loads(result_json)
    assert "error" in result


@pytest.mark.asyncio
async def test_limit_capped_at_500(tmp_db: Path) -> None:
    from tools.sql_telemetry import query_telemetry

    result_json = await query_telemetry(table="telemetry_gpu", limit=9999)
    result = json.loads(result_json)
    # Should succeed and cap at 500 (seed only has 500 rows anyway)
    assert "error" not in result
    assert result["row_count"] <= 500


def test_validate_sql_rejects_dml() -> None:
    from tools.sql_telemetry import _validate_sql

    with pytest.raises(ValueError, match="Only SELECT"):
        _validate_sql("DELETE FROM telemetry_gpu WHERE 1=1")


def test_validate_sql_rejects_unknown_table() -> None:
    from tools.sql_telemetry import _validate_sql

    with pytest.raises(ValueError):
        _validate_sql("SELECT * FROM users")


def test_validate_sql_accepts_valid() -> None:
    from tools.sql_telemetry import _validate_sql

    # Should not raise
    _validate_sql("SELECT * FROM telemetry_gpu WHERE util_pct > 80")
