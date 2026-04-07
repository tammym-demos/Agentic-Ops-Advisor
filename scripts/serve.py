#!/usr/bin/env python3
"""Hosted agent server for Azure AI Foundry Agent Service.

Implements the Foundry Responses API on port 8088.

Usage:
    python scripts/serve.py

What it does:
    1. Loads system prompt from agent/system_prompt.md
    2. Seeds the SQLite database if needed
    3. Starts aiohttp server on port 8088:
       - POST /responses — Foundry Responses API endpoint
       - GET /health — Health check
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
import sys
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

def _call_tool(name: str, arguments: str) -> str:
    """Dispatch a function-call from the LLM to the local tool surface."""
    from tools.sql_telemetry import TOOL_CALLABLES as SQL_CALLABLES
    from tools.action_stub import propose_change, request_approval
    from tools.work_context_stub import get_full_context, ENABLE_WORK_IQ

    # Build full tool callables dict
    tool_callables = dict(SQL_CALLABLES)
    tool_callables["propose_change"] = propose_change
    tool_callables["request_approval"] = request_approval
    if ENABLE_WORK_IQ:
        # Map get_work_context to get_full_context for compatibility
        tool_callables["get_work_context"] = get_full_context

    if name not in tool_callables:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        kwargs = json.loads(arguments) if arguments else {}
        result = tool_callables[name](**kwargs)
        # If result is already a string (from action_stub/work_context), return it
        if isinstance(result, str):
            return result
        return json.dumps(result)
    except (json.JSONDecodeError, TypeError, ValueError, FileNotFoundError, OSError) as exc:
        return json.dumps({"error": str(exc)})

# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

def _run_agent_conversation(messages: list[dict], endpoint: str, deployment: str, api_version: str) -> dict:
    """Run agent loop with Azure OpenAI function-calling.
    
    Returns:
        {"content": str, "error": str | None}
    """
    try:
        from openai import AzureOpenAI
    except ImportError:
        return {"content": "", "error": "openai package not found. Install with: pip install openai"}

    from tools.sql_telemetry import TOOL_DEFINITIONS
    from tools.action_stub import ACTION_STUB_TOOL_DEFINITIONS
    from tools.work_context_stub import ENABLE_WORK_IQ

    # Build full tool definitions
    tool_definitions = list(TOOL_DEFINITIONS) + list(ACTION_STUB_TOOL_DEFINITIONS)
    if ENABLE_WORK_IQ:
        # Add work_context tool definition
        work_context_def = {
            "type": "function",
            "function": {
                "name": "get_work_context",
                "description": (
                    "Retrieve synthetic work context (change events, decisions, ownership, runbooks) "
                    "for a specific service. All data is synthetic for demo purposes."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {
                            "type": "string",
                            "description": "Service name (e.g., 'gpu-cluster', 'network', 'cost').",
                        }
                    },
                    "required": ["service"],
                },
            },
        }
        tool_definitions.append(work_context_def)

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_version=api_version,
        # Uses DefaultAzureCredential / AZURE_OPENAI_API_KEY from env automatically
    )

    # Prepend system prompt
    conversation: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}] + messages

    max_tool_rounds = 8
    for _round in range(max_tool_rounds):
        try:
            response = client.chat.completions.create(
                model=deployment,
                messages=conversation,  # type: ignore[arg-type]
                tools=tool_definitions,  # type: ignore[arg-type]
                tool_choice="auto",
                temperature=0.2,
            )
        except Exception as exc:
            logger.exception("Azure OpenAI error")
            return {"content": "", "error": str(exc)}

        choice = response.choices[0]
        message = choice.message
        conversation.append(message.model_dump(exclude_unset=True))

        if choice.finish_reason == "tool_calls" and message.tool_calls:
            for tc in message.tool_calls:
                tool_result = _call_tool(tc.function.name, tc.function.arguments)
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": tool_result,
                    }
                )
        else:
            # Final answer
            answer = message.content or "(no response)"
            return {"content": answer, "error": None}

    return {"content": "", "error": "Reached max tool-call rounds — check your query."}

# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------

async def _responses_handler(request) -> object:
    """Handle POST /responses (Foundry Responses API)."""
    from aiohttp import web

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {"error": "Invalid JSON in request body"},
            status=400,
        )

    # Extract input (can be a string or a messages array)
    input_data = body.get("input")
    if isinstance(input_data, str):
        messages = [{"role": "user", "content": input_data}]
    elif isinstance(input_data, dict) and "messages" in input_data:
        messages = input_data["messages"]
    else:
        return web.json_response(
            {"error": "Invalid input format. Expected string or {messages: [...]}"},
            status=400,
        )

    # Get Azure OpenAI config
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1").strip()
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview").strip()

    if not endpoint:
        return web.json_response(
            {
                "id": f"resp_{uuid.uuid4().hex}",
                "object": "response",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": "AZURE_OPENAI_ENDPOINT not configured. Agent cannot run."
                    }
                ],
                "status": "failed",
            },
            status=500,
        )

    logger.debug(f"Processing conversation with {len(messages)} messages")

    # Run agent loop
    result = _run_agent_conversation(messages, endpoint, deployment, api_version)

    response_id = f"resp_{uuid.uuid4().hex}"

    if result["error"]:
        return web.json_response({
            "id": response_id,
            "object": "response",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": f"Error: {result['error']}"
                }
            ],
            "status": "failed",
        })

    return web.json_response({
        "id": response_id,
        "object": "response",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": result["content"],
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

    # Ensure DB exists before starting server
    try:
        _ensure_db()
    except (OSError, sqlite3.Error, ImportError) as exc:
        logger.error(f"Failed to set up database: {exc}")
        sys.exit(1)

    port = int(os.environ.get("PORT", "8088"))
    
    logger.info(f"Server starting on http://0.0.0.0:{port}")
    logger.info("Endpoints: POST /responses, GET /health, GET /")

    from aiohttp import web
    import asyncio

    app = asyncio.run(_init_app())
    web.run_app(app, host="0.0.0.0", port=port, print=None, access_log=logger)


if __name__ == "__main__":
    main()
