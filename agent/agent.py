"""Agentic Ops Advisor — agent definition and orchestration.

Uses the Azure AI Agent Service SDK (azure-ai-agents) to create a governed,
production-style AI agent for root-cause + change-context reasoning over
infrastructure telemetry and operator intent.

Core queries handled:
  1. "Why did GPU utilization drop in the last 24h?"
  2. "What changed right before the latency spike?"
  3. "Is this a known issue or a change-caused incident?"
  4. "What's the safest remediation plan? Provide options and tradeoffs."
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT_PATH = Path(__file__).parent / "system_prompt.md"


def _load_system_prompt() -> str:
    """Load the agent system prompt from agent/system_prompt.md.

    Raises:
        RuntimeError: If the system prompt file does not exist.
    """
    try:
        return _SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"System prompt not found at {_SYSTEM_PROMPT_PATH}. "
            "Ensure agent/system_prompt.md exists in the repository."
        ) from exc


# ---------------------------------------------------------------------------
# Agent SDK helpers
# ---------------------------------------------------------------------------


def _import_agent_sdk() -> tuple[Any, Any]:
    """Import and return (FunctionTool, ToolSet) from the azure-ai-agents SDK.

    Centralises the import so both create_agent() and ask() share the same
    error message and import path.

    Raises:
        RuntimeError: If azure-ai-agents is not installed.
    """
    try:
        from azure.ai.agents.models import FunctionTool, ToolSet

        return FunctionTool, ToolSet
    except ImportError as exc:
        raise RuntimeError(
            "azure-ai-agents is required. "
            "Install it with: pip install 'azure-ai-agents>=1.0.0'"
        ) from exc


# ---------------------------------------------------------------------------
# Sync wrapper for the async query_telemetry tool
#
# The Azure AI Agent Service FunctionTool dispatches tool calls synchronously,
# so we bridge the async gap by running the coroutine in a dedicated thread.
# ---------------------------------------------------------------------------


def query_telemetry(
    table: str | None = None,
    aggregate: str | None = None,
    sql: str | None = None,
    limit: int = 100,
    filters: dict[str, Any] | None = None,
) -> str:
    """Query synthetic infrastructure telemetry data stored in SQL.

    Covers GPU utilization, network throughput/latency, cost, and incidents.
    All data is synthetic and for demo purposes only.

    Args:
        table: Return raw rows from one of the telemetry tables:
            'telemetry_gpu', 'telemetry_net', 'telemetry_cost', 'incidents'.
        aggregate: Run a pre-built aggregate query. Available keys:
            cost_by_service_24h, gpu_avg_util_1h, gpu_avg_util_24h,
            net_avg_latency_1h, open_incidents, recent_incidents_24h.
        sql: A raw SELECT statement scoped to the known telemetry tables.
            Only SELECT is permitted; no DDL or DML.
        limit: Maximum number of rows to return for plain table queries
            (default 100, max 500).
        filters: Optional key/value pairs applied as equality WHERE filters
            for plain table queries. Example: {"host": "gpu-node-01"}.

    Returns:
        JSON string with keys 'columns', 'rows', 'row_count', and 'meta'.
    """
    from tools.sql_telemetry import query_telemetry as _async_query_telemetry

    coro = _async_query_telemetry(
        table=table,
        aggregate=aggregate,
        sql=sql,
        limit=limit,
        filters=filters,
    )

    # Run the coroutine in a fresh event loop in a worker thread so this
    # function stays safe to call regardless of whether an event loop is
    # already running in the current thread.
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(asyncio.run, coro)
        return future.result()


# ---------------------------------------------------------------------------
# Toolset builder
# ---------------------------------------------------------------------------


def _build_function_set(enable_work_iq: bool) -> set:
    """Return the set of callable tool functions based on feature flags.

    Always includes:
      - query_telemetry  (SQL telemetry, sync wrapper over async impl)
      - propose_change   (action stub)
      - request_approval (action stub)

    Conditionally includes (when enable_work_iq=True):
      - get_work_context (Work IQ context stub)
    """
    from tools.action_stub import propose_change, request_approval

    functions: set = {query_telemetry, propose_change, request_approval}

    if enable_work_iq:
        from tools.work_context_stub import get_work_context

        functions.add(get_work_context)
        logger.debug("Work IQ tool registered (ENABLE_WORK_IQ=true)")
    else:
        logger.debug("Work IQ tool skipped (ENABLE_WORK_IQ=false)")

    return functions


# ---------------------------------------------------------------------------
# AgentOpsAdvisor
# ---------------------------------------------------------------------------

AGENT_NAME = "agentic-ops-advisor"


class AgentOpsAdvisor:
    """Orchestrates the Agentic Ops Advisor on Azure AI Agent Service.

    Usage (context manager — recommended for clean teardown)::

        with AgentOpsAdvisor(settings) as advisor:
            advisor.create_agent()
            thread = advisor.create_thread()
            answer = advisor.ask(thread.id, "Why did GPU utilization drop?")
            print(answer)

    Usage (manual lifecycle)::

        advisor = AgentOpsAdvisor(settings)
        try:
            advisor.create_agent()
            thread = advisor.create_thread()
            answer = advisor.ask(thread.id, "What changed before the latency spike?")
        finally:
            advisor.delete_agent()
            advisor.close()
    """

    def __init__(self, settings: Any = None) -> None:
        """Initialize the advisor.

        Args:
            settings: A :class:`agent.config.Settings` instance. If *None*,
                      settings are loaded from environment variables via
                      ``Settings.from_env()``. Raises ``ValueError`` if
                      required environment variables are missing.
        """
        if settings is None:
            from agent.config import Settings

            settings = Settings.from_env()
        self._settings = settings
        self._client: Any = None
        self._agent: Any = None

    # ------------------------------------------------------------------
    # Client lifecycle
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        """Lazily create and return the AgentsClient.

        Raises:
            RuntimeError: If the SDK packages are not installed.
            ValueError:   If the endpoint is not configured.
        """
        if self._client is None:
            try:
                from azure.ai.agents import AgentsClient
                from azure.identity import DefaultAzureCredential
            except ImportError as exc:
                raise RuntimeError(
                    "azure-ai-agents and azure-identity are required. "
                    "Install them with: pip install azure-ai-agents azure-identity"
                ) from exc

            endpoint = self._settings.azure_ai_agents_endpoint
            if not endpoint:
                raise ValueError(
                    "AZURE_AI_AGENTS_ENDPOINT is not set. "
                    "Set it in your environment or .env file (see .env.example)."
                )

            logger.debug("Initializing AgentsClient with endpoint: %s", endpoint)
            self._client = AgentsClient(
                endpoint=endpoint,
                credential=DefaultAzureCredential(),
            )
        return self._client

    def close(self) -> None:
        """Close the underlying HTTP client and release all resources."""
        if self._client is not None:
            try:
                self._client.close()
                logger.debug("AgentsClient closed")
            except Exception:  # noqa: BLE001
                logger.warning("Error closing AgentsClient", exc_info=True)
            finally:
                self._client = None

    # ------------------------------------------------------------------
    # Agent lifecycle
    # ------------------------------------------------------------------

    def create_agent(self, name: str = AGENT_NAME) -> Any:
        """Create the agent on Azure AI Agent Service.

        Loads the system prompt, builds the toolset (honouring the
        ``enable_work_iq`` feature flag), and registers the agent with the
        configured GPT-4.1 deployment.

        Args:
            name: Display name for the agent (default: ``"agentic-ops-advisor"``).

        Returns:
            The agent object returned by the SDK (has ``.id`` attribute).

        Raises:
            RuntimeError: If the system prompt file is missing or the API call fails.
        """
        FunctionTool, ToolSet = _import_agent_sdk()

        client = self._get_client()
        system_prompt = _load_system_prompt()

        function_set = _build_function_set(self._settings.enable_work_iq)
        toolset = ToolSet()
        toolset.add(FunctionTool(functions=function_set))

        tool_names = [fn.__name__ for fn in function_set]
        logger.info(
            "Creating agent '%s' | model='%s' | tools=%s",
            name,
            self._settings.azure_openai_deployment,
            tool_names,
        )

        try:
            self._agent = client.create_agent(
                model=self._settings.azure_openai_deployment,
                name=name,
                instructions=system_prompt,
                toolset=toolset,
            )
        except Exception as exc:
            logger.error("Failed to create agent '%s': %s", name, exc)
            raise RuntimeError(f"Agent creation failed: {exc}") from exc

        logger.info("Agent created: id=%s name=%s", self._agent.id, name)
        return self._agent

    def delete_agent(self) -> None:
        """Delete the agent from Azure AI Agent Service and release the reference."""
        if self._agent is not None:
            agent_id = self._agent.id
            try:
                client = self._get_client()
                client.delete_agent(agent_id)
                logger.info("Agent deleted: id=%s", agent_id)
            except Exception:  # noqa: BLE001
                logger.warning("Error deleting agent id=%s", agent_id, exc_info=True)
            finally:
                self._agent = None

    @property
    def agent_id(self) -> str | None:
        """Return the agent ID, or None if no agent has been created."""
        return self._agent.id if self._agent is not None else None

    # ------------------------------------------------------------------
    # Thread management
    # ------------------------------------------------------------------

    def create_thread(self) -> Any:
        """Create a new conversation thread.

        Returns:
            The thread object returned by the SDK (has ``.id`` attribute).
        """
        client = self._get_client()
        thread = client.threads.create()
        logger.debug("Thread created: id=%s", thread.id)
        return thread

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------

    def ask(self, thread_id: str, message: str) -> str:
        """Add a user message to the thread and run the agent to completion.

        Handles the full agentic loop — tool calls are dispatched automatically
        by the SDK's ``create_and_process_run`` until the run reaches a
        terminal state (``completed``, ``failed``, ``cancelled``, or
        ``expired``).

        Args:
            thread_id: ID of an existing conversation thread (from
                       :meth:`create_thread`).
            message:   User message text (one of the four core query types or
                       any operator question).

        Returns:
            The agent's final text response as a plain string.

        Raises:
            RuntimeError: If the agent has not been created, the API call
                          fails, or the run ends in a ``failed`` state.
        """
        if self._agent is None:
            raise RuntimeError(
                "Agent has not been created. Call create_agent() before ask()."
            )

        FunctionTool, ToolSet = _import_agent_sdk()

        client = self._get_client()

        # Re-build the toolset so the FunctionTool dispatch callbacks are
        # available for this specific run.
        function_set = _build_function_set(self._settings.enable_work_iq)
        toolset = ToolSet()
        toolset.add(FunctionTool(functions=function_set))

        logger.debug("Adding user message to thread %s: %.80r", thread_id, message)
        client.messages.create(
            thread_id=thread_id,
            role="user",
            content=message,
        )

        logger.debug("Starting agent run on thread %s", thread_id)
        try:
            run = client.runs.create_and_process(
                thread_id=thread_id,
                agent_id=self._agent.id,
                toolset=toolset,
            )
        except Exception as exc:
            logger.error("create_and_process_run failed for thread %s: %s", thread_id, exc)
            raise RuntimeError(f"Agent run failed: {exc}") from exc

        logger.debug("Run %s completed with status '%s'", run.id, run.status)

        if run.status == "failed":
            error_detail = getattr(run, "last_error", "unknown error")
            logger.error("Run %s ended in failed state: %s", run.id, error_detail)
            raise RuntimeError(f"Agent run ended in failed state: {error_detail}")

        return self._extract_last_assistant_message(thread_id)

    def _extract_last_assistant_message(self, thread_id: str) -> str:
        """Return the text of the most-recent assistant message in the thread.

        Args:
            thread_id: The conversation thread ID.

        Returns:
            The text content of the latest assistant message, or an empty
            string if no assistant message is found.
        """
        from azure.ai.agents.models import MessageRole

        client = self._get_client()
        last_msg = client.messages.get_last_message_text_by_role(
            thread_id=thread_id,
            role=MessageRole.AGENT,
        )
        return last_msg if last_msg else ""

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "AgentOpsAdvisor":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Delete the agent and close the client on context exit."""
        self.delete_agent()
        self.close()


# ---------------------------------------------------------------------------
# Convenience: one-shot query helper
# ---------------------------------------------------------------------------


def run_query(message: str, settings: Any = None) -> str:
    """One-shot convenience helper: create an agent, ask once, return the answer.

    The agent is deleted after the call regardless of success or failure.
    Useful for scripting, quick demos, and evaluation runs.

    Args:
        message:  The operator query. Handles the four core query types:
                  - "Why did GPU utilization drop in the last 24h?"
                  - "What changed right before the latency spike?"
                  - "Is this a known issue or a change-caused incident?"
                  - "What's the safest remediation plan? Provide options and tradeoffs."
        settings: Optional :class:`agent.config.Settings`. Defaults to env vars.

    Returns:
        The agent's text response.
    """
    with AgentOpsAdvisor(settings) as advisor:
        advisor.create_agent()
        thread = advisor.create_thread()
        return advisor.ask(thread.id, message)
