"""Agentic Ops Advisor — Work IQ Context Stub.

Returns synthetic "work context" data: change events, decisions, ownership, and
runbooks.

**Important:** We're simulating Work IQ outputs in this demo.  Work IQ is in
public preview and requires Microsoft 365 Copilot licensing + admin consent.

Feature flag: ``ENABLE_WORK_IQ`` (default ``true``).

Each public function wraps its work in an ``execute_tool`` OpenTelemetry span so
tool calls appear as child spans of the top-level ``invoke_agent`` span.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from agent.tracing import execute_tool_span

logger = logging.getLogger(__name__)

_WORK_IQ_DISCLAIMER = (
    "We're simulating Work IQ outputs in this demo. "
    "Work IQ is in public preview and requires Microsoft 365 Copilot licensing + admin consent."
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_work_context(query: str) -> dict[str, Any]:
    """Return synthetic work-context data relevant to *query*.

    Args:
        query: Natural-language query used to select the most relevant stub records.

    Returns:
        A dict with keys ``context_type``, ``records``, ``record_count``,
        ``summary``, and ``disclaimer``.
    """
    if os.getenv("ENABLE_WORK_IQ", "true").lower() != "true":
        return {"summary": "Work IQ disabled via ENABLE_WORK_IQ=false", "record_count": 0, "disclaimer": _WORK_IQ_DISCLAIMER}

    context_type = _infer_context_type(query)
    with execute_tool_span("work_iq", query_type=context_type) as span:
        records = _stub_records(context_type)
        span.set_attribute("tool.record_count", len(records))
        return {
            "context_type": context_type,
            "records": records,
            "record_count": len(records),
            "summary": f"{len(records)} {context_type} record(s) found (synthetic demo data).",
            "disclaimer": _WORK_IQ_DISCLAIMER,
        }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _infer_context_type(query: str) -> str:
    lower = query.lower()
    if any(kw in lower for kw in ("change", "deploy", "release", "rollout")):
        return "change_events"
    if any(kw in lower for kw in ("decision", "approval", "sign-off")):
        return "decisions"
    if any(kw in lower for kw in ("owner", "team", "responsible", "contact")):
        return "ownership"
    if any(kw in lower for kw in ("runbook", "playbook", "procedure", "steps")):
        return "runbooks"
    return "change_events"


def _stub_records(context_type: str) -> list[dict[str, Any]]:
    stubs: dict[str, list[dict[str, Any]]] = {
        "change_events": [
            {
                "id": "CHG-1042",
                "title": "GPU driver upgrade to 550.x on cluster A",
                "author": "ops-team@contoso.com",
                "timestamp": "2025-01-01T22:00:00Z",
                "status": "completed",
            },
            {
                "id": "CHG-1043",
                "title": "Network MTU change on core switches",
                "author": "netops@contoso.com",
                "timestamp": "2025-01-02T01:00:00Z",
                "status": "in_progress",
            },
        ],
        "decisions": [
            {
                "id": "DEC-201",
                "title": "Approved: increase GPU cluster budget by 15%",
                "approver": "director-of-infra@contoso.com",
                "timestamp": "2024-12-20T10:00:00Z",
            }
        ],
        "ownership": [
            {"resource": "gpu-cluster-a", "team": "ML Platform", "contact": "mlplatform@contoso.com"},
            {"resource": "core-network", "team": "NetOps", "contact": "netops@contoso.com"},
        ],
        "runbooks": [
            {
                "id": "RB-07",
                "title": "GPU node OOM recovery procedure",
                "url": "https://wiki.contoso.com/runbooks/gpu-oom",
            }
        ],
    }
    return stubs.get(context_type, stubs["change_events"])
