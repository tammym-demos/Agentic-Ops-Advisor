#!/usr/bin/env python3
"""Invoke the Agentic Ops Advisor via the Foundry Responses API.

Supports two modes:

  prompt  — Register a PromptAgentDefinition with function tools and
            handle function_call items client-side.  This is the fastest
            way to test end-to-end without container routing.

  hosted  — Invoke the already-deployed hosted agent.  The container
            handles tool calls internally; the client just receives
            the final response.

Usage:
    # PromptAgent mode (client-side function calling):
    python scripts/run_foundry_agent.py --mode prompt "Show me GPU utilization"

    # HostedAgent mode (container handles tools):
    python scripts/run_foundry_agent.py --mode hosted "Show me GPU utilization"

    # Interactive REPL (default mode: prompt):
    python scripts/run_foundry_agent.py --interactive

Environment variables (required):
    AZURE_AI_AGENTS_ENDPOINT  — Foundry project endpoint
                                (e.g. https://hub.services.ai.azure.com/api/projects/proj)

Optional:
    AZURE_OPENAI_DEPLOYMENT   — Model deployment name (default: gpt-4.1)
    AGENT_NAME                — Agent name in Foundry (default: agentic-ops-advisor)
    ENABLE_WORK_IQ            — Enable work-context tool (default: true)

NOTE: All data is synthetic — for demo purposes only.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys

# Add repo root to sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool dispatch — reuses the existing tools/ surface
# ---------------------------------------------------------------------------

def _dispatch_tool(name: str, arguments: str) -> str:
    """Execute a tool function locally and return the result as a string."""
    import asyncio
    from tools.sql_telemetry import query_telemetry as async_query_telemetry
    from tools.action_stub import propose_change, request_approval
    from tools.work_context_stub import get_full_context, ENABLE_WORK_IQ

    kwargs = json.loads(arguments) if arguments else {}

    # Async tools
    if name == "query_telemetry":
        result = asyncio.run(async_query_telemetry(**kwargs))
    # Sync tools
    elif name == "propose_change":
        result = propose_change(**kwargs)
    elif name == "request_approval":
        result = request_approval(**kwargs)
    elif name == "get_work_context" and ENABLE_WORK_IQ:
        result = get_full_context(**kwargs)
    else:
        return json.dumps({"error": f"Unknown or disabled tool: {name}"})

    return result if isinstance(result, str) else json.dumps(result)


# ---------------------------------------------------------------------------
# Build tool definitions for PromptAgent registration
# ---------------------------------------------------------------------------

def _get_function_tool_definitions() -> list[dict]:
    """Collect tool schemas from all tool modules for PromptAgent registration."""
    from tools.sql_telemetry import TOOL_DEFINITIONS as sql_tools
    from tools.action_stub import ACTION_STUB_TOOL_DEFINITIONS as action_tools
    from tools.work_context_stub import (
        TOOL_DEFINITIONS as work_ctx_tools,
        ENABLE_WORK_IQ,
    )

    tools = list(sql_tools) + list(action_tools)
    if ENABLE_WORK_IQ:
        tools.extend(work_ctx_tools)
    return tools


# ---------------------------------------------------------------------------
# Load system prompt
# ---------------------------------------------------------------------------

def _load_system_prompt() -> str:
    """Load the system prompt from agent/system_prompt.md."""
    prompt_path = os.path.join(_REPO_ROOT, "agent", "system_prompt.md")
    try:
        with open(prompt_path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("System prompt not found at %s — using default", prompt_path)
        return "You are a helpful infrastructure operations assistant."


# ---------------------------------------------------------------------------
# Seed database (so tools have data to query)
# ---------------------------------------------------------------------------

def _ensure_database():
    """Seed the local SQLite database if needed."""
    os.environ.setdefault("DB_MODE", "sqlite")
    try:
        import sqlite3
        from data.seed import seed_connection

        db_path = os.path.join(_REPO_ROOT, "data", "telemetry.db")
        os.environ.setdefault("SQLITE_DB_PATH", db_path)
        conn = sqlite3.connect(db_path)
        try:
            seed_connection(conn)
        finally:
            conn.close()
        logger.info("Database seeded at %s", db_path)
    except Exception as exc:
        logger.warning("Database seeding failed (tools may not work): %s", exc)


# ---------------------------------------------------------------------------
# PromptAgent mode — client-side function calling via Responses API
# ---------------------------------------------------------------------------

def run_prompt_agent(user_input: str, endpoint: str, agent_name: str, model: str) -> str:
    """Register a PromptAgent with tools and handle function_call items.

    This follows the official Foundry pattern from:
    https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/runtime-components

    Returns the final assistant text response.
    """
    from azure.identity import DefaultAzureCredential
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import PromptAgentDefinition

    # 1. Create project client
    project = AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )

    # 2. Register agent with function tools
    system_prompt = _load_system_prompt()
    tool_definitions = _get_function_tool_definitions()

    logger.info("Registering PromptAgent '%s' with %d tools...", agent_name, len(tool_definitions))
    agent = project.agents.create_version(
        agent_name=agent_name,
        definition=PromptAgentDefinition(
            model=model,
            instructions=system_prompt,
            tools=tool_definitions,
        ),
    )
    logger.info("Agent registered: %s (version %s)", agent.name, agent.version)

    # 3. Get OpenAI client and invoke via Responses API
    openai = project.get_openai_client()

    logger.info("Sending message: %s", user_input[:100])
    response = openai.responses.create(
        extra_body={
            "agent_reference": {
                "name": agent.name,
                "type": "agent_reference",
            }
        },
        input=user_input,
    )

    # 4. Handle function_call loop
    max_rounds = 10
    for round_num in range(max_rounds):
        # Check if response contains function_call items
        function_calls = [
            item for item in response.output
            if item.type == "function_call"
        ]

        if not function_calls:
            # No function calls — we have the final response
            break

        logger.info("Round %d: %d function call(s)", round_num + 1, len(function_calls))

        # Execute each function call locally and build output items
        function_call_outputs = []
        for fc in function_calls:
            logger.info("  Calling tool: %s(%s)", fc.name, fc.arguments[:80] if fc.arguments else "")
            try:
                result = _dispatch_tool(fc.name, fc.arguments)
                logger.info("  Tool result: %s chars", len(result))
            except Exception as exc:
                logger.error("  Tool error: %s", exc)
                result = json.dumps({"error": str(exc)})

            function_call_outputs.append({
                "type": "function_call_output",
                "call_id": fc.call_id,
                "output": result,
            })

        # Submit function_call_output items back to the agent
        response = openai.responses.create(
            extra_body={
                "agent_reference": {
                    "name": agent.name,
                    "type": "agent_reference",
                }
            },
            previous_response_id=response.id,
            input=function_call_outputs,
        )
    else:
        logger.warning("Reached max function call rounds (%d)", max_rounds)

    # 5. Extract final text
    return response.output_text


# ---------------------------------------------------------------------------
# HostedAgent mode — container handles everything
# ---------------------------------------------------------------------------

def run_hosted_agent(user_input: str, endpoint: str, agent_name: str) -> str:
    """Invoke the deployed hosted agent via the Responses API.

    The hosted container handles tool calls internally — the client
    just gets the final response.

    Returns the final assistant text response.
    """
    from azure.identity import DefaultAzureCredential
    from azure.ai.projects import AIProjectClient

    # 1. Create project client
    project = AIProjectClient(
        endpoint=endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )

    # 2. Verify agent exists
    agent = project.agents.get(agent_name=agent_name)
    logger.info("Agent found: %s (version: %s)", agent.name, agent.versions.latest.version)

    # 3. Invoke via Responses API — container handles everything
    openai = project.get_openai_client()

    logger.info("Sending message: %s", user_input[:100])
    response = openai.responses.create(
        extra_body={
            "agent_reference": {
                "name": agent.name,
                "type": "agent_reference",
            }
        },
        input=[{"role": "user", "content": user_input}],
    )

    # Print tool calls for visibility
    for item in response.output:
        if item.type == "function_call":
            logger.info("[Tool] %s(%s) → handled by container", item.name, item.arguments[:60] if item.arguments else "")
        elif item.type == "web_search_call":
            logger.info("[Tool] Web search: status=%s", item.status)

    return response.output_text


# ---------------------------------------------------------------------------
# Interactive REPL
# ---------------------------------------------------------------------------

def run_interactive(mode: str, endpoint: str, agent_name: str, model: str):
    """Run an interactive conversation loop."""
    print(f"\n{'='*60}")
    print(f"  Agentic Ops Advisor — Foundry Agent ({mode} mode)")
    print(f"  Agent: {agent_name}")
    print("  Type 'quit' or 'exit' to stop")
    print(f"{'='*60}\n")

    while True:
        try:
            user_input = input("You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        try:
            if mode == "prompt":
                response = run_prompt_agent(user_input, endpoint, agent_name, model)
            else:
                response = run_hosted_agent(user_input, endpoint, agent_name)

            print(f"\nAgent> {response}\n")
        except Exception as exc:
            logger.error("Error: %s", exc, exc_info=True)
            print(f"\n[Error] {exc}\n")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Invoke the Agentic Ops Advisor via the Foundry Responses API",
    )
    parser.add_argument(
        "--mode",
        choices=["prompt", "hosted"],
        default="prompt",
        help="Agent mode: 'prompt' (client-side function calling) or 'hosted' (container handles tools). Default: prompt",
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive REPL mode",
    )
    parser.add_argument(
        "--agent-name",
        default=os.environ.get("AGENT_NAME", "agentic-ops-advisor"),
        help="Agent name in Foundry (default: agentic-ops-advisor)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1"),
        help="Model deployment name for PromptAgent mode (default: gpt-4.1)",
    )
    parser.add_argument(
        "message",
        nargs="*",
        help="Message to send to the agent (ignored in interactive mode)",
    )
    args = parser.parse_args()

    # Validate endpoint
    endpoint = os.environ.get("AZURE_AI_AGENTS_ENDPOINT", "").strip()
    if not endpoint:
        print("❌ AZURE_AI_AGENTS_ENDPOINT environment variable is required.")
        print("   Format: https://<resource>.services.ai.azure.com/api/projects/<project>")
        sys.exit(1)

    # Seed database for prompt mode (tools run locally)
    if args.mode == "prompt":
        _ensure_database()

    if args.interactive:
        run_interactive(args.mode, endpoint, args.agent_name, args.model)
    elif args.message:
        user_input = " ".join(args.message)
        try:
            if args.mode == "prompt":
                response = run_prompt_agent(user_input, endpoint, args.agent_name, args.model)
            else:
                response = run_hosted_agent(user_input, endpoint, args.agent_name)
            print(response)
        except Exception as exc:
            logger.error("Failed: %s", exc, exc_info=True)
            sys.exit(1)
    else:
        print("Provide a message or use --interactive mode.")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
