"""Agentic Ops Advisor — Agent orchestration layer.

This module provides the :func:`invoke_agent` entry-point that wires together
the three tool surfaces (SQL telemetry, Work IQ context, action stub) and the
LLM call, wrapping each step in OpenTelemetry spans for end-to-end traceability.

All data produced by this agent is **synthetic** and for demonstration purposes
only.  No real infrastructure data is accessed.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from agent.tracing import invoke_agent_span, llm_call_span, setup_tracing

logger = logging.getLogger(__name__)

AGENT_NAME = "agentic-ops-advisor"
DEFAULT_MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")


def invoke_agent(query: str, *, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    """Run the Agentic Ops Advisor for a single user query.

    The function is intentionally synchronous and self-contained so it can be
    exercised from the CLI, notebooks, and integration tests without a running
    Azure AI Foundry project connection.

    Args:
        query: The natural-language operator query.
        model: Azure OpenAI deployment name used for the LLM call.

    Returns:
        A dict containing ``answer``, ``tool_results``, and ``trace_id``.
    """
    setup_tracing()

    with invoke_agent_span(AGENT_NAME, query=query) as agent_span:
        tool_results: dict[str, Any] = {}

        # --- SQL Telemetry ---
        tool_results["sql_telemetry"] = _run_sql_telemetry(query)

        # --- Work IQ Context (feature-flagged) ---
        if os.getenv("ENABLE_WORK_IQ", "true").lower() == "true":
            tool_results["work_iq"] = _run_work_iq(query)

        # --- LLM synthesis ---
        answer = _run_llm(query, tool_results, model=model)

        agent_span.set_attribute("agent.tool_count", len(tool_results))

        return {
            "answer": answer,
            "tool_results": tool_results,
            "trace_id": _span_trace_id(agent_span),
        }


# ---------------------------------------------------------------------------
# Internal helpers — each wraps a tool call in an execute_tool span
# ---------------------------------------------------------------------------

def _run_sql_telemetry(query: str) -> dict[str, Any]:
    """Invoke the SQL telemetry tool and return its result.

    The tool itself creates an ``execute_tool`` span internally, so no
    additional wrapper is needed here.
    """
    from tools.sql_telemetry import query_telemetry  # local import to keep module testable

    return query_telemetry(query)


def _run_work_iq(query: str) -> dict[str, Any]:
    """Invoke the Work IQ context stub and return its result.

    The tool itself creates an ``execute_tool`` span internally, so no
    additional wrapper is needed here.
    """
    from tools.work_context_stub import get_work_context  # local import

    return get_work_context(query)


def _run_llm(query: str, tool_results: dict[str, Any], *, model: str) -> str:
    """Placeholder LLM synthesis step, wrapped in an llm_call span."""
    with llm_call_span(model, prompt=query):
        # In a full implementation this would call Azure OpenAI via the
        # azure-ai-projects SDK.  Here we return a stub answer so the module
        # can be exercised without live Azure credentials.
        summary = "; ".join(
            f"{k}: {v.get('summary', 'ok')}" for k, v in tool_results.items() if isinstance(v, dict)
        )
        return f"[Demo] Synthesised answer for '{query}'. Tool context: {summary or 'none'}."


def _span_trace_id(span: Any) -> str:
    """Return the trace ID of *span* as a hex string, or empty string."""
    try:
        ctx = span.get_span_context()
        return format(ctx.trace_id, "032x")
    except Exception:  # pragma: no cover
        return ""
