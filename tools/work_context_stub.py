"""Work IQ Context Stub — simulated Work IQ context tool.

Returns synthetic change events, decisions, ownership, and runbook data from
``data/synthetic_context.json``.  Controlled by the ``ENABLE_WORK_IQ``
environment variable (default: ``true``).

Every response includes the mandatory Work IQ disclaimer.

Note: We're simulating Work IQ outputs in this demo.
Work IQ is in public preview and requires Microsoft 365 Copilot licensing
+ admin consent.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mandatory disclaimer — must appear in every response
# ---------------------------------------------------------------------------
WORK_IQ_DISCLAIMER = (
    "Note: This is a Work IQ pattern simulation using synthetic data. "
    "Work IQ is in public preview and requires Microsoft 365 Copilot "
    "licensing + admin consent for tenant data access."
)

# ---------------------------------------------------------------------------
# Synthetic data loading
# ---------------------------------------------------------------------------
_DATA_PATH = Path(__file__).parent.parent / "data" / "synthetic_context.json"
_context_cache: dict[str, Any] | None = None


def _load_context() -> dict[str, Any]:
    """Load synthetic context data, using a module-level cache."""
    global _context_cache
    if _context_cache is None:
        with _DATA_PATH.open(encoding="utf-8") as fh:
            _context_cache = json.load(fh)
    return _context_cache


def _clear_context_cache() -> None:
    """Clear the in-memory context cache (useful in tests)."""
    global _context_cache
    _context_cache = None


# ---------------------------------------------------------------------------
# Feature-flag check
# ---------------------------------------------------------------------------
def _work_iq_enabled() -> bool:
    """Return True when the ENABLE_WORK_IQ feature flag is truthy."""
    raw = os.environ.get("ENABLE_WORK_IQ", "true").strip().lower()
    return raw not in {"false", "0", "no", "off"}


def _disabled_response() -> dict[str, Any]:
    return {
        "status": "disabled",
        "message": (
            "Work IQ context tool is disabled for this demo configuration. "
            "Set ENABLE_WORK_IQ=true to enable it."
        ),
        "disclaimer": WORK_IQ_DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Helper — ISO-8601 timestamp parsing
# ---------------------------------------------------------------------------
def _parse_ts(ts: str) -> datetime:
    """Parse an ISO-8601 timestamp string into an aware UTC datetime."""
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# ---------------------------------------------------------------------------
# Public tool function
# ---------------------------------------------------------------------------
def get_work_context(
    query_type: str,
    service: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    topic_keywords: str | None = None,
) -> dict[str, Any]:
    """Return synthetic Work IQ context relevant to an operator query.

    Args:
        query_type: One of ``"change_events"``, ``"ownership"``,
            ``"runbook"``, or ``"decisions"``.
        service: Optional service/cluster name to filter results.
        start_time: Optional ISO-8601 start of time range (inclusive).
        end_time: Optional ISO-8601 end of time range (inclusive).
        topic_keywords: Optional comma-separated keywords to filter decisions
            or runbooks by tag / title (e.g. ``"capacity,gpu"``).

    Returns:
        A dict containing the matching context records and the mandatory
        Work IQ disclaimer.
    """
    if not _work_iq_enabled():
        return _disabled_response()

    try:
        context = _load_context()
    except FileNotFoundError:
        logger.error("synthetic_context.json not found at %s", _DATA_PATH)
        return {
            "status": "error",
            "message": "Synthetic context data file not found.",
            "disclaimer": WORK_IQ_DISCLAIMER,
        }

    qt = query_type.strip().lower()

    _handlers = {
        "change_events": lambda: _query_change_events(context, service, start_time, end_time),
        "ownership": lambda: _query_ownership(context, service),
        "runbook": lambda: _query_runbook(context, service, topic_keywords),
        "decisions": lambda: _query_decisions(context, service, start_time, end_time, topic_keywords),
    }

    if qt not in _handlers:
        return {
            "status": "error",
            "message": (
                f"Unknown query_type '{query_type}'. "
                "Valid values: change_events, ownership, runbook, decisions."
            ),
            "disclaimer": WORK_IQ_DISCLAIMER,
        }

    results = _handlers[qt]()

    return {
        "status": "ok",
        "query_type": qt,
        "filters": {
            "service": service,
            "start_time": start_time,
            "end_time": end_time,
            "topic_keywords": topic_keywords,
        },
        "results": results,
        "result_count": len(results),
        "disclaimer": WORK_IQ_DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------
def _query_change_events(
    context: dict[str, Any],
    service: str | None,
    start_time: str | None,
    end_time: str | None,
) -> list[dict[str, Any]]:
    events = context.get("change_events", [])

    start_dt = _parse_ts(start_time) if start_time else None
    end_dt = _parse_ts(end_time) if end_time else None

    results = []
    for evt in events:
        if service and service.lower() not in evt.get("service", "").lower():
            continue
        if start_dt or end_dt:
            evt_dt = _parse_ts(evt["timestamp"])
            if start_dt and evt_dt < start_dt:
                continue
            if end_dt and evt_dt > end_dt:
                continue
        results.append(evt)

    return results


def _query_ownership(
    context: dict[str, Any],
    service: str | None,
) -> list[dict[str, Any]]:
    ownership = context.get("ownership", [])

    if not service:
        return ownership

    svc_lower = service.lower()
    return [o for o in ownership if svc_lower in o.get("service", "").lower()]


def _query_runbook(
    context: dict[str, Any],
    service: str | None,
    topic_keywords: str | None,
) -> list[dict[str, Any]]:
    runbooks = context.get("runbooks", [])

    keywords = [k.strip().lower() for k in topic_keywords.split(",")] if topic_keywords else []

    results = []
    for rb in runbooks:
        if service and service.lower() not in rb.get("service", "").lower():
            continue
        if keywords:
            rb_tags = [t.lower() for t in rb.get("tags", [])]
            rb_title = rb.get("title", "").lower()
            if not any(kw in rb_tags or kw in rb_title for kw in keywords):
                continue
        results.append(rb)

    return results


def _query_decisions(
    context: dict[str, Any],
    service: str | None,
    start_time: str | None,
    end_time: str | None,
    topic_keywords: str | None,
) -> list[dict[str, Any]]:
    decisions = context.get("decisions", [])

    start_dt = _parse_ts(start_time) if start_time else None
    end_dt = _parse_ts(end_time) if end_time else None
    keywords = [k.strip().lower() for k in topic_keywords.split(",")] if topic_keywords else []

    results = []
    for dec in decisions:
        if service and service.lower() not in dec.get("service", "").lower():
            continue
        if start_dt or end_dt:
            dec_dt = _parse_ts(dec["timestamp"])
            if start_dt and dec_dt < start_dt:
                continue
            if end_dt and dec_dt > end_dt:
                continue
        if keywords:
            dec_tags = [t.lower() for t in dec.get("tags", [])]
            dec_topic = dec.get("topic", "").lower()
            dec_summary = dec.get("summary", "").lower()
            if not any(kw in dec_tags or kw in dec_topic or kw in dec_summary for kw in keywords):
                continue
        results.append(dec)

    return results


# ---------------------------------------------------------------------------
# Azure AI Agent Service — function definition schema
# ---------------------------------------------------------------------------
TOOL_DEFINITION: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_work_context",
        "description": (
            "Retrieve synthetic Work IQ context including change events, "
            "service ownership, runbooks, and architectural decisions. "
            "Use this tool to answer questions like 'What changed around time X?', "
            "'Who owns service Y?', 'What is the runbook for Z?', or "
            "'What decisions were made about capacity?'. "
            "Always cite the disclaimer returned by this tool in your response."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["change_events", "ownership", "runbook", "decisions"],
                    "description": (
                        "Type of work context to retrieve. "
                        "Use 'change_events' for deployment/config history, "
                        "'ownership' for team/contact information, "
                        "'runbook' for incident remediation steps, "
                        "'decisions' for architectural/capacity decisions."
                    ),
                },
                "service": {
                    "type": "string",
                    "description": (
                        "Optional service or cluster name to filter results "
                        "(e.g. 'gpu-scheduler', 'inference-api', 'network-fabric')."
                    ),
                },
                "start_time": {
                    "type": "string",
                    "description": (
                        "Optional ISO-8601 start of time range, inclusive "
                        "(e.g. '2025-03-28T00:00:00Z'). "
                        "Used with change_events and decisions."
                    ),
                },
                "end_time": {
                    "type": "string",
                    "description": (
                        "Optional ISO-8601 end of time range, inclusive "
                        "(e.g. '2025-03-30T23:59:59Z'). "
                        "Used with change_events and decisions."
                    ),
                },
                "topic_keywords": {
                    "type": "string",
                    "description": (
                        "Optional comma-separated keywords to filter decisions or runbooks "
                        "(e.g. 'capacity,gpu' or 'latency,p99'). "
                        "Matches against tags and title/summary text."
                    ),
                },
            },
            "required": ["query_type"],
        },
    },
}
