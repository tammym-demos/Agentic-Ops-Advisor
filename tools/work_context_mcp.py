"""Work Context MCP Wrapper — optional MCP server wrapper behind ENABLE_MCP flag.

When ENABLE_MCP=true, this module wraps the work_context_stub as an MCP-style
tool server. When ENABLE_MCP=false (default), the module loads but all handlers
return a disabled message.

NOTE: Full MCP server requires the `mcp` package. This wrapper degrades gracefully
when `mcp` is not installed.
"""

from __future__ import annotations

import json
import os

# Feature flag
_MCP_ENABLED = os.environ.get("ENABLE_MCP", "false").lower() in ("1", "true", "yes")

_DISABLED_RESPONSE = json.dumps(
    {
        "status": "disabled",
        "message": (
            "MCP wrapper is disabled (ENABLE_MCP=false). "
            "Set ENABLE_MCP=true and install the `mcp` package to enable."
        ),
    }
)


def is_mcp_enabled() -> bool:
    """Return True if ENABLE_MCP feature flag is set."""
    return os.environ.get("ENABLE_MCP", "false").lower() in ("1", "true", "yes")


def handle_tool_call(tool_name: str, arguments: dict) -> str:
    """Dispatch an MCP-style tool call to the appropriate stub handler.

    Args:
        tool_name: Name of the tool to call (e.g., "get_work_context", "get_runbook").
        arguments: Dictionary of tool arguments.

    Returns:
        JSON string response from the underlying stub.
    """
    if not is_mcp_enabled():
        return _DISABLED_RESPONSE

    # Lazy import to avoid hard dependency on stub at module load time
    from tools.work_context_stub import get_runbook, get_work_context

    if tool_name == "get_work_context":
        topic = arguments.get("topic")
        return get_work_context(topic=topic)
    elif tool_name == "get_runbook":
        symptom_key = arguments.get("symptom_key", "")
        return get_runbook(symptom_key=symptom_key)
    else:
        return json.dumps({"error": f"Unknown MCP tool: '{tool_name}'"})


def list_tools() -> list[dict]:
    """Return the list of available MCP tools (schema)."""
    if not is_mcp_enabled():
        return []

    return [
        {
            "name": "get_work_context",
            "description": (
                "Return synthetic Work IQ context including change events, decisions, "
                "ownership info, and runbooks. SIMULATION only."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "enum": ["change_events", "decisions", "ownership", "runbooks", "all"],
                        "description": "Which context type to retrieve.",
                    }
                },
            },
        },
        {
            "name": "get_runbook",
            "description": "Return a specific remediation runbook by symptom key. SIMULATION only.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "symptom_key": {
                        "type": "string",
                        "enum": ["gpu_utilization_drop", "latency_spike", "cost_overrun"],
                        "description": "Symptom to look up a runbook for.",
                    }
                },
                "required": ["symptom_key"],
            },
        },
    ]
