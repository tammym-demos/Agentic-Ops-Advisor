"""Agentic Ops Advisor — OpenTelemetry tracing setup and span helpers.

Export destinations (resolved at startup, graceful degradation if unavailable):
- Console exporter (always enabled for local debugging)
- Azure Monitor / Application Insights (when APPLICATIONINSIGHTS_CONNECTION_STRING is set)
- OTLP gRPC endpoint (when OTEL_EXPORTER_OTLP_ENDPOINT is set)

Security consideration
----------------------
``AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED`` controls whether prompt and
completion content is recorded in spans.  Default is ``false`` — leave it OFF in
production and in any demo environment to avoid accidental exposure of sensitive
user queries or model outputs.  Set to ``true`` only in a controlled local/dev
environment.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Generator

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, Status, StatusCode

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_tracer: trace.Tracer | None = None
_initialized: bool = False

SERVICE = "agentic-ops-advisor"


# ---------------------------------------------------------------------------
# Public initialiser
# ---------------------------------------------------------------------------

def setup_tracing(service_name: str = SERVICE) -> trace.Tracer:
    """Configure the global OpenTelemetry tracer provider and return a tracer.

    Safe to call multiple times — subsequent calls return the existing tracer.

    Exporters configured (each is optional / gracefully skipped on error):
    - Console  — always on (useful for local debugging)
    - Azure Monitor — when ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set
    - OTLP gRPC — when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set
    """
    global _tracer, _initialized
    if _initialized:
        return _tracer  # type: ignore[return-value]

    resource = Resource(attributes={SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    # --- Console exporter (always on) ---
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    # --- Azure Monitor / Application Insights ---
    _try_add_azure_monitor(provider)

    # --- OTLP ---
    _try_add_otlp(provider)

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(service_name)
    _initialized = True
    logger.info("OpenTelemetry tracing initialised for service '%s'", service_name)
    return _tracer


def get_tracer() -> trace.Tracer:
    """Return the module-level tracer, initialising it if necessary."""
    if not _initialized:
        return setup_tracing()
    return _tracer  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Span context managers
# ---------------------------------------------------------------------------

@contextmanager
def invoke_agent_span(
    agent_name: str,
    query: str | None = None,
) -> Generator[Span, None, None]:
    """Context manager for a top-level agent invocation span.

    Args:
        agent_name: Logical name of the agent being invoked.
        query: The user query (only recorded when content recording is enabled).
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("invoke_agent") as span:
        span.set_attribute("agent.name", agent_name)
        if _content_recording_enabled() and query:
            span.set_attribute("agent.query", query)
        start = time.monotonic()
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise
        finally:
            span.set_attribute("agent.latency_ms", _elapsed_ms(start))


@contextmanager
def execute_tool_span(
    tool_name: str,
    query_type: str | None = None,
) -> Generator[Span, None, None]:
    """Context manager for a single tool call (child of the current span).

    Args:
        tool_name: Name of the tool being called (e.g. ``sql_telemetry``).
        query_type: Optional sub-category of the query (e.g. ``gpu_utilization``).
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("execute_tool") as span:
        span.set_attribute("tool.name", tool_name)
        if query_type:
            span.set_attribute("tool.query_type", query_type)
        start = time.monotonic()
        try:
            yield span
            span.set_attribute("tool.result_status", "success")
            span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            span.set_attribute("tool.result_status", "error")
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise
        finally:
            span.set_attribute("tool.latency_ms", _elapsed_ms(start))


@contextmanager
def llm_call_span(
    model: str,
    prompt: str | None = None,
) -> Generator[Span, None, None]:
    """Context manager for an LLM API call span.

    Args:
        model: Model deployment name (e.g. ``gpt-4.1``).
        prompt: The prompt text (only recorded when content recording is enabled).
    """
    tracer = get_tracer()
    with tracer.start_as_current_span("llm_call") as span:
        span.set_attribute("llm.model", model)
        if _content_recording_enabled() and prompt:
            span.set_attribute("llm.prompt", prompt)
        start = time.monotonic()
        try:
            yield span
            span.set_status(Status(StatusCode.OK))
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise
        finally:
            span.set_attribute("llm.latency_ms", _elapsed_ms(start))


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _content_recording_enabled() -> bool:
    """Return ``True`` only when the operator has explicitly opted in.

    Default is ``false`` to avoid accidental exposure of sensitive content.
    """
    return os.getenv("AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", "false").lower() == "true"


def _elapsed_ms(start: float) -> float:
    """Milliseconds elapsed since *start* (monotonic)."""
    return round((time.monotonic() - start) * 1000, 2)


def _try_add_azure_monitor(provider: TracerProvider) -> None:
    """Attempt to add the Azure Monitor exporter; log a warning on failure."""
    conn_str = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    if not conn_str:
        logger.debug("APPLICATIONINSIGHTS_CONNECTION_STRING not set — skipping Azure Monitor exporter")
        return
    try:
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter  # type: ignore[import]

        exporter = AzureMonitorTraceExporter(connection_string=conn_str)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("Azure Monitor trace exporter configured")
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to configure Azure Monitor exporter: %s", exc)


def _try_add_otlp(provider: TracerProvider) -> None:
    """Attempt to add an OTLP gRPC exporter; log a warning on failure."""
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if not endpoint:
        logger.debug("OTEL_EXPORTER_OTLP_ENDPOINT not set — skipping OTLP exporter")
        return
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore[import]

        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        logger.info("OTLP trace exporter configured for endpoint '%s'", endpoint)
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to configure OTLP exporter: %s", exc)
