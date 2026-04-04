"""Agentic Ops Advisor — Action Stub.

Proposes infrastructure changes and simulates approval workflows.
**This tool never modifies external systems.**

Each public function wraps its work in an ``execute_tool`` OpenTelemetry span so
tool calls appear as child spans of the top-level ``invoke_agent`` span.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from agent.tracing import execute_tool_span

logger = logging.getLogger(__name__)

_DISCLAIMER = "This action stub simulates an approval workflow. No external systems are modified."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def propose_action(action_type: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """Propose an infrastructure change and simulate an approval workflow.

    Args:
        action_type: Type of action (e.g. ``scale_up``, ``restart_service``).
        parameters: Action-specific parameters dict.

    Returns:
        A dict with ``proposal_id``, ``action_type``, ``parameters``,
        ``approval_status``, ``message``, and ``disclaimer``.
    """
    with execute_tool_span("action_stub", query_type=action_type) as span:
        proposal_id = str(uuid.uuid4())[:8].upper()
        approval_status = _simulate_approval(action_type)
        span.set_attribute("tool.proposal_id", proposal_id)
        span.set_attribute("tool.approval_status", approval_status)
        result = {
            "proposal_id": proposal_id,
            "action_type": action_type,
            "parameters": parameters,
            "approval_status": approval_status,
            "message": _approval_message(action_type, approval_status, proposal_id),
            "disclaimer": _DISCLAIMER,
        }
        logger.info("Action proposed: %s (proposal=%s, status=%s)", action_type, proposal_id, approval_status)
        return result


def list_pending_proposals() -> list[dict[str, Any]]:
    """Return a synthetic list of pending approval proposals."""
    with execute_tool_span("action_stub", query_type="list_pending"):
        return [
            {
                "proposal_id": "AB12CD",
                "action_type": "scale_up",
                "parameters": {"cluster": "gpu-cluster-a", "replicas": 4},
                "approval_status": "pending",
                "disclaimer": _DISCLAIMER,
            }
        ]


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _simulate_approval(action_type: str) -> str:
    """Return a simulated approval status based on *action_type*."""
    low_risk = {"restart_service", "refresh_config", "scale_down"}
    if action_type in low_risk:
        return "auto_approved"
    return "pending"


def _approval_message(action_type: str, approval_status: str, proposal_id: str) -> str:
    if approval_status == "auto_approved":
        return f"Action '{action_type}' auto-approved (proposal {proposal_id}). Simulated execution complete."
    return (
        f"Action '{action_type}' requires human approval (proposal {proposal_id}). "
        "An approval request has been queued (simulated)."
    )
