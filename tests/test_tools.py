"""Unit and integration tests for tool surfaces.

Tests use a real SQLite database (no mocks for the DB layer).
"""

from __future__ import annotations

import json

import pytest

from tools.action_stub import propose_change, request_approval
from tools.sql_telemetry import query_telemetry
from tools.work_context_stub import get_runbook, get_work_context


# ===========================================================================
# SQL Telemetry Tool Tests (real SQLite, no mocks)
# ===========================================================================


class TestSqlTelemetryTool:
    """Tests for the SQL telemetry tool using a real SQLite database."""

    @pytest.mark.asyncio
    async def test_query_gpu_returns_rows(self, tmp_db_path: str):
        """GPU query should return aggregated rows for all cluster/node combos."""
        result = await query_telemetry("gpu", hours_back=72, db_path=tmp_db_path)
        rows = json.loads(result)
        assert isinstance(rows, list), "Expected a list of rows"
        assert len(rows) > 0, "Expected at least one GPU telemetry row"
        # Each row should have expected keys
        row = rows[0]
        assert "cluster" in row
        assert "node" in row
        assert "avg_util" in row

    @pytest.mark.asyncio
    async def test_query_network_returns_rows(self, tmp_db_path: str):
        """Network query should return aggregated rows per site."""
        result = await query_telemetry("network", hours_back=72, db_path=tmp_db_path)
        rows = json.loads(result)
        assert isinstance(rows, list)
        assert len(rows) > 0
        assert "site" in rows[0]
        assert "avg_latency" in rows[0]

    @pytest.mark.asyncio
    async def test_query_cost_returns_rows(self, tmp_db_path: str):
        """Cost query should return rows with total_cost per cluster."""
        result = await query_telemetry("cost", hours_back=72, db_path=tmp_db_path)
        rows = json.loads(result)
        assert isinstance(rows, list)
        assert len(rows) > 0
        assert "total_cost" in rows[0]

    @pytest.mark.asyncio
    async def test_query_incidents_returns_rows(self, tmp_db_path: str):
        """Incidents query should return seeded incident rows."""
        result = await query_telemetry("incidents", hours_back=720, db_path=tmp_db_path)
        rows = json.loads(result)
        assert isinstance(rows, list)
        assert len(rows) > 0
        assert "service" in rows[0]
        assert "severity" in rows[0]

    @pytest.mark.asyncio
    async def test_query_summary_returns_three_metric_types(self, tmp_db_path: str):
        """Summary query should return a row for each of: gpu, network, cost."""
        result = await query_telemetry("summary", hours_back=72, db_path=tmp_db_path)
        rows = json.loads(result)
        metric_types = {r["metric_type"] for r in rows}
        assert metric_types == {"gpu", "network", "cost"}

    @pytest.mark.asyncio
    async def test_query_unknown_type_returns_error(self, tmp_db_path: str):
        """Unknown query_type should return an error JSON, not raise an exception."""
        result = await query_telemetry("nonexistent", db_path=tmp_db_path)
        data = json.loads(result)
        assert "error" in data
        assert "nonexistent" in data["error"]

    @pytest.mark.asyncio
    async def test_planted_gpu_anomaly_detectable(self, tmp_db_path: str):
        """The planted GPU utilization drop (cluster-a, ~25h ago) should lower avg_util."""
        result = await query_telemetry("gpu", hours_back=72, db_path=tmp_db_path)
        rows = json.loads(result)
        # Find gpu-cluster-a rows
        cluster_a = [r for r in rows if r["cluster"] == "gpu-cluster-a"]
        assert len(cluster_a) > 0, "Expected rows for gpu-cluster-a"
        # The min_util should reflect the planted drop
        min_vals = [r["min_util"] for r in cluster_a]
        assert min(min_vals) < 25, "Expected planted anomaly (util < 25%) to be present"

    @pytest.mark.asyncio
    async def test_hours_back_zero_returns_empty_or_minimal(self, tmp_db_path: str):
        """hours_back=0 should return very few or no rows (only this instant)."""
        result = await query_telemetry("gpu", hours_back=0, db_path=tmp_db_path)
        rows = json.loads(result)
        # Should not raise an error
        assert isinstance(rows, list)


# ===========================================================================
# Work IQ Context Stub Tests
# ===========================================================================


class TestWorkContextStub:
    """Tests for the Work IQ context stub with feature flag toggling."""

    def test_get_all_context_when_enabled(self, env_work_iq_enabled):
        """When ENABLE_WORK_IQ=true, get_work_context() returns all context types."""
        result = json.loads(get_work_context())
        assert "change_events" in result
        assert "decisions" in result
        assert "ownership" in result
        assert "runbooks" in result

    def test_disabled_flag_returns_disabled_status(self, env_work_iq_disabled):
        """When ENABLE_WORK_IQ=false, get_work_context() returns a disabled message."""
        result = json.loads(get_work_context())
        assert result["status"] == "disabled"
        assert "ENABLE_WORK_IQ" in result["message"]

    def test_topic_filter_change_events(self, env_work_iq_enabled):
        """Filtering by 'change_events' returns only change_events key."""
        result = json.loads(get_work_context(topic="change_events"))
        assert "change_events" in result
        assert "decisions" not in result
        assert len(result["change_events"]) > 0

    def test_topic_filter_decisions(self, env_work_iq_enabled):
        """Filtering by 'decisions' returns only decisions key."""
        result = json.loads(get_work_context(topic="decisions"))
        assert "decisions" in result
        assert "change_events" not in result

    def test_topic_filter_ownership(self, env_work_iq_enabled):
        """Filtering by 'ownership' returns ownership map."""
        result = json.loads(get_work_context(topic="ownership"))
        assert "ownership" in result
        assert "gpu-cluster-a" in result["ownership"]

    def test_disclaimer_present_when_enabled(self, env_work_iq_enabled):
        """Response should always include the Work IQ simulation disclaimer."""
        result = json.loads(get_work_context())
        assert "_disclaimer" in result
        assert "simulation" in result["_disclaimer"].lower() or "simulating" in result["_disclaimer"].lower()

    def test_get_runbook_valid_key(self, env_work_iq_enabled):
        """get_runbook() with a valid key returns a runbook with steps."""
        result = json.loads(get_runbook("gpu_utilization_drop"))
        assert "steps" in result
        assert isinstance(result["steps"], list)
        assert len(result["steps"]) > 0

    def test_get_runbook_invalid_key(self, env_work_iq_enabled):
        """get_runbook() with an invalid key returns an error message."""
        result = json.loads(get_runbook("unknown_symptom"))
        assert "error" in result

    def test_get_runbook_disabled(self, env_work_iq_disabled):
        """get_runbook() returns disabled status when ENABLE_WORK_IQ=false."""
        result = json.loads(get_runbook("latency_spike"))
        assert result["status"] == "disabled"


# ===========================================================================
# Action Stub Tests
# ===========================================================================


class TestActionStub:
    """Tests for the action stub tool (propose_change, request_approval)."""

    def test_propose_change_returns_valid_payload(self):
        """propose_change() should return a JSON payload with required fields."""
        result = json.loads(propose_change("Restart the scheduler service on node-01"))
        assert "request_id" in result
        assert "status" in result
        assert result["status"] == "draft"
        assert result["_simulation"] is True

    def test_propose_change_generates_unique_ids(self):
        """Each call to propose_change() should generate a unique request_id."""
        r1 = json.loads(propose_change("Restart scheduler"))
        r2 = json.loads(propose_change("Restart scheduler"))
        assert r1["request_id"] != r2["request_id"]

    def test_propose_change_high_risk_for_delete(self):
        """Plans containing 'delete' should be flagged as high risk."""
        result = json.loads(propose_change("Delete all stale jobs from gpu-cluster-a"))
        assert result["risk_level"] == "high"
        assert result["approval_required"] is True

    def test_propose_change_low_risk_for_restart(self):
        """Plans containing 'restart' should be flagged as low risk."""
        result = json.loads(propose_change("Restart the affected service"))
        assert result["risk_level"] == "low"

    def test_request_approval_low_risk_auto_approves(self):
        """Low-risk change requests should be auto-approved."""
        payload = propose_change("Reload config on single node")
        result = json.loads(request_approval(payload))
        assert result["approval_status"] == "approved"
        assert result["_simulation"] is True

    def test_request_approval_high_risk_stays_pending(self):
        """High-risk change requests should remain pending for human review."""
        payload = propose_change("Delete all nodes in cluster")
        result = json.loads(request_approval(payload))
        assert result["approval_status"] == "pending"

    def test_request_approval_accepts_request_id_string(self):
        """request_approval() should accept a raw request_id string (not full JSON)."""
        result = json.loads(request_approval("CR-ABCD1234"))
        assert "approval_status" in result
        assert result["request_id"] == "CR-ABCD1234"


# ===========================================================================
# MCP Wrapper Tests
# ===========================================================================


class TestMcpWrapper:
    """Tests for the optional MCP wrapper initialization and routing."""

    def test_mcp_disabled_by_default(self, env_mcp_disabled):
        """is_mcp_enabled() should return False when ENABLE_MCP=false."""
        from tools.work_context_mcp import is_mcp_enabled

        assert is_mcp_enabled() is False

    def test_mcp_enabled_when_flag_set(self, env_mcp_enabled):
        """is_mcp_enabled() should return True when ENABLE_MCP=true."""
        from tools.work_context_mcp import is_mcp_enabled

        assert is_mcp_enabled() is True

    def test_list_tools_empty_when_disabled(self, env_mcp_disabled):
        """list_tools() should return an empty list when MCP is disabled."""
        from tools.work_context_mcp import list_tools

        assert list_tools() == []

    def test_list_tools_nonempty_when_enabled(self, env_mcp_enabled):
        """list_tools() should return tool schemas when MCP is enabled."""
        from tools.work_context_mcp import list_tools

        tools = list_tools()
        assert len(tools) >= 2
        names = {t["name"] for t in tools}
        assert "get_work_context" in names
        assert "get_runbook" in names

    def test_handle_tool_call_disabled_returns_disabled(self, env_mcp_disabled):
        """handle_tool_call() should return disabled status when MCP is off."""
        from tools.work_context_mcp import handle_tool_call

        result = json.loads(handle_tool_call("get_work_context", {}))
        assert result["status"] == "disabled"

    def test_handle_tool_call_get_work_context(self, env_mcp_enabled, env_work_iq_enabled):
        """handle_tool_call('get_work_context') should route to the work context stub."""
        from tools.work_context_mcp import handle_tool_call

        result = json.loads(handle_tool_call("get_work_context", {"topic": "decisions"}))
        assert "decisions" in result

    def test_handle_tool_call_unknown_tool(self, env_mcp_enabled):
        """handle_tool_call() with an unknown tool name should return an error."""
        from tools.work_context_mcp import handle_tool_call

        result = json.loads(handle_tool_call("nonexistent_tool", {}))
        assert "error" in result
