#!/usr/bin/env python3
"""Local development runner for Agentic Ops Advisor.

Usage:
    python scripts/run_local.py

What it does:
    1. Sets DB_MODE=sqlite automatically.
    2. Seeds the database if it doesn't exist.
    3. Starts a health check server on port 8080 (GET /health).
    4. Starts an interactive terminal chat loop in one of two modes:

       Agent mode (Azure OpenAI configured):
           Full reasoning loop powered by GPT-4.1 with function-calling
           against the local SQLite telemetry database.

       Demo mode (no Azure credentials):
           Tool-only mode — queries are executed directly against the local
           database and results are printed in a structured format.  No LLM
           required; useful for validating the data layer without Azure.

    5. Suggests the 4 core demo queries on start-up.
    6. Handles Ctrl+C / EOF gracefully.

NOTE: All data is synthetic.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import sys
import textwrap
import threading
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
# Core demo queries (displayed as numbered suggestions)
# ---------------------------------------------------------------------------
DEMO_QUERIES: list[str] = [
    "Why did GPU utilization drop in the last 24h?",
    "What changed right before the latency spike?",
    "Is this a known issue or a change-caused incident?",
    "What's the safest remediation plan? Provide options and tradeoffs.",
]

# System prompt used in agent mode
_SYSTEM_PROMPT = textwrap.dedent("""\
    You are Agentic Ops Advisor — a professional AI ops teammate with light humour.

    You help ops engineers diagnose infrastructure issues by reasoning over
    telemetry data and change context.  All data you access is synthetic (demo).

    Response format:
    • Short, crisp bullets
    • Always include a "Confidence: High / Med / Low" line
    • Always cite evidence from tool results
    • Include a "Next best question" when confidence is not High
    • Propose a remediation plan with risk level when relevant

    Available tools query a local SQLite database populated with synthetic
    infrastructure telemetry (GPU, network, cost, incidents).
""")


# ---------------------------------------------------------------------------
# Health check server
# ---------------------------------------------------------------------------

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

    from aiohttp import web  # noqa: PLC0415

    return web.json_response({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": version,
    })


async def _start_health_server(port: int = 8080) -> None:
    """Start the health check HTTP server on the specified port."""
    from aiohttp import web  # noqa: PLC0415

    app = web.Application()
    app.router.add_get("/health", _health_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"  [health] Health server started on http://0.0.0.0:{port}/health\n")


def _run_health_server_thread(port: int = 8080) -> None:
    """Run the health server in a background thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(_start_health_server(port))
    loop.run_forever()


# ---------------------------------------------------------------------------
# DB bootstrap
# ---------------------------------------------------------------------------

def _ensure_db() -> None:
    """Seed the SQLite database if it doesn't already exist."""
    from data.seed_telemetry import DEFAULT_DB_PATH, create_schema, seed_connection  # noqa: PLC0415

    if os.path.exists(DEFAULT_DB_PATH):
        return

    print("  [setup] Database not found — seeding synthetic data …")
    import sqlite3

    os.makedirs(os.path.dirname(DEFAULT_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DEFAULT_DB_PATH)
    try:
        create_schema(conn)
        counts = seed_connection(conn)
        for table, n in counts.items():
            print(f"  [setup]   {table}: {n:,} rows")
    finally:
        conn.close()
    print("  [setup] Database ready.\n")


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

_BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║          Agentic Ops Advisor  —  Local Dev Mode              ║
║   (All data is synthetic — safe for demo use)                ║
╚══════════════════════════════════════════════════════════════╝
"""


def _print_banner() -> None:
    print(_BANNER)


def _print_suggestions() -> None:
    print("  Suggested queries (type the number or your own question):\n")
    for i, q in enumerate(DEMO_QUERIES, start=1):
        print(f"    [{i}] {q}")
    print()
    print("  Type 'quit' or press Ctrl+C to exit.\n")


def _resolve_input(user_input: str) -> str:
    """Expand a numeric shortcut to the corresponding demo query."""
    stripped = user_input.strip()
    if stripped.isdigit():
        idx = int(stripped)
        if 1 <= idx <= len(DEMO_QUERIES):
            return DEMO_QUERIES[idx - 1]
    return stripped


# ---------------------------------------------------------------------------
# Demo mode (no LLM)
# ---------------------------------------------------------------------------

def _run_demo_mode() -> None:
    """Tool-only interactive loop — no LLM required."""
    from tools.sql_telemetry import TOOL_CALLABLES  # noqa: PLC0415
    from tools.work_context_stub import (  # noqa: PLC0415
        ENABLE_WORK_IQ,
        get_change_events,
        get_decisions,
        get_full_context,
        get_ownership,
        get_runbooks,
    )

    print("  Mode: DEMO (no Azure OpenAI configured — running tool-only mode)\n")
    print("  In demo mode, queries are matched to telemetry tools and raw results")
    print("  are returned.  Configure AZURE_OPENAI_ENDPOINT for full agent mode.\n")
    print("-" * 64)

    _print_suggestions()

    while True:
        try:
            raw = input("You › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye! 👋")
            return

        if not raw:
            continue
        if raw.lower() in {"quit", "exit", "q"}:
            print("Goodbye! 👋")
            return

        query = _resolve_input(raw)
        print(f"\n  Running tools for: {query!r}\n")

        # Route to appropriate tools based on keywords in the query
        ql = query.lower()
        results: dict[str, object] = {}

        if any(kw in ql for kw in ("gpu", "utiliz", "utilisation", "cuda")):
            results["gpu_summary"] = TOOL_CALLABLES["query_gpu_utilization"](hours_back=24)

        if any(kw in ql for kw in ("latency", "network", "spike", "changed", "change", "rollout")):
            results["network_summary"] = TOOL_CALLABLES["query_network_telemetry"](hours_back=96)

        if any(kw in ql for kw in ("cost", "spend", "billing", "token")):
            results["cost_trends"] = TOOL_CALLABLES["query_cost_trends"](days_back=7)

        if any(kw in ql for kw in ("incident", "known", "issue", "open", "remediat", "plan")):
            results["incidents"] = TOOL_CALLABLES["query_incidents"](status="open")

        # Fallback: return all telemetry summaries
        if not results:
            results["gpu_summary"] = TOOL_CALLABLES["query_gpu_utilization"](hours_back=24)
            results["network_summary"] = TOOL_CALLABLES["query_network_telemetry"](hours_back=24)
            results["incidents"] = TOOL_CALLABLES["query_incidents"](status="open")

        # --- Work-context enrichment (gated by ENABLE_WORK_IQ) ---
        if ENABLE_WORK_IQ:
            # Determine the relevant service based on query keywords
            service: str | None = None
            if any(kw in ql for kw in ("gpu", "utiliz", "utilisation", "cuda")):
                service = "gpu-cluster"
            elif any(kw in ql for kw in ("latency", "network", "spike")):
                service = "network"
            elif any(kw in ql for kw in ("cost", "spend", "billing", "token")):
                service = "cost"

            if any(kw in ql for kw in ("changed", "change", "rollout")):
                svc = service or "gpu-cluster"
                results["change_events"] = get_change_events(svc)

            if any(kw in ql for kw in ("incident", "known", "issue", "remediat", "plan")):
                svc = service or "gpu-cluster"
                results["ownership"] = get_ownership(svc)
                results["runbooks"] = get_runbooks(svc)
                results["decisions"] = get_decisions(svc)

            # Fallback: if no specific work-context was added, include full context
            if not any(k in results for k in ("change_events", "ownership", "runbooks", "decisions")):
                svc = service or "gpu-cluster"
                results["work_context"] = get_full_context(svc)

        for tool_name, data in results.items():
            print(f"  ── {tool_name} ──")
            print(json.dumps(data, indent=4))
            print()

        print(
            "  ℹ  Configure AZURE_OPENAI_ENDPOINT + AZURE_OPENAI_DEPLOYMENT in .env\n"
            "     to enable LLM-powered root-cause analysis.\n"
        )
        print("-" * 64)


# ---------------------------------------------------------------------------
# Agent mode (Azure OpenAI with function calling)
# ---------------------------------------------------------------------------

def _call_tool(name: str, arguments: str) -> str:
    """Dispatch a function-call from the LLM to the local tool surface."""
    from tools.sql_telemetry import TOOL_CALLABLES  # noqa: PLC0415

    if name not in TOOL_CALLABLES:
        return json.dumps({"error": f"Unknown tool: {name}"})
    try:
        kwargs = json.loads(arguments) if arguments else {}
        result = TOOL_CALLABLES[name](**kwargs)
        return json.dumps(result)
    except (json.JSONDecodeError, TypeError, ValueError, FileNotFoundError, OSError) as exc:
        return json.dumps({"error": str(exc)})


def _run_agent_mode(endpoint: str, deployment: str, api_version: str) -> None:
    """Full reasoning loop using Azure OpenAI with function-calling."""
    try:
        from openai import AzureOpenAI  # noqa: PLC0415
    except ImportError:
        print(
            "  ✗ openai package not found. Install with:\n"
            "    pip install openai\n"
            "  Or install project dependencies:\n"
            "    pip install -r requirements.txt\n",
            file=sys.stderr,
        )
        sys.exit(1)

    from tools.sql_telemetry import TOOL_DEFINITIONS  # noqa: PLC0415

    client = AzureOpenAI(
        azure_endpoint=endpoint,
        api_version=api_version,
        # Uses DefaultAzureCredential / AZURE_OPENAI_API_KEY from env automatically
    )

    print(f"  Mode: AGENT (Azure OpenAI · {deployment} · {endpoint})\n")
    print("-" * 64)
    _print_suggestions()

    conversation: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]

    while True:
        try:
            raw = input("You › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye! 👋")
            return

        if not raw:
            continue
        if raw.lower() in {"quit", "exit", "q"}:
            print("Goodbye! 👋")
            return

        query = _resolve_input(raw)
        conversation.append({"role": "user", "content": query})

        # Agentic loop: keep going until the model stops calling tools
        max_tool_rounds = 8
        for _round in range(max_tool_rounds):
            try:
                response = client.chat.completions.create(
                    model=deployment,
                    messages=conversation,  # type: ignore[arg-type]
                    tools=TOOL_DEFINITIONS,  # type: ignore[arg-type]
                    tool_choice="auto",
                    temperature=0.2,
                )
            except Exception as exc:  # noqa: BLE001
                # Catch-all: the openai SDK raises various exception types
                # (APIConnectionError, AuthenticationError, RateLimitError, etc.)
                # that aren't always importable without openai being installed.
                # We surface the message and break rather than crash the loop.
                print(f"\n  ✗ Azure OpenAI error: {exc}\n", file=sys.stderr)
                break

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
                print(f"\nAdvisor › {answer}\n")
                print("-" * 64)
                break
        else:
            print("  ⚠ Reached max tool-call rounds — check your query.\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    _print_banner()

    # Ensure DB exists before doing anything else
    try:
        _ensure_db()
    except (OSError, sqlite3.Error, ImportError) as exc:
        print(f"  ✗ Failed to set up database: {exc}", file=sys.stderr)
        sys.exit(1)

    # Start health check server in background thread
    health_port = int(os.environ.get("HEALTH_PORT", "8080"))
    health_thread = threading.Thread(
        target=_run_health_server_thread,
        args=(health_port,),
        daemon=True,
        name="health-server"
    )
    health_thread.start()

    # Small delay to let health server start
    import time
    time.sleep(0.5)

    # Determine operating mode
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1").strip()
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview").strip()

    if endpoint:
        _run_agent_mode(endpoint, deployment, api_version)
    else:
        _run_demo_mode()


if __name__ == "__main__":
    main()
