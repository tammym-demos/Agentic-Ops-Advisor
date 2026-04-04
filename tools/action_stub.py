"""Action Stub — proposes changes and simulates approval workflows.

IMPORTANT: This tool never modifies external systems. All actions are simulated.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone


def propose_change(plan: str) -> str:
    """Create a synthetic change request payload for the proposed plan.

    Args:
        plan: Natural-language description of the proposed remediation or change.

    Returns:
        JSON-encoded change request payload with a unique ID, status, and risk assessment.
    """
    request_id = f"CR-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.now(tz=timezone.utc).isoformat()

    # Simple heuristic risk assessment based on keywords
    plan_lower = plan.lower()
    if any(kw in plan_lower for kw in ("rollback", "revert", "downgrade")):
        risk = "medium"
        approval_required = True
    elif any(kw in plan_lower for kw in ("restart", "reload", "refresh")):
        risk = "low"
        approval_required = False
    elif any(kw in plan_lower for kw in ("delete", "drop", "remove", "terminate")):
        risk = "high"
        approval_required = True
    else:
        risk = "low"
        approval_required = False

    payload = {
        "request_id": request_id,
        "ts": now,
        "status": "draft",
        "plan": plan,
        "risk_level": risk,
        "approval_required": approval_required,
        "estimated_impact": _estimate_impact(plan),
        "_simulation": True,
        "_disclaimer": "SIMULATION: This change request is synthetic. No external systems are modified.",
    }
    return json.dumps(payload)


def request_approval(payload: str) -> str:
    """Simulate an approval workflow for a change request.

    Args:
        payload: JSON string of the change request (as returned by propose_change),
                 OR a plain request_id string.

    Returns:
        JSON-encoded approval result with status "pending" or "approved".
    """
    # Accept either a JSON payload or a raw request_id string
    try:
        data = json.loads(payload)
        request_id = data.get("request_id", "UNKNOWN")
        risk_level = data.get("risk_level", "low")
    except (json.JSONDecodeError, AttributeError):
        request_id = str(payload)
        risk_level = "low"

    now = datetime.now(tz=timezone.utc).isoformat()

    # Simulate approval logic: high risk stays pending, others auto-approve
    if risk_level == "high":
        status = "pending"
        reviewer = "ops-lead@contoso.com"
        message = "High-risk change requires human review. Approval request sent to ops-lead."
    else:
        status = "approved"
        reviewer = "auto-governance-bot"
        message = "Change auto-approved by governance policy (risk level: {}).".format(risk_level)

    result = {
        "request_id": request_id,
        "approval_status": status,
        "reviewed_by": reviewer,
        "ts": now,
        "message": message,
        "_simulation": True,
        "_disclaimer": "SIMULATION: This approval workflow is synthetic. No external systems are modified.",
    }
    return json.dumps(result)


def _estimate_impact(plan: str) -> str:
    """Heuristic impact estimate based on plan keywords."""
    plan_lower = plan.lower()
    if any(kw in plan_lower for kw in ("cluster", "all nodes", "global")):
        return "cluster-wide — high blast radius"
    if any(kw in plan_lower for kw in ("node", "single", "one")):
        return "single node — limited blast radius"
    return "service-scoped — moderate blast radius"
