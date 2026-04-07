"""Unit tests for tools/ — sql_telemetry, work_context_stub, action_stub.

Tests the actual public API of each tool module, using correct function
signatures and expected return types.
"""

from __future__ import annotations

import json

import pytest


# ---------------------------------------------------------------------------
# sql_telemetry
# ---------------------------------------------------------------------------


class TestQueryTelemetry:
    """Tests for tools.sql_telemetry.query_telemetry (async, keyword-arg API)."""

    @pytest.mark.asyncio
    async def test_table_query_returns_json(self):
        from tools.sql_telemetry import query_telemetry

        result_json = await query_telemetry(table="telemetry_gpu", limit=5)
        result = json.loads(result_json)
        # Either returns data or a graceful error — never crashes
        assert isinstance(result, dict)
        assert "meta" in result

    @pytest.mark.asyncio
    async def test_invalid_table_returns_error(self):
        from tools.sql_telemetry import query_telemetry

        result_json = await query_telemetry(table="nonexistent")
        result = json.loads(result_json)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_no_args_returns_error(self):
        from tools.sql_telemetry import query_telemetry

        result_json = await query_telemetry()
        result = json.loads(result_json)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_non_select_blocked(self):
        from tools.sql_telemetry import query_telemetry

        result_json = await query_telemetry(sql="DROP TABLE telemetry_gpu")
        result = json.loads(result_json)
        assert "error" in result

    def test_tool_schema_structure(self):
        from tools.sql_telemetry import TOOL_SCHEMA

        assert TOOL_SCHEMA["type"] == "function"
        fn = TOOL_SCHEMA["function"]
        assert fn["name"] == "query_telemetry"
        assert "parameters" in fn

    def test_get_tool_definition(self):
        from tools.sql_telemetry import TOOL_SCHEMA, get_tool_definition

        assert get_tool_definition() is TOOL_SCHEMA

    def test_list_aggregates_returns_known_keys(self):
        from tools.sql_telemetry import list_aggregates

        aggs = list_aggregates()
        assert "gpu_avg_util_1h" in aggs
        assert "open_incidents" in aggs

    def test_validate_sql_rejects_dml(self):
        from tools.sql_telemetry import _validate_sql

        with pytest.raises(ValueError, match="Only SELECT"):
            _validate_sql("DELETE FROM telemetry_gpu WHERE 1=1")

    def test_validate_sql_accepts_valid(self):
        from tools.sql_telemetry import _validate_sql

        _validate_sql("SELECT * FROM telemetry_gpu WHERE 1=1")

    # -- Issue #92 edge-case tests ------------------------------------------

    @pytest.mark.asyncio
    async def test_postgres_syntax_returns_error(self):
        """PostgreSQL-style SQL should fail with a clear error (SQLite only)."""
        from tools.sql_telemetry import query_telemetry

        result_json = await query_telemetry(
            sql="SELECT * FROM telemetry_gpu WHERE ts > NOW() - INTERVAL '24 HOURS'"
        )
        result = json.loads(result_json)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_wrong_table_name_gpu_utilization(self):
        """The LLM's actual mistake (gpu_utilization) should list valid tables."""
        from tools.sql_telemetry import query_telemetry

        result_json = await query_telemetry(table="gpu_utilization")
        result = json.loads(result_json)
        assert "error" in result
        # Error message must guide the LLM to the correct table names
        assert "telemetry_gpu" in result["error"]
        assert "telemetry_net" in result["error"]
        assert "telemetry_cost" in result["error"]
        assert "incidents" in result["error"]

    @pytest.mark.asyncio
    async def test_wrong_column_name_utilization(self):
        """Wrong column 'utilization' (should be 'utilization_pct') triggers error."""
        from tools.sql_telemetry import query_telemetry

        result_json = await query_telemetry(
            sql="SELECT AVG(utilization) FROM telemetry_gpu"
        )
        result = json.loads(result_json)
        assert "error" in result

    def test_tool_schema_table_description_includes_columns(self):
        """TOOL_SCHEMA table property description must list column names."""
        from tools.sql_telemetry import TOOL_SCHEMA

        table_desc = TOOL_SCHEMA["function"]["parameters"]["properties"]["table"]["description"]
        for col in ("utilization_pct", "latency_ms", "cost_usd"):
            assert col in table_desc, f"Column '{col}' missing from table description"

    def test_tool_schema_sql_mentions_sqlite(self):
        """TOOL_SCHEMA sql description must mention SQLite so the LLM uses correct syntax."""
        from tools.sql_telemetry import TOOL_SCHEMA

        sql_desc = TOOL_SCHEMA["function"]["parameters"]["properties"]["sql"]["description"]
        assert "sqlite" in sql_desc.lower(), "sql description must mention SQLite"


# ---------------------------------------------------------------------------
# work_context_stub
# ---------------------------------------------------------------------------


class TestWorkContextStub:
    """Tests for tools.work_context_stub public functions."""

    def test_get_change_events_returns_list(self):
        from tools.work_context_stub import get_change_events

        events = get_change_events("gpu-cluster")
        assert isinstance(events, list)

    def test_get_decisions_returns_list(self):
        from tools.work_context_stub import get_decisions

        decisions = get_decisions("gpu-cluster")
        assert isinstance(decisions, list)

    def test_get_ownership_returns_dict(self):
        from tools.work_context_stub import get_ownership

        info = get_ownership("gpu-cluster")
        assert isinstance(info, dict)

    def test_get_runbooks_returns_list(self):
        from tools.work_context_stub import get_runbooks

        runbooks = get_runbooks("gpu-cluster")
        assert isinstance(runbooks, list)

    def test_get_full_context_has_disclaimer(self):
        from tools.work_context_stub import get_full_context

        ctx = get_full_context("gpu-cluster")
        assert "disclaimer" in ctx
        assert "Work IQ" in ctx["disclaimer"]

    def test_get_full_context_has_all_sections(self):
        from tools.work_context_stub import get_full_context

        ctx = get_full_context("gpu-cluster")
        for key in ("change_events", "decisions", "ownership", "runbooks"):
            assert key in ctx

    # -- Issue #92 edge-case tests ------------------------------------------

    def test_cluster_name_maps_to_gpu_cluster(self):
        """Cluster name 'prod-east-01' should resolve to 'gpu-cluster', not 'default'."""
        from tools.work_context_stub import _service_key

        assert _service_key("prod-east-01") == "gpu-cluster"

    def test_cluster_name_maps_to_network(self):
        """Cluster name 'cdn-west' should resolve to 'network', not 'default'."""
        from tools.work_context_stub import _service_key

        assert _service_key("cdn-west") == "network"

    def test_exact_service_name_gpu_cluster(self):
        from tools.work_context_stub import _service_key

        assert _service_key("gpu-cluster") == "gpu-cluster"

    def test_exact_service_name_network(self):
        from tools.work_context_stub import _service_key

        assert _service_key("network") == "network"

    def test_exact_service_name_cost(self):
        from tools.work_context_stub import _service_key

        assert _service_key("cost") == "cost"

    def test_unknown_service_falls_back_to_default(self):
        from tools.work_context_stub import _service_key

        assert _service_key("totally-unknown-service") == "default"

    def test_tool_schema_service_enum(self):
        """TOOL_SCHEMA must expose a service enum with all three categories."""
        from tools.work_context_stub import TOOL_SCHEMA

        svc_prop = TOOL_SCHEMA["function"]["parameters"]["properties"]["service"]
        assert "enum" in svc_prop
        assert set(svc_prop["enum"]) == {"gpu-cluster", "network", "cost"}


# ---------------------------------------------------------------------------
# action_stub
# ---------------------------------------------------------------------------


class TestActionStub:
    """Tests for tools.action_stub — propose_change and request_approval."""

    def test_propose_change_returns_json(self):
        from tools.action_stub import propose_change

        result_json = propose_change("Restart the GPU scheduler service")
        result = json.loads(result_json)
        assert "id" in result
        assert "risk_level" in result
        assert "status" in result
        assert result["status"] == "proposed"
        assert "disclaimer" in result

    def test_propose_change_high_risk(self):
        from tools.action_stub import propose_change

        result_json = propose_change("Delete all data from the production database")
        result = json.loads(result_json)
        assert result["risk_level"] == "high"
        assert "human_approval_gate" in result

    def test_propose_change_low_risk(self):
        from tools.action_stub import propose_change

        result_json = propose_change("Check the dashboard for anomalies")
        result = json.loads(result_json)
        assert result["risk_level"] == "low"

    def test_propose_change_medium_risk(self):
        from tools.action_stub import propose_change

        result_json = propose_change("Restart the API gateway")
        result = json.loads(result_json)
        assert result["risk_level"] == "medium"

    def test_request_approval_returns_json(self):
        from tools.action_stub import propose_change, request_approval

        proposal = json.loads(propose_change("Scale up the cluster"))
        change_id = proposal["id"]

        approval_json = request_approval(change_id)
        approval = json.loads(approval_json)
        assert "approval_status" in approval
        assert approval["approval_status"] in ("pending", "approved", "rejected")
        assert "disclaimer" in approval

    def test_action_stub_tool_definitions(self):
        from tools.action_stub import ACTION_STUB_TOOL_DEFINITIONS

        assert len(ACTION_STUB_TOOL_DEFINITIONS) == 2
        names = {t["function"]["name"] for t in ACTION_STUB_TOOL_DEFINITIONS}
        assert "propose_change" in names
        assert "request_approval" in names


