"""
Agentic Ops Advisor — Work IQ MCP stdio server wrapper.

Wraps tools/work_context_stub.py as an MCP (Model Context Protocol) stdio
server so that any MCP-compatible host can query synthetic Work IQ context
without using the Azure AI Agent Service directly.

All data is synthetic. We're simulating Work IQ outputs in this demo.
Work IQ is in public preview and requires Microsoft 365 Copilot licensing
+ admin consent.

Feature flags:
- ENABLE_MCP controls whether the stdio server starts (default: false)
- MCP_REQUIRE_AUTH controls whether Azure AD token validation is enforced
  for tool calls (default: true)

Usage (when ENABLE_MCP=true):
    ENABLE_MCP=true python tools/work_context_mcp.py
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Feature flags — must be checked before any heavy imports
# ---------------------------------------------------------------------------

_ENABLE_MCP: bool = os.getenv("ENABLE_MCP", "false").lower() in ("true", "1", "yes")
_MCP_REQUIRE_AUTH: bool = os.getenv("MCP_REQUIRE_AUTH", "true").lower() in ("true", "1", "yes")

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

logger = logging.getLogger(__name__)

_DEFAULT_SRE_AGENT_RESOURCE_ID = "59f0a04a-b322-4310-adc9-39ac41e9631e"
_RESERVED_AUTH_ARGUMENT_KEYS = frozenset({"_auth_token", "auth_token", "access_token", "bearer_token", "_meta"})


@dataclass(frozen=True)
class McpAuthConfig:
    """Resolved auth settings for inbound MCP tool-call validation."""

    require_auth: bool
    expected_audience: str
    tenant_id: str | None
    expected_issuer: str | None


# Auth flow notes:
# 1. SRE Agent (or another caller) should acquire Azure AD tokens using the same
#    DefaultAzureCredential-based client pattern used across this repo.
# 2. The stdio transport does not expose HTTP headers, so Phase 1 validates a
#    token injected into reserved tool-call metadata/arguments before dispatch.
# 3. TODO: when this server moves to HTTP/SSE transport, enforce auth from the
#    transport layer and add JWKS-backed signature validation there.

def _get_optional_env(var_name: str) -> str | None:
    """Return a stripped environment variable value, or None when unset."""
    value = os.getenv(var_name, "").strip()
    return value or None


def _load_auth_config() -> McpAuthConfig:
    """Load MCP auth configuration from environment variables."""
    tenant_id = _get_optional_env("MCP_AUTH_TENANT_ID") or _get_optional_env("AZURE_TENANT_ID")
    expected_audience = (
        _get_optional_env("MCP_AUTH_AUDIENCE")
        or _get_optional_env("SRE_AGENT_RESOURCE_ID")
        or _DEFAULT_SRE_AGENT_RESOURCE_ID
    )
    expected_issuer = _get_optional_env("MCP_AUTH_ISSUER")
    if not expected_issuer and tenant_id:
        expected_issuer = f"https://login.microsoftonline.com/{tenant_id}/v2.0"

    return McpAuthConfig(
        require_auth=_MCP_REQUIRE_AUTH,
        expected_audience=expected_audience,
        tenant_id=tenant_id,
        expected_issuer=expected_issuer,
    )


_AUTH_CONFIG = _load_auth_config()


def _extract_bearer_token(
    arguments: Mapping[str, Any],
    *,
    request_meta: Mapping[str, Any] | None = None,
) -> str | None:
    """Extract a bearer token from reserved MCP metadata or arguments."""

    def _normalize(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.lower().startswith("bearer "):
            candidate = candidate[7:].strip()
        return candidate or None

    def _from_mapping(mapping: Mapping[str, Any] | None) -> str | None:
        if not mapping:
            return None

        for key in ("authorization", "Authorization", "bearer_token", "access_token", "auth_token"):
            token = _normalize(mapping.get(key))
            if token:
                return token

        headers = mapping.get("headers")
        if isinstance(headers, Mapping):
            for key in ("authorization", "Authorization"):
                token = _normalize(headers.get(key))
                if token:
                    return token

        return None

    token = _from_mapping(request_meta)
    if token:
        return token

    argument_meta = arguments.get("_meta")
    if isinstance(argument_meta, Mapping):
        token = _from_mapping(argument_meta)
        if token:
            return token

    for key in ("_auth_token", "auth_token", "access_token", "bearer_token"):
        token = _normalize(arguments.get(key))
        if token:
            return token

    return None


def _decode_jwt_claims(token: str) -> dict[str, Any]:
    """Decode JWT claims without logging or returning the raw token."""
    parts = token.split(".")
    if len(parts) < 2:
        raise PermissionError("Azure AD token validation failed: malformed token.")

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload + padding))
    except (binascii.Error, json.JSONDecodeError, ValueError) as exc:
        raise PermissionError("Azure AD token validation failed: malformed token payload.") from exc

    if not isinstance(claims, dict):
        raise PermissionError("Azure AD token validation failed: malformed claims.")

    return claims


def _validate_audience(claims: Mapping[str, Any], config: McpAuthConfig) -> None:
    aud_claim = claims.get("aud")
    audiences = aud_claim if isinstance(aud_claim, list) else [aud_claim]
    normalized_audiences = {aud for aud in audiences if isinstance(aud, str)}
    if config.expected_audience not in normalized_audiences:
        raise PermissionError("Azure AD token validation failed: audience mismatch.")


def _validate_issuer_and_tenant(claims: Mapping[str, Any], config: McpAuthConfig) -> None:
    if not config.tenant_id:
        raise RuntimeError(
            "MCP auth is enabled but AZURE_TENANT_ID (or MCP_AUTH_TENANT_ID) is not configured."
        )

    tenant_claim = claims.get("tid")
    if tenant_claim != config.tenant_id:
        raise PermissionError("Azure AD token validation failed: tenant mismatch.")

    issuer = claims.get("iss")
    if not isinstance(issuer, str) or not issuer.strip():
        raise PermissionError("Azure AD token validation failed: issuer missing.")

    normalized_issuer = issuer.rstrip("/").lower()
    valid_prefixes = (
        f"https://login.microsoftonline.com/{config.tenant_id}".lower(),
        f"https://sts.windows.net/{config.tenant_id}".lower(),
    )
    if not normalized_issuer.startswith(valid_prefixes):
        raise PermissionError("Azure AD token validation failed: issuer tenant mismatch.")

    if config.expected_issuer and normalized_issuer != config.expected_issuer.rstrip("/").lower():
        raise PermissionError("Azure AD token validation failed: issuer mismatch.")


def _validate_token_lifetime(claims: Mapping[str, Any]) -> None:
    """Reject obviously expired or not-yet-valid tokens."""
    now = int(time.time())

    exp = claims.get("exp")
    if isinstance(exp, (int, float)) and now >= int(exp):
        raise PermissionError("Azure AD token validation failed: token expired.")

    nbf = claims.get("nbf")
    if isinstance(nbf, (int, float)) and now < int(nbf):
        raise PermissionError("Azure AD token validation failed: token not yet valid.")


def validate_incoming_token(
    token: str | None,
    *,
    tool_name: str,
    config: McpAuthConfig = _AUTH_CONFIG,
) -> dict[str, Any] | None:
    """Validate Azure AD token claims for an inbound MCP tool call."""
    if not config.require_auth:
        return None

    if not token:
        logger.warning("MCP auth failed for tool '%s': no token supplied.", tool_name)
        raise PermissionError("Azure AD authentication is required for MCP tool calls.")

    claims = _decode_jwt_claims(token)
    _validate_audience(claims, config)
    _validate_issuer_and_tenant(claims, config)
    _validate_token_lifetime(claims)
    return claims


def _validate_tool_call_auth(
    tool_name: str,
    arguments: Mapping[str, Any],
    *,
    request_meta: Mapping[str, Any] | None = None,
) -> None:
    """Validate inbound auth before dispatching a tool call."""
    if not _AUTH_CONFIG.require_auth:
        return

    try:
        token = _extract_bearer_token(arguments, request_meta=request_meta)
        validate_incoming_token(token, tool_name=tool_name)
    except (PermissionError, RuntimeError):
        logger.warning("MCP auth rejected tool '%s'.", tool_name)
        raise


def _sanitize_tool_arguments(arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Strip reserved auth fields before calling the synthetic tool handlers."""
    return {key: value for key, value in arguments.items() if key not in _RESERVED_AUTH_ARGUMENT_KEYS}


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
    arguments: dict[str, Any],
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Dispatch a tool call to the Work IQ stub and return results as JSON text."""
    _validate_tool_call_auth(name, arguments)
    tool_arguments = _sanitize_tool_arguments(arguments)
    service = str(tool_arguments.get("service", ""))

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
