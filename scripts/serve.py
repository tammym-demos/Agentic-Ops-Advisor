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

# Module-level readiness flag — set after background init completes
_ready_event = asyncio.Event()
_startup_clock: float = 0.0

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

    # --- Auth: managed identity first (production), API key fallback (local dev) ---
    # In production (Foundry hosted container), the project's system-assigned
    # managed identity is available via DefaultAzureCredential.  API key auth
    # is disabled by policy on the Azure OpenAI resource, so MI must be tried
    # first.  The API key path is kept only for local dev scenarios where MI
    # is unavailable.  Note: DefaultAzureCredential() is intentionally created
    # per-request (not at module level) to avoid startup hangs when IMDS is
    # unreachable.
    client = None
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        logger.info("Trying managed identity auth for Azure OpenAI")
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
        logger.warning("Managed identity auth unavailable: %s", cred_exc)
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        if api_key:
            logger.info("Falling back to API key auth for Azure OpenAI")
            client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=api_key,
                api_version=api_version,
                timeout=REQUEST_TIMEOUT_S,
                max_retries=1,
            )
        else:
            logger.error("Auth failed — managed identity unavailable and no API key set: %s", cred_exc)
            return {"content": "", "error": f"Auth failed (no managed identity or API key): {cred_exc}"}

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

    if not _ready_event.is_set():
        return _error_response("Agent is starting up. Please retry in a few seconds.")

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

    input_data = body.get("input")
    messages = _parse_input_to_messages(input_data)

    if messages is None:
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
    if not _ready_event.is_set():
        return web.json_response({
            "status": "starting",
            "message": "Agent is initializing...",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": version,
        }, status=503)
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

async def _on_startup(app) -> None:
    """Startup hook: launch background init task (DB seed + readiness)."""

    async def _do_init() -> None:
        t0 = time.monotonic()
        logger.info("[STARTUP] mi_probe=skipped reason=deferred_to_request_time")
        try:
            await asyncio.to_thread(_ensure_db)
            logger.info(
                "[STARTUP] phase=db_seed status=complete elapsed=%.1fs",
                time.monotonic() - t0,
            )
        except Exception as exc:
            logger.error(
                "[STARTUP] phase=db_seed status=failed error=%s elapsed=%.1fs",
                exc,
                time.monotonic() - t0,
            )
        _ready_event.set()
        logger.info(
            "[STARTUP] ready=true total_elapsed=%.1fs",
            time.monotonic() - _startup_clock,
        )

    asyncio.create_task(_do_init())


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

    # Register async startup hook — fires when app is served, not when instantiated
    app.on_startup.append(_on_startup)

    return app

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _resolve_port() -> int:
    """Determine listen port. Foundry adapter uses DEFAULT_AD_PORT; we also check SERVE_PORT/PORT."""
    port = int(
        os.environ.get("SERVE_PORT")
        or os.environ.get("DEFAULT_AD_PORT")
        or os.environ.get("PORT")
        or "8088"
    )
    if port == 8080:
        logger.warning("Port 8080 is reserved by Foundry sidecar — overriding to 8088")
        port = 8088
    return port


def _log_startup_diagnostics() -> None:
    logger.info("Starting Agentic Ops Advisor hosted agent server …")
    logger.info("AZURE_OPENAI_ENDPOINT: %s", os.environ.get("AZURE_OPENAI_ENDPOINT", "(not set)"))
    logger.info("AZURE_OPENAI_API_KEY: %s", "set" if os.environ.get("AZURE_OPENAI_API_KEY") else "not set")
    logger.info("AZURE_CLIENT_ID: %s", "set" if os.environ.get("AZURE_CLIENT_ID") else "not set")


def _parse_input_to_messages(input_data) -> list[dict] | None:
    """Parse Foundry Responses API input into OpenAI-style messages.

    Returns None if input format is invalid.
    """
    if isinstance(input_data, str):
        return [{"role": "user", "content": input_data}]
    elif isinstance(input_data, list):
        messages = []
        for item in input_data:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type", "message")
            if item_type not in ("message",):
                continue
            role = item.get("role", "user")
            content = item.get("content", "")
            if isinstance(content, list):
                text_parts = [p.get("text", "") for p in content if p.get("type") in ("input_text", "text")]
                content = " ".join(text_parts)
            if not content:
                continue
            messages.append({"role": role, "content": content})
        return messages
    elif isinstance(input_data, dict) and "messages" in input_data:
        return input_data["messages"]
    return None


# ---------------------------------------------------------------------------
# Foundry hosting adapter (production path)
# ---------------------------------------------------------------------------

def _run_with_foundry_adapter(port: int) -> None:
    """Start the server using the official Foundry FoundryCBAgent adapter.

    This is the production path for Azure AI Foundry hosted agents.
    Uses uvicorn + Starlette with proper sidecar integration, tracing,
    CORS, and graceful shutdown.
    """
    import datetime as dt

    # ── Disable App Insights BEFORE importing the adapter ──
    # The adapter's __init__.py calls config_logging() at import time,
    # which sets up AzureMonitorLogExporter.  If the App Insights
    # connection string is invalid the exporter floods stderr with
    # "Non-retryable server side error: Bad Request" on a background
    # thread, which can starve I/O and interfere with SSE streaming.
    # Disable it here; re-enable once telemetry config is validated.
    os.environ["ENABLE_APPLICATION_INSIGHTS_LOGGER"] = "false"

    from azure.ai.agentserver.core import FoundryCBAgent, AgentRunContext
    from azure.ai.agentserver.core.models import Response as FoundryResponse
    from azure.ai.agentserver.core.models.projects import (
        ItemContentOutputText,
        ResponseCompletedEvent,
        ResponseContentPartAddedEvent,
        ResponseContentPartDoneEvent,
        ResponseCreatedEvent,
        ResponseInProgressEvent,
        ResponseOutputItemAddedEvent,
        ResponseOutputItemDoneEvent,
        ResponseTextDeltaEvent,
        ResponseTextDoneEvent,
        ResponsesAssistantMessageItemResource,
    )

    # Seed DB synchronously before starting the adapter
    _ensure_db()
    _ready_event.set()

    class AgenticOpsAgent(FoundryCBAgent):
        def init_tracing(self):
            """Skip App Insights tracing to avoid blocking export errors.

            The base class sets up AzureMonitorTraceExporter via
            BatchSpanProcessor.  If the connection string is invalid the
            exporter retries on a background thread, flooding stderr and
            potentially starving async I/O.  We create a no-op tracer
            (spans are created but not exported anywhere).
            """
            from opentelemetry import trace as _trace
            self.tracer = _trace.get_tracer(__name__)
            logger.info("Tracing: using no-op tracer (App Insights export disabled)")

        async def agent_run(self, context: AgentRunContext):
            """Run the agent.

            For streaming (Foundry Playground always sends stream:true),
            returns an async generator *immediately* — before the OpenAI
            call starts.  The generator yields ``response.created`` and
            ``response.in_progress`` first, then awaits the OpenAI work.
            This keeps the adapter's SSE keep-alive mechanism active during
            the entire agent conversation, preventing the Foundry gateway's
            100 s timeout from closing the connection.
            """
            payload = context.raw_payload
            input_data = payload.get("input")
            messages = _parse_input_to_messages(input_data)

            # Fast validation — no OpenAI call needed for these errors
            error_text = None
            if not messages:
                error_text = "Invalid input format. Send {\"input\": \"your question\"}."
            else:
                endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
                deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1").strip()
                api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview").strip()
                if not endpoint:
                    error_text = "AZURE_OPENAI_ENDPOINT not configured. Agent cannot run."

            # --- Streaming path (Foundry Playground) ---
            # Return the async generator IMMEDIATELY so the adapter can
            # start sending SSE events (and keep-alive comments) right away.
            if context.stream:
                if error_text:
                    return self._stream_text(context, error_text)
                return self._stream_with_keepalive(
                    context, messages, endpoint, deployment, api_version,
                )

            # --- Non-streaming path ---
            if error_text:
                text = error_text
            else:
                result = await _run_agent_conversation(
                    messages, endpoint, deployment, api_version,
                )
                text = result["content"] if not result["error"] else f"Error: {result['error']}"
            if not text:
                text = "(no response)"
            return self._build_response(context, text)

        # -- helpers --------------------------------------------------------

        def _build_response(self, context, text: str):
            """Build a completed FoundryResponse object."""
            resp_id = context.response_id
            msg_id = context.id_generator.generate("msg")
            output_content = [ItemContentOutputText(text=text, annotations=[])]
            conversation = context.get_conversation_object()

            msg_item = ResponsesAssistantMessageItemResource(
                id=msg_id,
                status="completed",
                content=output_content,
            )
            return FoundryResponse(
                metadata={},
                temperature=0.0,
                top_p=0.0,
                user="",
                id=resp_id,
                created_at=dt.datetime.now(dt.timezone.utc),
                status="completed",
                error=None,
                incomplete_details=None,
                instructions=None,
                parallel_tool_calls=False,
                conversation=conversation,
                output=[msg_item],
            )

        async def _stream_with_keepalive(
            self, context, messages, endpoint, deployment, api_version,
        ):
            """Yield SSE events with the OpenAI call *inside* the generator.

            Flow:
              1. Yield ``response.created`` + ``response.in_progress``
                 → adapter starts SSE stream and keep-alive timer
              2. ``await _run_agent_conversation(...)`` (may take 30 s+)
                 → adapter sends ``: keep-alive`` SSE comments while waiting
              3. Yield content events once the answer is ready.

            This prevents the Foundry gateway's 100 s timeout from killing
            the connection during long agent conversations.
            """
            resp_id = context.response_id
            msg_id = context.id_generator.generate("msg")
            conversation = context.get_conversation_object()
            seq = 0

            # Skeleton response for early events
            skeleton = {
                "id": resp_id,
                "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "status": "in_progress",
                "output": [],
                "metadata": {},
                "temperature": 0.0,
                "top_p": 0.0,
                "user": "",
                "error": None,
                "incomplete_details": None,
                "instructions": None,
                "parallel_tool_calls": False,
            }

            # --- Yield early events BEFORE the OpenAI call ---
            yield ResponseCreatedEvent(
                type="response.created", sequence_number=seq, response=skeleton,
            )
            seq += 1

            yield ResponseInProgressEvent(
                type="response.in_progress", sequence_number=seq, response=skeleton,
            )
            seq += 1

            # --- OpenAI call (adapter sends keep-alives while we await) ---
            try:
                logger.info("Streaming: starting OpenAI call (keep-alives active)")
                result = await _run_agent_conversation(
                    messages, endpoint, deployment, api_version,
                )
                text = result["content"] if not result["error"] else f"Error: {result['error']}"
                if not text:
                    text = "(no response)"
                logger.info("Streaming: OpenAI call complete, yielding content events")
            except Exception as exc:
                logger.exception("Streaming: OpenAI call raised exception")
                text = f"Error: agent call failed: {exc}"

            # Build final objects
            output_content = [ItemContentOutputText(text=text, annotations=[])]
            msg_item = ResponsesAssistantMessageItemResource(
                id=msg_id,
                status="completed",
                content=output_content,
            )
            response = FoundryResponse(
                metadata={},
                temperature=0.0,
                top_p=0.0,
                user="",
                id=resp_id,
                created_at=dt.datetime.now(dt.timezone.utc),
                status="completed",
                error=None,
                incomplete_details=None,
                instructions=None,
                parallel_tool_calls=False,
                conversation=conversation,
                output=[msg_item],
            )

            # --- Yield content events ---
            item_dict = msg_item.as_dict()
            item_dict["status"] = "in_progress"
            item_dict["content"] = []
            yield ResponseOutputItemAddedEvent(
                type="response.output_item.added", sequence_number=seq,
                output_index=0, item=item_dict,
            )
            seq += 1

            yield ResponseContentPartAddedEvent(
                type="response.content_part.added", sequence_number=seq,
                output_index=0, content_index=0,
                part={"type": "output_text", "text": ""},
            )
            seq += 1

            yield ResponseTextDeltaEvent(
                type="response.output_text.delta", sequence_number=seq,
                output_index=0, content_index=0, delta=text,
            )
            seq += 1

            yield ResponseTextDoneEvent(
                type="response.output_text.done", sequence_number=seq,
                output_index=0, content_index=0, text=text,
            )
            seq += 1

            yield ResponseContentPartDoneEvent(
                type="response.content_part.done", sequence_number=seq,
                output_index=0, content_index=0,
                part={"type": "output_text", "text": text},
            )
            seq += 1

            yield ResponseOutputItemDoneEvent(
                type="response.output_item.done", sequence_number=seq,
                output_index=0, item=msg_item.as_dict(),
            )
            seq += 1

            yield ResponseCompletedEvent(
                type="response.completed", sequence_number=seq,
                response=response.as_dict(),
            )

        async def _stream_text(self, context, text: str):
            """Stream a pre-computed text (errors / fast responses)."""
            response = self._build_response(context, text)
            msg_item = response.output[0]
            seq = 0

            in_progress = response.as_dict()
            in_progress["status"] = "in_progress"
            in_progress["output"] = []

            yield ResponseCreatedEvent(
                type="response.created", sequence_number=seq, response=in_progress,
            )
            seq += 1

            yield ResponseInProgressEvent(
                type="response.in_progress", sequence_number=seq, response=in_progress,
            )
            seq += 1

            item_dict = msg_item.as_dict()
            item_dict["status"] = "in_progress"
            item_dict["content"] = []
            yield ResponseOutputItemAddedEvent(
                type="response.output_item.added", sequence_number=seq,
                output_index=0, item=item_dict,
            )
            seq += 1

            yield ResponseContentPartAddedEvent(
                type="response.content_part.added", sequence_number=seq,
                output_index=0, content_index=0,
                part={"type": "output_text", "text": ""},
            )
            seq += 1

            yield ResponseTextDeltaEvent(
                type="response.output_text.delta", sequence_number=seq,
                output_index=0, content_index=0, delta=text,
            )
            seq += 1

            yield ResponseTextDoneEvent(
                type="response.output_text.done", sequence_number=seq,
                output_index=0, content_index=0, text=text,
            )
            seq += 1

            yield ResponseContentPartDoneEvent(
                type="response.content_part.done", sequence_number=seq,
                output_index=0, content_index=0,
                part={"type": "output_text", "text": text},
            )
            seq += 1

            yield ResponseOutputItemDoneEvent(
                type="response.output_item.done", sequence_number=seq,
                output_index=0, item=msg_item.as_dict(),
            )
            seq += 1

            yield ResponseCompletedEvent(
                type="response.completed", sequence_number=seq,
                response=response.as_dict(),
            )

    agent = AgenticOpsAgent()
    logger.info("[STARTUP] using Foundry hosting adapter (uvicorn + FoundryCBAgent)")
    logger.info("[STARTUP] server listening on port %d", port)
    agent.run(port=port)


# ---------------------------------------------------------------------------
# aiohttp fallback (local dev / tests)
# ---------------------------------------------------------------------------

def _run_with_aiohttp(port: int) -> None:
    """Start the server using raw aiohttp (fallback for local dev/tests)."""
    from aiohttp import web

    app = asyncio.run(_init_app())
    logger.info("[STARTUP] using aiohttp fallback server")
    logger.info("[STARTUP] server listening on port %d", port)
    web.run_app(app, host="0.0.0.0", port=port, print=None, access_log=logger)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    global _startup_clock

    # Check if MODE=cli (run run_local.py instead)
    mode = os.environ.get("MODE", "").lower()
    if mode == "cli":
        from scripts.run_local import main as run_local_main
        run_local_main()
        return

    _startup_clock = time.monotonic()
    _log_startup_diagnostics()
    port = _resolve_port()

    # Use the official Foundry hosting adapter in production.
    # Falls back to aiohttp for local dev or when the adapter isn't installed.
    try:
        _run_with_foundry_adapter(port)
    except ImportError:
        logger.info("azure-ai-agentserver-core not installed — falling back to aiohttp")
        _run_with_aiohttp(port)


if __name__ == "__main__":
    main()
