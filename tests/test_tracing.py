"""Unit tests for agent/tracing.py — OpenTelemetry span helpers."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider() -> tuple[TracerProvider, InMemorySpanExporter]:
    """Create a fresh TracerProvider backed by an InMemorySpanExporter."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


# ---------------------------------------------------------------------------
# setup_tracing
# ---------------------------------------------------------------------------

class TestSetupTracing:
    def test_returns_tracer(self):
        """setup_tracing returns a usable tracer object."""
        import agent.tracing as tracing_mod  # noqa: PLC0415

        # Reset module state so we can call setup_tracing fresh.
        tracing_mod._initialized = False
        tracing_mod._tracer = None

        t = tracing_mod.setup_tracing("test-service")
        assert t is not None

        # Calling again returns the same tracer (idempotent).
        t2 = tracing_mod.setup_tracing("test-service")
        assert t is t2

        # Cleanup: reset so other tests get a fresh provider.
        tracing_mod._initialized = False
        tracing_mod._tracer = None

    def test_get_tracer_auto_initialises(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415

        tracing_mod._initialized = False
        tracing_mod._tracer = None

        t = tracing_mod.get_tracer()
        assert t is not None

        tracing_mod._initialized = False
        tracing_mod._tracer = None


# ---------------------------------------------------------------------------
# _content_recording_enabled
# ---------------------------------------------------------------------------

class TestContentRecording:
    def test_default_is_false(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", None)
            assert tracing_mod._content_recording_enabled() is False

    def test_explicit_false(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415

        with patch.dict(os.environ, {"AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED": "false"}):
            assert tracing_mod._content_recording_enabled() is False

    def test_true_when_opted_in(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415

        with patch.dict(os.environ, {"AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED": "true"}):
            assert tracing_mod._content_recording_enabled() is True

    def test_case_insensitive(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415

        with patch.dict(os.environ, {"AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED": "TRUE"}):
            assert tracing_mod._content_recording_enabled() is True


# ---------------------------------------------------------------------------
# Span context managers — use a dedicated in-memory provider per test
# ---------------------------------------------------------------------------

class TestInvokeAgentSpan:
    def _patched_tracer(self, exporter: InMemorySpanExporter):
        """Return a Tracer backed by the given exporter."""
        provider, _ = _make_provider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        return provider.get_tracer("test")

    def test_span_name_and_attributes(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        test_tracer = provider.get_tracer("test")

        with patch.object(tracing_mod, "get_tracer", return_value=test_tracer):
            with patch.dict(os.environ, {"AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED": "true"}):
                with tracing_mod.invoke_agent_span("my-agent", query="test query"):
                    pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "invoke_agent"
        assert span.attributes["agent.name"] == "my-agent"
        assert span.attributes["agent.query"] == "test query"
        assert "agent.latency_ms" in span.attributes

    def test_query_not_recorded_when_content_off(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        test_tracer = provider.get_tracer("test")

        with patch.object(tracing_mod, "get_tracer", return_value=test_tracer):
            with patch.dict(os.environ, {"AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED": "false"}):
                with tracing_mod.invoke_agent_span("my-agent", query="secret query"):
                    pass

        span = exporter.get_finished_spans()[0]
        assert "agent.query" not in span.attributes

    def test_exception_sets_error_status(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415
        from opentelemetry.trace import StatusCode  # noqa: PLC0415

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        test_tracer = provider.get_tracer("test")

        with patch.object(tracing_mod, "get_tracer", return_value=test_tracer):
            with pytest.raises(RuntimeError):
                with tracing_mod.invoke_agent_span("my-agent"):
                    raise RuntimeError("boom")

        span = exporter.get_finished_spans()[0]
        assert span.status.status_code == StatusCode.ERROR


class TestExecuteToolSpan:
    def test_attributes(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        test_tracer = provider.get_tracer("test")

        with patch.object(tracing_mod, "get_tracer", return_value=test_tracer):
            with tracing_mod.execute_tool_span("sql_telemetry", "gpu_utilization"):
                pass

        span = exporter.get_finished_spans()[0]
        assert span.name == "execute_tool"
        assert span.attributes["tool.name"] == "sql_telemetry"
        assert span.attributes["tool.query_type"] == "gpu_utilization"
        assert span.attributes["tool.result_status"] == "success"
        assert "tool.latency_ms" in span.attributes

    def test_error_status_on_exception(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415
        from opentelemetry.trace import StatusCode  # noqa: PLC0415

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        test_tracer = provider.get_tracer("test")

        with patch.object(tracing_mod, "get_tracer", return_value=test_tracer):
            with pytest.raises(ValueError):
                with tracing_mod.execute_tool_span("sql_telemetry"):
                    raise ValueError("db error")

        span = exporter.get_finished_spans()[0]
        assert span.attributes["tool.result_status"] == "error"
        assert span.status.status_code == StatusCode.ERROR


class TestLlmCallSpan:
    def test_attributes(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        test_tracer = provider.get_tracer("test")

        with patch.object(tracing_mod, "get_tracer", return_value=test_tracer):
            with patch.dict(os.environ, {"AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED": "true"}):
                with tracing_mod.llm_call_span("gpt-4.1", prompt="hello"):
                    pass

        span = exporter.get_finished_spans()[0]
        assert span.name == "llm_call"
        assert span.attributes["llm.model"] == "gpt-4.1"
        assert span.attributes["llm.prompt"] == "hello"
        assert "llm.latency_ms" in span.attributes

    def test_prompt_not_recorded_when_content_off(self):
        import agent.tracing as tracing_mod  # noqa: PLC0415

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        test_tracer = provider.get_tracer("test")

        with patch.object(tracing_mod, "get_tracer", return_value=test_tracer):
            with patch.dict(os.environ, {"AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED": "false"}):
                with tracing_mod.llm_call_span("gpt-4.1", prompt="secret"):
                    pass

        span = exporter.get_finished_spans()[0]
        assert "llm.prompt" not in span.attributes


# ---------------------------------------------------------------------------
# _elapsed_ms
# ---------------------------------------------------------------------------

class TestElapsedMs:
    def test_positive_value(self):
        import time
        import agent.tracing as tracing_mod  # noqa: PLC0415

        start = time.monotonic() - 0.1  # 100 ms ago
        ms = tracing_mod._elapsed_ms(start)
        assert ms >= 90  # allow some scheduling slack
