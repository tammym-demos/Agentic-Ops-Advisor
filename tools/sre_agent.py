"""
Agentic Ops Advisor — SRE Agent REST Integration Tool.

Queries Azure SRE Agent via the REST chat API (/api/v2/chat) for
Azure-native diagnostics and triage. This is Phase 2 of the
bidirectional SRE Agent integration.

Feature flag: ENABLE_SRE_AGENT (default: false)
When disabled, returns synthetic SRE Agent responses for demo purposes.

⚠️ The REST chat API is undocumented (discovered via browser DevTools).
Build with synthetic fallback — the API could change without notice.

All data is synthetic — this is a demo tool.
"""

from __future__ import annotations

import logging
import os
from copy import deepcopy
from typing import Any

from agent.config import settings as app_settings

logger = logging.getLogger(__name__)

_DEFAULT_SRE_AGENT_RESOURCE_ID = "59f0a04a-b322-4310-adc9-39ac41e9631e"
_REQUEST_TIMEOUT_SECONDS = 20.0
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_DEMO_DISCLAIMER = (
    "Demo integration: synthetic SRE diagnostics are always available as fallback, and all returned "
    "output should be treated as demonstration data rather than authoritative production telemetry."
)

_SYNTHETIC_RESPONSES: dict[str, dict[str, Any]] = {
    "gpu": {
        "response": (
            "Synthetic SRE triage suggests GPU pressure is localized to gpu-node-07 and gpu-node-12. "
            "Utilization is high, CUDA memory-allocation retries are rising, and one node is trending degraded."
        ),
        "diagnostics": {
            "cluster": "gpu-cluster-prod-east",
            "time_window": "last 15 minutes",
            "gpu_utilization_pct": {"avg": 82.4, "p95": 97.1},
            "node_health": [
                {
                    "node": "gpu-node-07",
                    "state": "degraded",
                    "issue": "elevated ECC memory errors",
                },
                {
                    "node": "gpu-node-12",
                    "state": "warning",
                    "issue": "CUDA OOM retries above baseline",
                },
            ],
            "cuda_errors": [
                {
                    "node": "gpu-node-12",
                    "error": "cudaErrorMemoryAllocation",
                    "count": 14,
                    "last_seen": "2025-01-15T14:27:00Z",
                }
            ],
            "scheduler_backlog_jobs": 6,
            "recommended_actions": [
                "Drain gpu-node-07 and validate the next ECC scrub cycle.",
                "Reduce concurrent training jobs on gpu-node-12 until memory fragmentation clears.",
                "Compare the current driver/CUDA image with the last known-good rollout.",
            ],
        },
    },
    "network": {
        "response": (
            "Synthetic SRE triage points to a network peering regression. East-west latency is elevated, "
            "packet loss is concentrated on one path, and BGP is flapping on the secondary edge."
        ),
        "diagnostics": {
            "region_pair": "eastus2-westus3",
            "time_window": "last 30 minutes",
            "latency_ms": {"avg": 18.7, "p95": 41.2},
            "packet_loss_pct": {"avg": 0.42, "peak": 1.3},
            "bgp_status": {
                "primary_peer": "Established",
                "secondary_peer": "Flapping",
                "route_churn_events": 9,
            },
            "impacted_paths": ["vwan-hub-eastus2", "expressroute-circuit-02"],
            "recommended_actions": [
                "Fail traffic away from the flapping secondary peer.",
                "Review the most recent route-table or peering-policy change before expanding blast radius.",
                "Correlate packet loss with NSG and firewall rule updates in the last hour.",
            ],
        },
    },
    "cost": {
        "response": (
            "Synthetic SRE triage found a cost anomaly driven by bursty GPU consumption and weaker Reserved "
            "Instance coverage overnight. Savings opportunities look real; the bill is just being dramatic."
        ),
        "diagnostics": {
            "time_window": "last 24 hours",
            "total_spend_usd": 12482.31,
            "anomaly_delta_pct": 18.4,
            "largest_drivers": [
                {"service": "gpu-training", "delta_usd": 1320.55},
                {"service": "egress-network", "delta_usd": 244.18},
            ],
            "reserved_instance_coverage_pct": 61.0,
            "spot_eviction_rate_pct": 7.8,
            "recommended_actions": [
                "Shift the next batch window to RI-backed clusters where capacity is available.",
                "Review whether overnight retried GPU jobs can be throttled or checkpointed sooner.",
                "Validate autoscale floors on inference pools that remained warm longer than expected.",
            ],
        },
    },
    "general": {
        "response": (
            "Synthetic SRE triage did not find a single dominant fault domain. Start with the freshest incident "
            "signal, then correlate telemetry, recent change context, and cost anomalies before taking action."
        ),
        "diagnostics": {
            "time_window": "last 60 minutes",
            "active_signals": [
                "No Sev0 pattern detected in the synthetic snapshot.",
                "Two medium-confidence anomalies span GPU utilization and east-west latency.",
                "No governance blocks are simulated for read-only diagnostics queries.",
            ],
            "recommended_actions": [
                "Clarify whether the question is GPU, network, or cost focused.",
                "Ask for the affected region, cluster, or subscription if available.",
                "Correlate with Work IQ-style change context before proposing remediation.",
            ],
        },
    },
}


def _env_truthy(var_name: str, default: bool) -> bool:
    """Parse a boolean environment variable."""
    raw = os.getenv(var_name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_VALUES


def _get_enable_sre_agent() -> bool:
    """Resolve the SRE Agent feature flag from env first, then settings."""
    if os.getenv("ENABLE_SRE_AGENT") is not None:
        return _env_truthy("ENABLE_SRE_AGENT", default=False)
    return app_settings.enable_sre_agent if app_settings is not None else False


def _get_sre_agent_url() -> str | None:
    """Resolve the configured SRE Agent URL, if present."""
    raw = os.getenv("SRE_AGENT_URL")
    if raw is not None and raw.strip():
        return raw.strip()
    return app_settings.sre_agent_url if app_settings is not None else None


def _get_sre_agent_resource_id() -> str:
    """Resolve the SRE Agent resource ID used for token acquisition."""
    raw = os.getenv("SRE_AGENT_RESOURCE_ID")
    if raw is not None and raw.strip():
        return raw.strip()
    if app_settings is not None and app_settings.sre_agent_resource_id:
        return app_settings.sre_agent_resource_id
    return _DEFAULT_SRE_AGENT_RESOURCE_ID


def _build_chat_url(sre_agent_url: str) -> str:
    """Normalize a configured SRE Agent URL to the REST chat endpoint."""
    normalized = sre_agent_url.strip().rstrip("/")
    if normalized.endswith("/api/v2/chat"):
        return normalized
    return f"{normalized}/api/v2/chat"


def _build_scope(resource_id: str) -> str:
    """Return the Azure AD scope for the SRE Agent resource."""
    normalized = resource_id.strip()
    if normalized.endswith("/.default"):
        return normalized
    return f"{normalized}/.default"


def _classify_question(question: str) -> str:
    """Map the question to a synthetic diagnostics category."""
    lowered = question.lower()
    if any(keyword in lowered for keyword in ("gpu", "cuda", "nvidia", "training", "inference", "node")):
        return "gpu"
    if any(keyword in lowered for keyword in ("network", "latency", "packet", "bgp", "dns", "peering")):
        return "network"
    if any(keyword in lowered for keyword in ("cost", "spend", "budget", "ri", "reservation", "finops")):
        return "cost"
    return "general"


def _normalize_question(question: str) -> str:
    """Return a non-empty question string for the tool payload."""
    normalized = str(question or "").strip()
    return normalized or "Provide a general Azure diagnostics summary for the current issue."


def _build_synthetic_result(
    question: str,
    *,
    fallback_reason: str,
    warning: str | None = None,
) -> dict[str, Any]:
    """Return a structured synthetic SRE Agent response."""
    category = _classify_question(question)
    profile = deepcopy(_SYNTHETIC_RESPONSES[category])
    diagnostics = profile["diagnostics"]
    diagnostics["category"] = category
    diagnostics["mode"] = "synthetic-fallback"
    diagnostics["fallback_reason"] = fallback_reason
    if warning:
        diagnostics["warning"] = warning

    response_text = profile["response"]
    if warning:
        response_text = f"{response_text} Note: {warning}"

    return {
        "source": "synthetic",
        "disclaimer": _DEMO_DISCLAIMER,
        "question": question,
        "response": response_text,
        "diagnostics": diagnostics,
    }


def _coerce_text(value: Any) -> str | None:
    """Extract readable text from common API response shapes."""
    if isinstance(value, str):
        text = value.strip()
        return text or None

    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            part = _coerce_text(item)
            if part:
                parts.append(part)
        return "\n".join(parts) if parts else None

    if isinstance(value, dict):
        for key in ("text", "content", "message", "output_text", "answer", "response", "value"):
            part = _coerce_text(value.get(key))
            if part:
                return part

    return None


def _extract_response_text(payload: Any) -> str:
    """Best-effort extraction of assistant text from an undocumented API payload."""
    if isinstance(payload, str):
        return payload.strip() or "Azure SRE Agent returned an empty text response."

    if isinstance(payload, list):
        parts = [part for item in payload if (part := _extract_response_text(item))]
        return "\n".join(parts) if parts else "Azure SRE Agent returned an unrecognized list payload."

    if not isinstance(payload, dict):
        return "Azure SRE Agent returned a response, but the message body could not be normalized."

    messages = payload.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "assistant":
                text = _coerce_text(message.get("content"))
                if text:
                    return text

    choices = payload.get("choices")
    if isinstance(choices, list):
        for choice in reversed(choices):
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict):
                text = _coerce_text(message.get("content"))
                if text:
                    return text
            text = _coerce_text(choice.get("content"))
            if text:
                return text

    for key in ("response", "answer", "output_text"):
        text = _coerce_text(payload.get(key))
        if text:
            return text

    content_text = _coerce_text(payload.get("content"))
    if content_text:
        return content_text

    for key in ("result", "data"):
        nested = payload.get(key)
        if nested is not None:
            nested_text = _extract_response_text(nested)
            if "could not be normalized" not in nested_text and "unrecognized" not in nested_text:
                return nested_text

    return "Azure SRE Agent returned a response, but the message body could not be normalized."


def _extract_live_diagnostics(payload: Any) -> dict[str, Any]:
    """Keep the most useful structured fields from the live API payload."""
    if not isinstance(payload, dict):
        return {"raw_payload": payload}

    extracted: dict[str, Any] = {}
    for key in ("diagnostics", "triage", "context", "citations", "metadata", "observations", "evidence"):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            extracted[key] = value

    if not extracted:
        extracted["raw_payload"] = payload

    return extracted


async def _post_chat_request(*, chat_url: str, access_token: str, question: str) -> Any:
    """POST a chat request to the SRE Agent using httpx with aiohttp fallback."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = {"messages": [{"role": "user", "content": question}]}

    try:
        import httpx  # noqa: PLC0415
    except ImportError:
        import aiohttp  # noqa: PLC0415

        timeout = aiohttp.ClientTimeout(total=_REQUEST_TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(chat_url, json=body, headers=headers) as response:
                response.raise_for_status()
                try:
                    return await response.json(content_type=None)
                except Exception:  # noqa: BLE001
                    return {"response": await response.text()}

    async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(chat_url, json=body, headers=headers)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {"response": response.text}


async def _fetch_live_sre_payload(*, question: str, chat_url: str, scope: str) -> Any:
    """Acquire a token per request and invoke the live SRE Agent REST endpoint."""
    from azure.identity.aio import DefaultAzureCredential  # noqa: PLC0415

    credential = DefaultAzureCredential()
    try:
        token = await credential.get_token(scope)
    finally:
        await credential.close()

    return await _post_chat_request(chat_url=chat_url, access_token=token.token, question=question)


async def query_sre_agent(question: str) -> dict[str, Any]:
    """Query Azure SRE Agent diagnostics, with synthetic fallback for demo reliability."""
    normalized_question = _normalize_question(question)

    if not _get_enable_sre_agent():
        return _build_synthetic_result(
            normalized_question,
            fallback_reason="ENABLE_SRE_AGENT is disabled.",
        )

    sre_agent_url = _get_sre_agent_url()
    if not sre_agent_url:
        return _build_synthetic_result(
            normalized_question,
            fallback_reason="SRE Agent URL is missing while ENABLE_SRE_AGENT is enabled.",
            warning="Live SRE diagnostics are not configured, so the advisor used synthetic fallback data.",
        )

    chat_url = _build_chat_url(sre_agent_url)
    scope = _build_scope(_get_sre_agent_resource_id())

    try:
        payload = await _fetch_live_sre_payload(question=normalized_question, chat_url=chat_url, scope=scope)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SRE Agent REST chat failed; using synthetic fallback: %s", exc)
        return _build_synthetic_result(
            normalized_question,
            fallback_reason="Live SRE Agent request failed or timed out.",
            warning="Azure SRE Agent was unreachable, so the advisor returned synthetic diagnostics instead.",
        )

    diagnostics = {
        "mode": "live-rest-chat",
        "endpoint": chat_url,
        "resource_scope": scope,
        **_extract_live_diagnostics(payload),
    }
    return {
        "source": "live",
        "disclaimer": _DEMO_DISCLAIMER,
        "question": normalized_question,
        "response": _extract_response_text(payload),
        "diagnostics": diagnostics,
    }


ENABLE_SRE_AGENT: bool = _get_enable_sre_agent()

get_sre_diagnostics = query_sre_agent
get_sre_diagnostics.__name__ = "get_sre_diagnostics"
get_sre_diagnostics.__qualname__ = "get_sre_diagnostics"

__all__ = ["ENABLE_SRE_AGENT", "query_sre_agent", "get_sre_diagnostics"]
