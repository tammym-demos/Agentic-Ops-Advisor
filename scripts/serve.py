#!/usr/bin/env python3
"""Agentic Ops Advisor — Agent Framework hosted agent.

Usage:
    python scripts/serve.py

What it does:
    1. Seeds the SQLite database with synthetic telemetry (if needed)
    2. Loads system prompt from agent/system_prompt.md
    3. Creates an AzureOpenAIChatClient agent with tool functions
    4. Serves the Responses API on port 8088 via from_agent_framework()

Environment variables:
    See .env.example for the full list.  Key ones:
    - AZURE_OPENAI_ENDPOINT (required)
    - AZURE_OPENAI_DEPLOYMENT (default: gpt-4.1)
    - ENABLE_WORK_IQ (default: true)
    - DB_MODE (default: sqlite)

NOTE: All data is synthetic.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys

# ---------------------------------------------------------------------------
# Bootstrap: add repo root to sys.path before any local imports
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# ---------------------------------------------------------------------------
# Sensible defaults BEFORE importing tool modules
# ---------------------------------------------------------------------------
os.environ.setdefault("DB_MODE", "sqlite")
os.environ.setdefault("ENABLE_WORK_IQ", "true")
os.environ.setdefault("ENABLE_MCP", "false")

# ---------------------------------------------------------------------------
# SDK compatibility shim: agent-framework-azure-ai references symbols that
# were renamed in azure-ai-projects 2.0.x.  Patch before any framework import.
# ---------------------------------------------------------------------------
from scripts.patch_sdk_compat import apply_compat_shim  # noqa: E402
apply_compat_shim()

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
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_PATH = os.path.join(_REPO_ROOT, "agent", "system_prompt.md")


def _load_system_prompt() -> str:
    """Load system prompt from agent/system_prompt.md."""
    try:
        with open(_SYSTEM_PROMPT_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        logger.warning("System prompt not found at %s", _SYSTEM_PROMPT_PATH)
        return ""


# ---------------------------------------------------------------------------
# Startup diagnostics
# ---------------------------------------------------------------------------


def _log_startup_diagnostics() -> None:
    """Log configuration values at startup for troubleshooting."""
    logger.info("Starting Agentic Ops Advisor hosted agent server …")
    ep = os.environ.get("AZURE_OPENAI_ENDPOINT", "(not set)")
    deploy = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "(not set)")
    logger.info("AZURE_OPENAI_ENDPOINT: %s", ep)
    logger.info("AZURE_OPENAI_DEPLOYMENT: %s", deploy)
    logger.info(
        "AZURE_OPENAI_API_KEY: %s",
        "set" if os.environ.get("AZURE_OPENAI_API_KEY") else "not set",
    )
    logger.info(
        "AZURE_CLIENT_ID: %s",
        "set" if os.environ.get("AZURE_CLIENT_ID") else "not set",
    )
    try:
        from urllib.parse import urlparse

        parsed = urlparse(ep)
        if parsed.hostname:
            logger.info("Parsed endpoint hostname: %s", parsed.hostname)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Tool list assembly
# ---------------------------------------------------------------------------


def _get_tools() -> list:
    """Return tool callables based on feature flags."""
    from tools.sql_telemetry import query_telemetry
    from tools.action_stub import propose_change, request_approval
    from tools.work_context_stub import get_work_context, ENABLE_WORK_IQ

    tools = [query_telemetry]
    if ENABLE_WORK_IQ:
        tools.append(get_work_context)
    tools.extend([propose_change, request_approval])
    return tools


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Initialise and start the Agent Framework hosted agent."""
    from agent_framework.azure import AzureOpenAIChatClient
    from azure.ai.agentserver.agentframework import from_agent_framework
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    from agent.config import Settings

    _log_startup_diagnostics()

    # Belt-and-suspenders: ensure the SDK's env var fallback works too
    _deploy = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
    if _deploy and not os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"):
        os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"] = _deploy

    # 1. Seed database (must run before the blocking .run() call)
    _ensure_db()

    # 2. Load config and system prompt
    settings = Settings.from_env()
    system_prompt = _load_system_prompt()

    # 3. Create the Azure OpenAI chat client
    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(
        credential, "https://cognitiveservices.azure.com/.default"
    )
    chat_client = AzureOpenAIChatClient(
        ad_token_provider=token_provider,
        endpoint=settings.azure_openai_endpoint,
        deployment_name=settings.azure_openai_deployment,
    )

    # 4. Create agent with tools
    tools = _get_tools()
    agent = chat_client.create_agent(
        name="agentic-ops-advisor",
        instructions=system_prompt,
        tools=tools,
    )

    # 5. Serve — blocks, exposes /responses on port 8088
    logger.info("Starting Agentic Ops Advisor on port 8088 …")
    from_agent_framework(agent).run()


if __name__ == "__main__":
    main()
