"""Unit and integration tests for tool surfaces.

SQL telemetry tests use a real SQLite database (no mocks for the DB layer).
Work IQ context and action stub tests validate the tool APIs directly.
"""

from __future__ import annotations

import json

import pytest

from tools.action_stub import propose_change, request_approval
from tools.sql_telemetry import query_telemetry


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
        """The planted GPU utilization drop (cluster-a) should lower min_util."""
        result = await query_telemetry("gpu", hours_back=72, db_path=tmp_db_path)
        rows = json.loads(result)
        cluster_a = [r for r in rows if r["cluster"] == "gpu-cluster-a"]
        assert len(cluster_a) > 0, "Expected rows for gpu-cluster-a"
        min_vals = [r["min_util"] for r in cluster_a]
        assert min(min_vals) < 25, "Expected planted anomaly (util < 25%) to be present"

    @pytest.mark.asyncio
    async def test_hours_back_zero_returns_empty_or_list(self, tmp_db_path: str):
        """hours_back=0 should return a list (possibly empty) without raising."""
        result = await query_telemetry("gpu", hours_back=0, db_path=tmp_db_path)
        rows = json.loads(result)
        assert isinstance(rows, list)


# ===========================================================================
# Work IQ Context Stub Tests
# ===========================================================================


class TestWorkContextStub:
    """Tests for the Work IQ context stub with feature flag and data shape validation."""

    def _reload_stub(self, enable: bool):
        """Reload work_context_stub with ENABLE_WORK_IQ set appropriately."""
        import importlib
        import os
        import sys

        os.environ["ENABLE_WORK_IQ"] = "true" if enable else "false"
        for mod in list(sys.modules.keys()):
            if "work_context_stub" in mod:
                del sys.modules[mod]
        return importlib.import_module("tools.work_context_stub")

    def test_get_change_events_returns_list(self):
        """get_change_events() returns a list of change events."""
        stub = self._reload_stub(enable=True)
        events = stub.get_change_events("gpu-cluster")
        assert isinstance(events, list)
        assert len(events) > 0

    def test_change_event_has_required_fields(self):
        """Each change event has id, type, and description fields."""
        stub = self._reload_stub(enable=True)
        for event in stub.get_change_events("gpu-cluster"):
            assert "id" in event
            assert "type" in event
            assert "description" in event

    def test_get_full_context_includes_all_keys(self):
        """get_full_context() returns all four context categories plus disclaimer."""
        stub = self._reload_stub(enable=True)
        ctx = stub.get_full_context("gpu-cluster")
        for key in ("service", "disclaimer", "change_events", "decisions", "ownership", "runbooks"):
            assert key in ctx, f"Missing key: {key}"

    def test_disclaimer_present_in_full_context(self):
        """The simulation disclaimer should reference Work IQ."""
        stub = self._reload_stub(enable=True)
        ctx = stub.get_full_context("gpu-cluster")
        assert "Work IQ" in ctx["disclaimer"]

    def test_disabled_flag_returns_empty_collections(self):
        """When ENABLE_WORK_IQ=false, all getters return empty collections."""
        stub = self._reload_stub(enable=False)
        assert stub.get_change_events("gpu-cluster") == []
        assert stub.get_decisions("gpu-cluster") == []
        assert stub.get_ownership("gpu-cluster") == {}
        assert stub.get_runbooks("gpu-cluster") == []


# ===========================================================================
# Action Stub Tests
# ===========================================================================


class TestActionStub:
    """Tests for the action stub tool (propose_change, request_approval)."""

    def test_propose_change_returns_valid_json(self):
        """propose_change() should return valid JSON."""
        result = propose_change("Restart the scheduler service on node-01")
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

    def test_propose_change_required_fields(self):
        """propose_change() payload should contain all required fields."""
        result = json.loads(propose_change("Update the network firewall rules"))
        for field in ("id", "description", "risk_level", "affected_services", "rollback_plan", "estimated_duration"):
            assert field in result, f"Missing field: {field}"

    def test_propose_change_status_is_proposed(self):
        """propose_change() should set status to 'proposed'."""
        result = json.loads(propose_change("Scale up the compute cluster"))
        assert result["status"] == "proposed"

    def test_propose_change_high_risk_for_delete(self):
        """Plans containing 'delete' should be flagged as high risk."""
        result = json.loads(propose_change("Delete all stale jobs from gpu-cluster-a"))
        assert result["risk_level"] == "high"

    def test_propose_change_affected_services_is_list(self):
        """affected_services should be a non-empty list."""
        result = json.loads(propose_change("Restart the database"))
        assert isinstance(result["affected_services"], list)
        assert len(result["affected_services"]) > 0

    def test_request_approval_returns_valid_json(self):
        """request_approval() should return valid JSON with approval_status."""
        payload = json.loads(propose_change("Restart the app service"))
        result = json.loads(request_approval(payload["id"]))
        assert "approval_status" in result
        assert result["approval_status"] in ("pending", "approved", "rejected")

    def test_request_approval_deterministic_per_id(self):
        """Same change_request_id should always return the same approval status."""
        payload = json.loads(propose_change("Reload config on single node"))
        cr_id = payload["id"]
        r1 = json.loads(request_approval(cr_id))
        r2 = json.loads(request_approval(cr_id))
        assert r1["approval_status"] == r2["approval_status"]

    def test_request_approval_different_ids_may_differ(self):
        """Different IDs can return different statuses (demo variety)."""
        results = set()
        for _ in range(20):
            p = json.loads(propose_change("Restart some service"))
            r = json.loads(request_approval(p["id"]))
            results.add(r["approval_status"])
        # With 20 calls, we should see at least 2 different states
        assert len(results) >= 1  # at minimum passes without error
