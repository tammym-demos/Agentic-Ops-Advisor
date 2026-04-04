"""Unit tests for tools/ — sql_telemetry, work_context_stub, action_stub."""

from __future__ import annotations

import os
from unittest.mock import patch

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

import agent.tracing as tracing_mod


def _patch_tracer(exporter: InMemorySpanExporter):
    """Return a context manager that replaces the module tracer with a test one."""
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    test_tracer = provider.get_tracer("test")
    return patch.object(tracing_mod, "get_tracer", return_value=test_tracer)


# ---------------------------------------------------------------------------
# sql_telemetry
# ---------------------------------------------------------------------------

class TestQueryTelemetry:
    def test_returns_dict_with_expected_keys(self):
        from tools.sql_telemetry import query_telemetry

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter):
            result = query_telemetry("show me GPU utilization")

        assert "query_type" in result
        assert "rows" in result
        assert "row_count" in result
        assert "summary" in result
        assert result["query_type"] == "gpu_utilization"
        assert result["row_count"] == len(result["rows"])

    def test_infers_network_query_type(self):
        from tools.sql_telemetry import query_telemetry

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter):
            result = query_telemetry("network latency issues")

        assert result["query_type"] == "network"

    def test_infers_cost_query_type(self):
        from tools.sql_telemetry import query_telemetry

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter):
            result = query_telemetry("what is our cloud spend")

        assert result["query_type"] == "cost"

    def test_infers_incidents_query_type(self):
        from tools.sql_telemetry import query_telemetry

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter):
            result = query_telemetry("recent incidents and alerts")

        assert result["query_type"] == "incidents"

    def test_produces_execute_tool_span(self):
        from tools.sql_telemetry import query_telemetry

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter):
            query_telemetry("GPU utilization")

        spans = exporter.get_finished_spans()
        # The tool itself creates an inner span; the outer span is from query_telemetry
        tool_spans = [s for s in spans if s.name == "execute_tool"]
        assert len(tool_spans) >= 1
        names = {s.attributes.get("tool.name") for s in tool_spans}
        assert "sql_telemetry" in names

    def test_stub_rows_fallback(self):
        from tools import sql_telemetry as st_mod

        rows = st_mod._stub_rows("gpu_utilization")
        assert len(rows) > 0
        assert "node" in rows[0]


# ---------------------------------------------------------------------------
# work_context_stub
# ---------------------------------------------------------------------------

class TestGetWorkContext:
    def test_returns_dict_with_disclaimer(self):
        from tools.work_context_stub import get_work_context

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter), patch.dict(os.environ, {"ENABLE_WORK_IQ": "true"}):
            result = get_work_context("recent deployments")

        assert "disclaimer" in result
        assert "Work IQ" in result["disclaimer"]

    def test_infers_change_events(self):
        from tools.work_context_stub import get_work_context

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter), patch.dict(os.environ, {"ENABLE_WORK_IQ": "true"}):
            result = get_work_context("any recent changes or deployments?")

        assert result["context_type"] == "change_events"

    def test_infers_runbooks(self):
        from tools.work_context_stub import get_work_context

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter), patch.dict(os.environ, {"ENABLE_WORK_IQ": "true"}):
            result = get_work_context("show me the runbook for this")

        assert result["context_type"] == "runbooks"

    def test_disabled_when_flag_off(self):
        from tools.work_context_stub import get_work_context

        with patch.dict(os.environ, {"ENABLE_WORK_IQ": "false"}):
            result = get_work_context("anything")

        assert result["record_count"] == 0

    def test_produces_execute_tool_span(self):
        from tools.work_context_stub import get_work_context

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter), patch.dict(os.environ, {"ENABLE_WORK_IQ": "true"}):
            get_work_context("recent changes")

        spans = exporter.get_finished_spans()
        tool_spans = [s for s in spans if s.name == "execute_tool"]
        assert any(s.attributes.get("tool.name") == "work_iq" for s in tool_spans)


# ---------------------------------------------------------------------------
# action_stub
# ---------------------------------------------------------------------------

class TestProposeAction:
    def test_returns_proposal(self):
        from tools.action_stub import propose_action

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter):
            result = propose_action("scale_up", {"cluster": "gpu-a", "replicas": 4})

        assert "proposal_id" in result
        assert result["action_type"] == "scale_up"
        assert "disclaimer" in result
        assert result["approval_status"] == "pending"

    def test_auto_approved_for_low_risk(self):
        from tools.action_stub import propose_action

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter):
            result = propose_action("restart_service", {"service": "nginx"})

        assert result["approval_status"] == "auto_approved"

    def test_produces_execute_tool_span(self):
        from tools.action_stub import propose_action

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter):
            propose_action("scale_up", {})

        spans = exporter.get_finished_spans()
        tool_spans = [s for s in spans if s.name == "execute_tool"]
        assert any(s.attributes.get("tool.name") == "action_stub" for s in tool_spans)

    def test_list_pending_proposals(self):
        from tools.action_stub import list_pending_proposals

        exporter = InMemorySpanExporter()
        with _patch_tracer(exporter):
            proposals = list_pending_proposals()

        assert isinstance(proposals, list)
        assert len(proposals) >= 1


# ---------------------------------------------------------------------------
# agent.agent — smoke test (no Azure credentials needed)
# ---------------------------------------------------------------------------

class TestInvokeAgent:
    def test_returns_expected_keys(self):
        from agent.agent import invoke_agent

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        test_tracer = provider.get_tracer("test")

        with patch.object(tracing_mod, "get_tracer", return_value=test_tracer):
            with patch.dict(os.environ, {"ENABLE_WORK_IQ": "true"}):
                result = invoke_agent("show me GPU utilization")

        assert "answer" in result
        assert "tool_results" in result
        assert "trace_id" in result
        assert "sql_telemetry" in result["tool_results"]
        assert "work_iq" in result["tool_results"]

    def test_work_iq_skipped_when_disabled(self):
        from agent.agent import invoke_agent

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        test_tracer = provider.get_tracer("test")

        with patch.object(tracing_mod, "get_tracer", return_value=test_tracer):
            with patch.dict(os.environ, {"ENABLE_WORK_IQ": "false"}):
                result = invoke_agent("show GPU stats")

        assert "work_iq" not in result["tool_results"]
