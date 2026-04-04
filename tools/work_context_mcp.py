"""
Agentic Ops Advisor — Work IQ MCP stdio server wrapper.

Wraps tools/work_context_stub.py as an MCP (Model Context Protocol) stdio
server so that any MCP-compatible host can query synthetic Work IQ context
without using the Azure AI Agent Service directly.

Feature flag: ENABLE_MCP environment variable (default: false).
When ENABLE_MCP is not "true" / "1" / "yes" the script exits immediately
with an explanatory message — it will NOT start the server.

Usage (when ENABLE_MCP=true):
    ENABLE_MCP=true python tools/work_context_mcp.py

All data is synthetic — see work_context_stub.py for details.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

# ---------------------------------------------------------------------------
# Feature flag — must be checked before any heavy imports
# ---------------------------------------------------------------------------

_ENABLE_MCP: bool = os.getenv("ENABLE_MCP", "false").lower() in ("true", "1", "yes")

if not _ENABLE_MCP:
    print(
        "MCP server is disabled. Set ENABLE_MCP=true to start the Work IQ MCP server.",
        file=sys.stderr,
    )
    sys.exit(0)

# ---------------------------------------------------------------------------
# Imports (only reached when flag is enabled)
# ---------------------------------------------------------------------------

import mcp.types as types  # noqa: E402
from mcp.server import Server  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402

from tools.work_context_stub import (  # noqa: E402
    get_change_events,
    get_decisions,
    get_full_context,
    get_ownership,
    get_runbooks,
)

# ---------------------------------------------------------------------------
# Server definition
# ---------------------------------------------------------------------------

app = Server("work-context-mcp")

# Tool schemas exposed via MCP
_TOOLS: list[types.Tool] = [
    types.Tool(
        name="get_change_events",
        description=(
            "Return recent change events for a given service/resource "
            "(synthetic Work IQ data — demo only)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service or resource name (e.g. 'gpu-cluster', 'network').",
                }
            },
            "required": ["service"],
        },
    ),
    types.Tool(
        name="get_decisions",
        description=(
            "Return active architectural/operational decisions for a given service "
            "(synthetic Work IQ data — demo only)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service or resource name.",
                }
            },
            "required": ["service"],
        },
    ),
    types.Tool(
        name="get_ownership",
        description=(
            "Return team ownership info (primary contact, on-call rotation) "
            "for a given service (synthetic Work IQ data — demo only)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service or resource name.",
                }
            },
            "required": ["service"],
        },
    ),
    types.Tool(
        name="get_runbooks",
        description=(
            "Return relevant runbook links for a given service "
            "(synthetic Work IQ data — demo only)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service or resource name.",
                }
            },
            "required": ["service"],
        },
    ),
    types.Tool(
        name="get_full_context",
        description=(
            "Return all work context (change events, decisions, ownership, runbooks) "
            "for a given service in a single call (synthetic Work IQ data — demo only)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "service": {
                    "type": "string",
                    "description": "Service or resource name.",
                }
            },
            "required": ["service"],
        },
    ),
]

# ---------------------------------------------------------------------------
# MCP handlers
# ---------------------------------------------------------------------------


@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """Return the list of tools this server exposes."""
    return _TOOLS


@app.call_tool()
async def handle_call_tool(
    name: str,
    arguments: dict,
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Dispatch a tool call to the Work IQ stub and return results as JSON text."""
    service: str = arguments.get("service", "")

    dispatch = {
        "get_change_events": lambda: get_change_events(service),
        "get_decisions": lambda: get_decisions(service),
        "get_ownership": lambda: get_ownership(service),
        "get_runbooks": lambda: get_runbooks(service),
        "get_full_context": lambda: get_full_context(service),
    }

    if name not in dispatch:
        raise ValueError(f"Unknown tool: {name!r}")

    result = dispatch[name]()
    return [types.TextContent(type="text", text=json.dumps(result, indent=2))]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def _main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(_main())
