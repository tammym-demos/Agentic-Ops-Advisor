#!/usr/bin/env python3
"""Hosted agent server for Azure AI Foundry Agent Service.

Implements the Foundry Responses API on port 8088 (default).

Usage:
    python scripts/serve.py

What it does:
    1. Loads system prompt from agent/system_prompt.md
    2. Seeds the SQLite database if needed
    3. Starts aiohttp server on port 8088 (override with PORT env var):
       - POST /responses — Foundry Responses API endpoint
       - GET /health — Health check
       - GET /readiness — Readiness check
       - GET / — Serve static/index.html or JSON welcome
    4. Handles agent loop with Azure OpenAI function-calling
    5. Stateless — each request is independent

Environment variables:
    - AZURE_OPENAI_ENDPOINT (required for agent mode)
    - AZURE_OPENAI_DEPLOYMENT (default: gpt-4.1)
    - AZURE_OPENAI_API_VERSION (default: 2025-01-01-preview)
    - ENABLE_WORK_IQ (default: true)
    - DB_MODE (default: sqlite)
    - MODE (if "cli", runs run_local.py's main() instead)

NOTE: All data is synthetic.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import asyncio
import sys
import time
import uuid
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Bootstrap: add repo root to sys.path before any local imports
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ---------------------------------------------------------------------------
# Force local DB mode BEFORE importing tool modules
# ---------------------------------------------------------------------------
os.environ.setdefault("DB_MODE", "sqlite")
os.environ.setdefault("ENABLE_WORK_IQ", "true")
os.environ.setdefault("ENABLE_MCP", "false")

# Load .env (best-effort; ignored if file absent)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_REPO_ROOT, ".env"))
except ImportError:
    pass  # python-dotenv not installed — skip

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Load system prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT_PATH = os.path.join(_REPO_ROOT, "agent", "system_prompt.md")
_SYSTEM_PROMPT = ""

try:
    with open(_SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
        _SYSTEM_PROMPT = f.read().strip()
except FileNotFoundError:
    logger.warning(f"System prompt not found at {_SYSTEM_PROMPT_PATH}. Agent will have no system instructions.")

# ---------------------------------------------------------------------------
# DB bootstrap
# ---------------------------------------------------------------------------

def _ensure_db() -> None:
    """Seed the SQLite database if it doesn't already exist."""
    from data.seed_telemetry import DEFAULT_DB_PATH, create_schema, seed_connection

    if os.path.exists(DEFAULT_DB_PATH):
        return

    logger.info("Database not found — seeding synthetic data …")
    os.makedirs(os.path.dirname(DEFAULT_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    try:
        create_schema(conn)
        counts = seed_connection(conn)
        for table, n in counts.items():
            logger.info(f"  {table}: {n:,} rows")
    finally:
        conn.close()
    logger.info("Database ready.")

# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

async def _call_tool(name: str, arguments: str) -> str:
    """Dispatch a function-call from the LLM to the local tool surface."""
    from tools.sql_telemetry import query_telemetry as async_query_telemetry
    from tools.action_stub import propose_change, request_approval
    from tools.work_context_stub import get_full_context, ENABLE_WORK_IQ

    # Async tool callables (query_telemetry is natively async)
    async_callables: dict = {"query_telemetry": async_query_telemetry}

    # Sync tool callables
    sync_callables: dict = {
        "propose_change": propose_change,
        "request_approval": request_approval,
    }
    if ENABLE_WORK_IQ:
        sync_callables["get_work_context"] = get_full_context

    try:
        kwargs = json.loads(arguments) if arguments else {}

        if name in async_callables:
            result = await async_callables[name](**kwargs)
        elif name in sync_callables:
            result = sync_callables[name](**kwargs)
        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

        return result if isinstance(result, str) else json.dumps(result)
    except Exception as exc:
        logger.exception("Tool %s failed", name)
        return json.dumps({"error": str(exc)})

# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

async def _run_agent_conversation(messages: list[dict], endpoint: str, deployment: str, api_version: str) -> dict:
    """Run agent loop with Azure OpenAI function-calling (async).
    
    Returns:
        {"content": str, "error": str | None}
    
    Timeouts:
        - Per-request: 30s (OpenAI SDK httpx timeout)
        - Overall loop: 85s (must finish before Foundry's 100s gateway timeout)
    """
    try:
        from openai import AzureOpenAI
    except ImportError:
        return {"content": "", "error": "openai package not found. Install with: pip install openai"}

    from tools.sql_telemetry import TOOL_DEFINITIONS
    from tools.action_stub import ACTION_STUB_TOOL_DEFINITIONS
    from tools.work_context_stub import ENABLE_WORK_IQ, TOOL_DEFINITIONS as WORK_CTX_TOOL_DEFINITIONS

    # Build full tool definitions
    tool_definitions = list(TOOL_DEFINITIONS) + list(ACTION_STUB_TOOL_DEFINITIONS)
    if ENABLE_WORK_IQ:
        tool_definitions.extend(WORK_CTX_TOOL_DEFINITIONS)

    # Foundry gateway has a 100s HttpClient.Timeout. We must respond before that.
    LOOP_TIMEOUT_S = 85
    REQUEST_TIMEOUT_S = 30.0
    loop_start = time.monotonic()

    # --- Auth: API key first, managed identity fallback ---
    # API key is preferred because DefaultAzureCredential's managed identity
    # probe can hang for ~2 min when no MI is configured (IMDS timeout).
    api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
    if api_key:
        logger.info("Using API key auth for Azure OpenAI")
        client = AzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            timeout=REQUEST_TIMEOUT_S,
            max_retries=1,
        )
    else:
        try:
            from azure.identity import DefaultAzureCredential, get_bearer_token_provider

            logger.info("No API key — trying managed identity auth")
            credential = DefaultAzureCredential()
            token_provider = get_bearer_token_provider(
                credential, "https://cognitiveservices.azure.com/.default"
            )
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                azure_ad_token_provider=token_provider,
                api_version=api_version,
                timeout=REQUEST_TIMEOUT_S,
                max_retries=1,
            )
        except Exception as cred_exc:
            logger.error("Auth failed — no API key and managed identity unavailable: %s", cred_exc)
            return {"content": "", "error": f"Auth failed (no API key or managed identity): {cred_exc}"}

    # Prepend system prompt
    conversation: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}] + messages

    max_tool_rounds = 4
    for _round in range(max_tool_rounds):
        elapsed = time.monotonic() - loop_start
        remaining = LOOP_TIMEOUT_S - elapsed
        if remaining < 5:
            logger.warning("Agent loop timeout — %.1fs elapsed, aborting", elapsed)
            return {"content": "", "error": f"Agent loop timeout ({elapsed:.0f}s elapsed, {LOOP_TIMEOUT_S}s limit)"}

        try:
            call_start = time.monotonic()
            logger.info("OpenAI call round %d (%.1fs elapsed, %.1fs remaining)", _round + 1, elapsed, remaining)
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=deployment,
                messages=conversation,  # type: ignore[arg-type]
                tools=tool_definitions,  # type: ignore[arg-type]
                tool_choice="auto",
                temperature=0.2,
            )
            call_duration = time.monotonic() - call_start
            logger.info("OpenAI call round %d completed in %.1fs", _round + 1, call_duration)
        except Exception as exc:
            call_duration = time.monotonic() - call_start
            logger.exception("Azure OpenAI error after %.1fs", call_duration)
            return {"content": "", "error": f"OpenAI call failed after {call_duration:.0f}s: {exc}"}

        choice = response.choices[0]
        message = choice.message
        conversation.append(message.model_dump(exclude_unset=True))

        if choice.finish_reason == "tool_calls" and message.tool_calls:
            tool_names = [tc.function.name for tc in message.tool_calls]
            logger.info("Tool calls requested: %s", tool_names)
            for tc in message.tool_calls:
                tool_start = time.monotonic()
                tool_result = await _call_tool(tc.function.name, tc.function.arguments)
                logger.info("Tool %s completed in %.1fs", tc.function.name, time.monotonic() - tool_start)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    }
                )
        else:
            # Final answer
            total = time.monotonic() - loop_start
            answer = message.content or "(no response)"
            logger.info("Agent loop complete: %d rounds, %.1fs total", _round + 1, total)
            return {"content": answer, "error": None}

    total = time.monotonic() - loop_start
    return {"content": "", "error": f"Reached max tool-call rounds ({max_tool_rounds}) in {total:.0f}s — check your query."}

# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

async def _responses_handler(request) -> object:
    """Handle POST /responses (Foundry Responses API)."""
    from aiohttp import web

    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1").strip()

    def _error_response(text: str, *, http_status: int = 200) -> object:
        """Build a Responses API error envelope."""
        return web.json_response({
            "id": f"resp_{uuid.uuid4().hex}",
            "object": "response",
            "created_at": int(time.time()),
            "model": deployment,
            "output": [
                {
                    "type": "message",
                    "id": f"msg_{uuid.uuid4().hex}",
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text, "annotations": []}],
                }
            ],
            "status": "completed",
        }, status=http_status)

    try:
        return await _handle_responses_inner(request, deployment, _error_response)
    except Exception as exc:
        logger.exception("Unhandled error in /responses handler")
        return _error_response(f"Internal error: {exc}")


async def _handle_responses_inner(request, deployment: str, _error_response) -> object:
    """Inner handler for POST /responses — separated for top-level error catch."""
    from aiohttp import web

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"error": "Invalid JSON in request body"},
            status=400,
        )

    logger.info("POST /responses — keys: %s", list(body.keys()))

    # Extract input (can be a string, list, or messages dict)
    input_data = body.get("input")
    if isinstance(input_data, str):
        messages = [{"role": "user", "content": input_data}]
    elif isinstance(input_data, list):
        # Foundry Responses API v1 sends input as array of typed items.
        # We only convert "message" items; function_call / function_call_output
        # and other internal types are skipped (our container handles tools).
        messages = []
        for item in input_data:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type", "message")
            # Skip non-message items (function_call, function_call_output, etc.)
            if item_type not in ("message",):
                continue
            role = item.get("role", "user")
            content = item.get("content", "")
            # Content may be a string or array of content parts
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if p.get("type") in ("input_text", "text")]
                content = " ".join(text_parts)
            if not content:
                continue
            messages.append({"role": role, "content": content})
    elif isinstance(input_data, dict) and "messages" in input_data:
        messages = input_data["messages"]
    else:
        return _error_response(
            "Invalid input format. Send {\"input\": \"your question\"}.",
            http_status=400,
        )

    if not messages:
        return _error_response("No user messages found in the input.")

    # Get Azure OpenAI config
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview").strip()

    if not endpoint:
        return _error_response(
            "AZURE_OPENAI_ENDPOINT not configured. Agent cannot run.",
            http_status=500,
        )

    logger.info("Processing conversation: %d messages, endpoint=%s, model=%s",
                len(messages), endpoint[:40] + "…" if len(endpoint) > 40 else endpoint, deployment)

    # Run agent loop
    result = await _run_agent_conversation(messages, endpoint, deployment, api_version)

    response_id = f"resp_{uuid.uuid4().hex}"

    if result["error"]:
        logger.warning("Agent loop error: %s", result["error"][:200])
        return _error_response(f"Error: {result['error']}")

    return web.json_response({
        "id": response_id,
        "object": "response",
        "created_at": int(time.time()),
        "model": deployment,
        "output": [
            {
                "type": "message",
                "id": f"msg_{uuid.uuid4().hex}",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": result["content"], "annotations": []}],
            }
        ],
        "status": "completed",
    })


async def _health_handler(request) -> object:
    """Handle GET /health requests."""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        import tomli as tomllib  # fallback for Python 3.10

    # Read version from pyproject.toml
    version = "unknown"
    try:
        pyproject_path = os.path.join(_REPO_ROOT, "pyproject.toml")
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            version = data.get("project", {}).get("version", "unknown")
    except (FileNotFoundError, KeyError):
        pass

    from aiohttp import web

    return web.json_response({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": version,
    })


async def _readiness_handler(request) -> object:
    """Handle GET /readiness requests — used by Foundry for container probes."""
    from aiohttp import web

    version = os.environ.get("CONTAINER_IMAGE_TAG", "dev")
    return web.json_response({
        "status": "ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": version,
    })


async def _root_handler(request) -> object:
    """Handle GET / requests — serve static/index.html or JSON welcome."""
    from aiohttp import web

    static_index = os.path.join(_REPO_ROOT, "static", "index.html")
    if os.path.exists(static_index):
        return web.FileResponse(static_index)

    return web.json_response({
        "name": "Agentic Ops Advisor",
        "description": "Hosted agent for Azure AI Foundry Agent Service",
        "endpoints": {
            "POST /responses": "Foundry Responses API",
            "GET /health": "Health check",
            "GET /": "This message or static/index.html if present",
        },
        "disclaimer": "All data is synthetic — for demo purposes only.",
    })

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

async def _init_app() -> object:
    """Initialize aiohttp application."""
    from aiohttp import web
    from aiohttp_cors import setup as cors_setup, ResourceOptions

    app = web.Application()
    
    # Add CORS for browser-based chat UI
    cors = cors_setup(app, defaults={
        "*": ResourceOptions(
            allow_credentials=True,
            expose_headers="*",
            allow_headers="*",
            allow_methods=["GET", "POST", "OPTIONS"],
        )
    })

    # Add routes
    app.router.add_post("/responses", _responses_handler)
    app.router.add_get("/health", _health_handler)
    app.router.add_get("/readiness", _readiness_handler)
    app.router.add_get("/", _root_handler)

    # Enable CORS on all routes
    for route in list(app.router.routes()):
        cors.add(route)

    return app

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    # Check if MODE=cli (run run_local.py instead)
    mode = os.environ.get("MODE", "").lower()
    if mode == "cli":
        from scripts.run_local import main as run_local_main
        run_local_main()
        return

    logger.info("Starting Agentic Ops Advisor hosted agent server …")

    # --- Startup diagnostics ---
    logger.info("AZURE_OPENAI_ENDPOINT: %s", os.environ.get("AZURE_OPENAI_ENDPOINT", "(not set)"))
    logger.info("AZURE_OPENAI_API_KEY: %s", "set" if os.environ.get("AZURE_OPENAI_API_KEY") else "not set")
    logger.info("AZURE_CLIENT_ID: %s", "set" if os.environ.get("AZURE_CLIENT_ID") else "not set")
    # Skip managed identity probe at startup when API key is available.
    # DefaultAzureCredential().get_token() probes IMDS at 169.254.169.254,
    # which hangs ~2 min when no MI is configured — blocking server startup.
    if not os.environ.get("AZURE_OPENAI_API_KEY"):
        try:
            from azure.identity import DefaultAzureCredential
            cred = DefaultAzureCredential()
            cred.get_token("https://cognitiveservices.azure.com/.default")
            logger.info("Managed identity auth: SUCCESS")
        except Exception as diag_exc:
            logger.warning("Managed identity auth: FAILED (%s)", diag_exc)
    else:
        logger.info("API key available — skipping managed identity probe at startup")

    # Ensure DB exists before starting server
    try:
        _ensure_db()
    except (OSError, sqlite3.Error, ImportError) as exc:
        logger.error(f"Failed to set up database: {exc}")
        sys.exit(1)

    # Prefer SERVE_PORT; fall back to PORT for backward compat; default 8088.
    # Guard: Foundry sidecar occupies 8080 — never bind there.
    port = int(os.environ.get("SERVE_PORT") or os.environ.get("PORT") or "8088")
    if port == 8080:
        logger.warning("Port 8080 is reserved by Foundry sidecar — overriding to 8088")
        port = 8088

    logger.info(f"Server starting on http://0.0.0.0:{port}")
    logger.info("Endpoints: POST /responses, GET /health, GET /")

    from aiohttp import web

    app = asyncio.run(_init_app())
    web.run_app(app, host="0.0.0.0", port=port, print=None, access_log=logger)


if __name__ == "__main__":
    main()
