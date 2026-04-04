"""Work IQ Context Stub — simulates Work IQ outputs with synthetic data.

NOTE: We're simulating Work IQ outputs in this demo. Work IQ is in public preview
and requires Microsoft 365 Copilot licensing + admin consent.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------------
# Synthetic data corpus
# ---------------------------------------------------------------------------

_now = datetime.now(tz=timezone.utc)

_CHANGE_EVENTS = [
    {
        "id": "ce-001",
        "ts": (_now - timedelta(hours=26)).isoformat(),
        "type": "rollout",
        "title": "GPU driver update v525.89 deployed to gpu-cluster-a",
        "author": "ops-bot@contoso.com",
        "status": "completed",
        "risk": "medium",
        "services_affected": ["gpu-cluster-a"],
    },
    {
        "id": "ce-002",
        "ts": (_now - timedelta(hours=50)).isoformat(),
        "type": "policy_change",
        "title": "Network QoS policy updated — eastus2 priority queue rebalanced",
        "author": "network-team@contoso.com",
        "status": "completed",
        "risk": "low",
        "services_affected": ["network", "eastus2"],
    },
    {
        "id": "ce-003",
        "ts": (_now - timedelta(hours=12)).isoformat(),
        "type": "approval",
        "title": "Scale-down of gpu-cluster-b approved for off-peak window",
        "author": "capacity-mgr@contoso.com",
        "status": "pending",
        "risk": "low",
        "services_affected": ["gpu-cluster-b"],
    },
]

_DECISIONS = [
    {
        "id": "dec-001",
        "ts": (_now - timedelta(days=3)).isoformat(),
        "meeting": "AI Factory Planning",
        "outcome": "Agreed to defer GPU cluster expansion to Q3; monitor utilization weekly.",
        "owner": "alice.chen@contoso.com",
        "tags": ["gpu", "capacity", "planning"],
    },
    {
        "id": "dec-002",
        "ts": (_now - timedelta(days=7)).isoformat(),
        "meeting": "Ops Review",
        "outcome": "Network latency SLA set at 50ms P99 for eastus2; alerts configured.",
        "owner": "bob.smith@contoso.com",
        "tags": ["network", "sla", "alerting"],
    },
]

_OWNERSHIP = {
    "gpu-cluster-a": {
        "team": "AI Infrastructure",
        "lead": "alice.chen@contoso.com",
        "escalation": "cto-on-call@contoso.com",
        "runbook_url": "https://wiki.contoso.com/runbooks/gpu-cluster-a",
    },
    "gpu-cluster-b": {
        "team": "AI Infrastructure",
        "lead": "alice.chen@contoso.com",
        "escalation": "cto-on-call@contoso.com",
        "runbook_url": "https://wiki.contoso.com/runbooks/gpu-cluster-b",
    },
    "network": {
        "team": "Network Ops",
        "lead": "bob.smith@contoso.com",
        "escalation": "netops-oncall@contoso.com",
        "runbook_url": "https://wiki.contoso.com/runbooks/network",
    },
    "cost-tracker": {
        "team": "FinOps",
        "lead": "carol.jones@contoso.com",
        "escalation": "finops-lead@contoso.com",
        "runbook_url": "https://wiki.contoso.com/runbooks/cost-tracker",
    },
}

_RUNBOOKS = {
    "gpu_utilization_drop": {
        "id": "rb-001",
        "title": "GPU Utilization Drop — Diagnosis & Recovery",
        "steps": [
            "1. Check nvidia-smi on affected nodes for driver/process errors.",
            "2. Review recent change events for driver updates or config changes.",
            "3. Inspect workload queue — confirm jobs are submitting correctly.",
            "4. If driver issue: roll back to previous driver version.",
            "5. If workload issue: restart scheduler service and re-queue jobs.",
            "6. Notify AI Infrastructure team lead within 30 min of diagnosis.",
        ],
        "estimated_resolution_min": 45,
        "severity_threshold": "high",
    },
    "latency_spike": {
        "id": "rb-002",
        "title": "Network Latency Spike — Diagnosis & Recovery",
        "steps": [
            "1. Check network device health (switches, NICs) in affected site.",
            "2. Review recent policy/QoS changes on the affected path.",
            "3. Run traceroute to identify bottleneck hop.",
            "4. If QoS misconfiguration: revert to previous policy snapshot.",
            "5. If hardware issue: engage Network Ops on-call immediately.",
            "6. Update incident ticket with RCA within 2h.",
        ],
        "estimated_resolution_min": 30,
        "severity_threshold": "medium",
    },
    "cost_overrun": {
        "id": "rb-003",
        "title": "Token Cost Overrun — Response Playbook",
        "steps": [
            "1. Identify cluster/model driving excess token usage.",
            "2. Check for runaway batch jobs or misconfigured max_tokens.",
            "3. Apply emergency throttle via API gateway rate limits.",
            "4. Notify FinOps lead and request budget exception if needed.",
            "5. Post-incident: review token budgets and set alerts.",
        ],
        "estimated_resolution_min": 20,
        "severity_threshold": "low",
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _check_enabled() -> dict | None:
    """Return disabled-message dict if Work IQ is disabled, else None."""
    enabled = os.environ.get("ENABLE_WORK_IQ", "true").lower() in ("1", "true", "yes")
    if not enabled:
        return {
            "status": "disabled",
            "message": (
                "Work IQ context is disabled (ENABLE_WORK_IQ=false). "
                "Enable it to access synthetic change-context data."
            ),
        }
    return None


def get_work_context(topic: str | None = None) -> str:
    """Return synthetic work context as a JSON string.

    Args:
        topic: Optional filter — one of "change_events", "decisions", "ownership", "runbooks".
               If None or "all", returns all context types.

    Returns:
        JSON-encoded work context payload with a simulation disclaimer.
    """
    disabled = _check_enabled()
    if disabled:
        return json.dumps(disabled)

    disclaimer = (
        "SIMULATION DISCLAIMER: We're simulating Work IQ outputs in this demo. "
        "Work IQ is in public preview and requires Microsoft 365 Copilot licensing + admin consent."
    )

    if topic == "change_events":
        payload: dict = {"change_events": _CHANGE_EVENTS}
    elif topic == "decisions":
        payload = {"decisions": _DECISIONS}
    elif topic == "ownership":
        payload = {"ownership": _OWNERSHIP}
    elif topic == "runbooks":
        payload = {"runbooks": _RUNBOOKS}
    else:
        # Return all context
        payload = {
            "change_events": _CHANGE_EVENTS,
            "decisions": _DECISIONS,
            "ownership": _OWNERSHIP,
            "runbooks": _RUNBOOKS,
        }

    payload["_disclaimer"] = disclaimer
    return json.dumps(payload)


def get_runbook(symptom_key: str) -> str:
    """Return a specific runbook by symptom key as JSON.

    Args:
        symptom_key: One of "gpu_utilization_drop", "latency_spike", "cost_overrun".

    Returns:
        JSON-encoded runbook or error message.
    """
    disabled = _check_enabled()
    if disabled:
        return json.dumps(disabled)

    if symptom_key not in _RUNBOOKS:
        return json.dumps(
            {
                "error": f"Unknown symptom_key '{symptom_key}'. "
                f"Available: {list(_RUNBOOKS)}"
            }
        )

    result = dict(_RUNBOOKS[symptom_key])
    result["_disclaimer"] = (
        "SIMULATION: Synthetic runbook data — not a real operational playbook."
    )
    return json.dumps(result)
