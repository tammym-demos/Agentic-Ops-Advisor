"""
Agentic Ops Advisor — Work IQ Context Stub (synthetic data).

Returns synthetic "work context" data: change events, decisions, ownership,
and runbooks.  This is a demo stub — **all data is synthetic**.

Feature flag: ENABLE_WORK_IQ (default: true)

Disclaimer: Work IQ is in public preview and requires Microsoft 365 Copilot
licensing + admin consent.  This module simulates Work IQ outputs for demo
purposes only.
"""

from __future__ import annotations

import os
from typing import Any

# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

ENABLE_WORK_IQ: bool = os.getenv("ENABLE_WORK_IQ", "true").lower() not in ("false", "0", "no")

# ---------------------------------------------------------------------------
# Synthetic data
# ---------------------------------------------------------------------------

_CHANGE_EVENTS: dict[str, list[dict[str, Any]]] = {
    "gpu-cluster": [
        {
            "id": "CHG-1042",
            "type": "config_change",
            "author": "sre-bot",
            "timestamp": "2025-01-15T14:22:00Z",
            "description": "Increased CUDA memory fraction to 0.95 on gpu-node-07",
            "risk": "medium",
            "approved_by": "alice@contoso.com",
        },
        {
            "id": "CHG-1039",
            "type": "deployment",
            "author": "ci-pipeline",
            "timestamp": "2025-01-15T09:05:00Z",
            "description": "Rolled out training-worker v2.3.1 to gpu-cluster",
            "risk": "low",
            "approved_by": "bob@contoso.com",
        },
    ],
    "network": [
        {
            "id": "CHG-1044",
            "type": "infra_change",
            "author": "netops",
            "timestamp": "2025-01-15T16:00:00Z",
            "description": "BGP route table update — added 10.20.0.0/16 peering",
            "risk": "high",
            "approved_by": "carol@contoso.com",
        }
    ],
    "cost": [
        {
            "id": "CHG-1041",
            "type": "policy_change",
            "author": "finops-bot",
            "timestamp": "2025-01-14T10:00:00Z",
            "description": "Updated Reserved Instance coverage target from 60% to 75%",
            "risk": "low",
            "approved_by": "dave@contoso.com",
        }
    ],
}

_DECISIONS: dict[str, list[dict[str, Any]]] = {
    "gpu-cluster": [
        {
            "id": "DEC-201",
            "summary": "Defer GPU node replacement until Q2 — cost optimisation",
            "owner": "alice@contoso.com",
            "date": "2025-01-10",
            "status": "active",
        }
    ],
    "network": [
        {
            "id": "DEC-198",
            "summary": "Accept elevated p99 latency (<5 ms) during peering migration window",
            "owner": "carol@contoso.com",
            "date": "2025-01-14",
            "status": "active",
        }
    ],
    "cost": [
        {
            "id": "DEC-195",
            "summary": "Increase spot-instance ratio to 40% for batch workloads",
            "owner": "dave@contoso.com",
            "date": "2025-01-12",
            "status": "active",
        }
    ],
}

_OWNERSHIP: dict[str, dict[str, Any]] = {
    "gpu-cluster": {
        "team": "ML Platform",
        "primary": "alice@contoso.com",
        "secondary": "bob@contoso.com",
        "slack": "#ml-platform-ops",
        "oncall_rotation": "PagerDuty: ml-platform",
    },
    "network": {
        "team": "Network Operations",
        "primary": "carol@contoso.com",
        "secondary": "netops-team@contoso.com",
        "slack": "#netops",
        "oncall_rotation": "PagerDuty: netops",
    },
    "cost": {
        "team": "FinOps",
        "primary": "dave@contoso.com",
        "secondary": "finops@contoso.com",
        "slack": "#finops",
        "oncall_rotation": "PagerDuty: finops",
    },
    "default": {
        "team": "SRE",
        "primary": "sre-oncall@contoso.com",
        "secondary": "sre-team@contoso.com",
        "slack": "#sre",
        "oncall_rotation": "PagerDuty: sre-primary",
    },
}

_RUNBOOKS: dict[str, list[dict[str, str]]] = {
    "gpu-cluster": [
        {
            "title": "GPU Node OOM Remediation",
            "url": "https://wiki.contoso.com/runbooks/gpu-oom",
            "last_updated": "2025-01-08",
        },
        {
            "title": "CUDA Driver Upgrade Procedure",
            "url": "https://wiki.contoso.com/runbooks/cuda-upgrade",
            "last_updated": "2024-12-15",
        },
    ],
    "network": [
        {
            "title": "BGP Peering Failover",
            "url": "https://wiki.contoso.com/runbooks/bgp-failover",
            "last_updated": "2025-01-13",
        }
    ],
    "cost": [
        {
            "title": "RI Coverage Optimisation",
            "url": "https://wiki.contoso.com/runbooks/ri-coverage",
            "last_updated": "2024-11-20",
        }
    ],
}

# ---------------------------------------------------------------------------
# Cluster / host name → service category mapping (fuzzy matching fallback)
# ---------------------------------------------------------------------------

_CLUSTER_TO_SERVICE: dict[str, str] = {
    "prod-east": "gpu-cluster",
    "prod-west": "gpu-cluster",
    "gpu": "gpu-cluster",
    "train": "gpu-cluster",
    "inference": "gpu-cluster",
    "wan": "network",
    "cdn": "network",
    "edge": "network",
    "latency": "network",
    "finops": "cost",
    "billing": "cost",
    "spend": "cost",
    "budget": "cost",
}

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _service_key(service: str) -> str:
    """Normalise a service name to a known key or 'default'."""
    s = service.lower().strip()
    # Exact match first
    if s in _CHANGE_EVENTS:
        return s
    # Substring match against known keys
    for key in _CHANGE_EVENTS:
        if key in s or s in key:
            return key
    # Cluster / host name pattern mapping
    for pattern, svc in _CLUSTER_TO_SERVICE.items():
        if pattern in s:
            return svc
    return "default"


def get_change_events(service: str) -> list[dict[str, Any]]:
    """Return recent change events for *service* (synthetic data)."""
    if not ENABLE_WORK_IQ:
        return []
    return _CHANGE_EVENTS.get(_service_key(service), [])


def get_decisions(service: str) -> list[dict[str, Any]]:
    """Return active architectural/operational decisions for *service*."""
    if not ENABLE_WORK_IQ:
        return []
    return _DECISIONS.get(_service_key(service), [])


def get_ownership(service: str) -> dict[str, Any]:
    """Return team ownership info for *service*."""
    if not ENABLE_WORK_IQ:
        return {}
    key = _service_key(service)
    return _OWNERSHIP.get(key, _OWNERSHIP["default"])


def get_runbooks(service: str) -> list[dict[str, str]]:
    """Return relevant runbook links for *service*."""
    if not ENABLE_WORK_IQ:
        return []
    return _RUNBOOKS.get(_service_key(service), [])


def get_full_context(service: str) -> dict[str, Any]:
    """Return all work context for *service* in a single call."""
    return {
        "service": service,
        "disclaimer": (
            "Simulating Work IQ outputs. Work IQ is in public preview and requires "
            "Microsoft 365 Copilot licensing + admin consent."
        ),
        "change_events": get_change_events(service),
        "decisions": get_decisions(service),
        "ownership": get_ownership(service),
        "runbooks": get_runbooks(service),
    }


# Alias used by agent/agent.py — the Azure AI Agent Service registers
# functions by __name__, so the tool appears as "get_work_context" to the LLM.
get_work_context = get_full_context
get_work_context.__name__ = "get_work_context"
get_work_context.__qualname__ = "get_work_context"


# ---------------------------------------------------------------------------
# Azure AI Agent Service tool schema
# ---------------------------------------------------------------------------

TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_work_context",
        "strict": False,
        "description": (
            "Retrieve synthetic work context (change events, decisions, ownership, runbooks) "
            "for a service category. All data is synthetic for demo purposes. "
            "Simulates Work IQ outputs — Work IQ is in public preview and requires "
            "Microsoft 365 Copilot licensing + admin consent."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": (
                        "Service category — not a cluster or host name. "
                        "Common cluster names (e.g. 'prod-east-01') are "
                        "resolved automatically."
                    ),
                    "enum": ["gpu-cluster", "network", "cost"],
                },
            },
            "required": ["service"],
            "additionalProperties": False,
        },
    },
}


def get_tool_definition() -> dict[str, Any]:
    """Return the Azure AI Agent Service-compatible tool definition for this tool."""
    return TOOL_SCHEMA


TOOL_DEFINITIONS: list[dict[str, Any]] = [TOOL_SCHEMA]

TOOL_CALLABLES: dict[str, Any] = {
    "get_work_context": get_work_context,
}
