"""Action stub tool — safe, simulated change proposal and approval workflow.

All responses are purely simulated. This tool NEVER modifies external systems.

Disclaimer: This is a demo. All change requests, approvals, and risk assessments
are synthetic and do not reflect real infrastructure state.
"""

import json
import uuid

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Keywords used to infer risk level from a plan description
_HIGH_RISK_KEYWORDS = {"delete", "drop", "terminate", "destroy", "remove", "wipe", "purge", "reset"}
_MEDIUM_RISK_KEYWORDS = {"restart", "reboot", "update", "upgrade", "migrate", "redeploy", "scale"}

# Approval state cycle for demo purposes — cycles through states based on
# the last hex digit of the change request UUID so results are deterministic
# per request id yet varied across different ids.
_APPROVAL_STATES = ["pending", "approved", "rejected"]


def _infer_risk_level(plan: str) -> str:
    """Return 'high', 'medium', or 'low' based on keywords in the plan."""
    lower = plan.lower()
    if any(kw in lower for kw in _HIGH_RISK_KEYWORDS):
        return "high"
    if any(kw in lower for kw in _MEDIUM_RISK_KEYWORDS):
        return "medium"
    return "low"


def _infer_affected_services(plan: str) -> list[str]:
    """Return a synthetic list of affected services inferred from the plan."""
    lower = plan.lower()
    services: list[str] = []
    if any(kw in lower for kw in ("gpu", "compute", "vm", "node")):
        services.append("compute-cluster")
    if any(kw in lower for kw in ("network", "vnet", "subnet", "nsg", "firewall")):
        services.append("network")
    if any(kw in lower for kw in ("db", "database", "sql", "postgres", "cosmos")):
        services.append("database")
    if any(kw in lower for kw in ("storage", "blob", "bucket", "disk")):
        services.append("storage")
    if any(kw in lower for kw in ("app", "service", "api", "function", "web")):
        services.append("app-service")
    if not services:
        services.append("general-infrastructure")
    return services


def _build_rollback_plan(risk_level: str, affected_services: list[str]) -> str:
    """Return a synthetic rollback plan string."""
    services_str = ", ".join(affected_services)
    if risk_level == "high":
        return (
            f"Immediately revert {services_str} to last known-good snapshot. "
            "Engage on-call SRE. Open P1 incident bridge."
        )
    if risk_level == "medium":
        return f"Re-deploy previous configuration for {services_str}. Monitor for 30 minutes post-rollback."
    return f"Undo configuration change on {services_str} and verify metrics return to baseline."


def _build_estimated_duration(risk_level: str) -> str:
    """Return a synthetic estimated duration string."""
    return {"high": "60–120 minutes", "medium": "20–45 minutes", "low": "5–15 minutes"}.get(risk_level, "unknown")


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


def propose_change(plan: str) -> str:
    """Propose a simulated infrastructure change based on the operator's plan.

    Args:
        plan: Free-text description of the intended change.

    Returns:
        JSON string containing a structured change request payload.
        When risk_level is 'high', the payload includes a human_approval_gate
        field advising the operator to wait for explicit human approval.
    """
    change_id = str(uuid.uuid4())
    risk_level = _infer_risk_level(plan)
    affected_services = _infer_affected_services(plan)

    payload: dict = {
        "id": change_id,
        "description": plan.strip(),
        "risk_level": risk_level,
        "affected_services": affected_services,
        "rollback_plan": _build_rollback_plan(risk_level, affected_services),
        "estimated_duration": _build_estimated_duration(risk_level),
        "status": "proposed",
        "disclaimer": (
            "This is a simulated change request. No external systems have been modified."
        ),
    }

    if risk_level == "high":
        payload["human_approval_gate"] = {
            "required": True,
            "message": (
                "⚠️  HIGH RISK — human approval required before proceeding. "
                "Use request_approval(change_request_id) to check approval status, "
                "or escalate to your on-call SRE before executing this change."
            ),
        }

    return json.dumps(payload, indent=2)


def request_approval(change_request_id: str) -> str:
    """Return a simulated approval status for the given change request.

    Approval state cycles deterministically through 'pending', 'approved',
    and 'rejected' based on the change_request_id, so different IDs return
    different states for demo variety without randomness.

    Args:
        change_request_id: The UUID returned by propose_change.

    Returns:
        JSON string with approval status and supporting metadata.
    """
    # Use sum of last 8 hex digits of the UUID to pick a cycle index.
    clean_id = change_request_id.replace("-", "")
    try:
        cycle_index = int(clean_id[-1], 16) % len(_APPROVAL_STATES)
    except (ValueError, IndexError):
        cycle_index = 0

    status = _APPROVAL_STATES[cycle_index]

    result: dict = {
        "change_request_id": change_request_id,
        "approval_status": status,
        "reviewed_by": "simulated-approver@contoso.com",
        "disclaimer": (
            "This is a simulated approval workflow. No real approval system was contacted."
        ),
    }

    if status == "pending":
        result["message"] = "Change request is awaiting review. Check back shortly or escalate if urgent."
    elif status == "approved":
        result["message"] = "Change request approved. Proceed with caution and monitor closely."
    else:  # rejected
        result["message"] = "Change request rejected. Review the risk assessment and revise the plan."

    return json.dumps(result, indent=2)


# ---------------------------------------------------------------------------
# Azure AI Agent Service tool schemas
# ---------------------------------------------------------------------------

ACTION_STUB_TOOL_DEFINITIONS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "propose_change",
            "strict": False,
            "description": (
                "Propose a simulated infrastructure change based on an operator's plan. "
                "Returns a structured change request payload including risk level, "
                "affected services, rollback plan, and estimated duration. "
                "When risk is high, a human approval gate is included. "
                "NEVER modifies external systems — purely simulated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "plan": {
                        "type": "string",
                        "description": "Free-text description of the intended infrastructure change.",
                    }
                },
                "required": ["plan"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_approval",
            "strict": False,
            "description": (
                "Return a simulated approval status for a previously proposed change request. "
                "Cycles through 'pending', 'approved', and 'rejected' states for demo purposes. "
                "NEVER contacts a real approval system — purely simulated."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "change_request_id": {
                        "type": "string",
                        "description": "The UUID of the change request returned by propose_change.",
                    }
                },
                "required": ["change_request_id"],
                "additionalProperties": False,
            },
        },
    },
]
