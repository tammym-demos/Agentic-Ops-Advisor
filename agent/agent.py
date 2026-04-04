"""AgentOpsAdvisor — orchestrates the Azure AI Agent Service with three tool surfaces.

Architecture:
  1. SQL Telemetry Tool  — queries synthetic infra telemetry (GPU, network, cost, incidents)
  2. Work IQ Context     — returns synthetic change context (feature flag: ENABLE_WORK_IQ)
  3. Action Stub         — proposes changes + simulates approval (safe stubs only)
"""

from __future__ import annotations

from typing import Any

from agent.config import Settings

# Tool surface imports (always available — no Azure dependency)
from tools.action_stub import propose_change, request_approval
from tools.sql_telemetry import query_telemetry_sync
from tools.work_context_stub import (
    get_change_events,
    get_decisions,
    get_full_context,
    get_ownership,
    get_runbooks,
)


class AgentOpsAdvisor:
    """Governed agent that reasons over infrastructure telemetry and operator intent."""

    SYSTEM_PROMPT = """You are the Agentic Ops Advisor — a professional ops teammate with light humor.

Your job: perform root-cause + change-context reasoning over infrastructure telemetry and operator intent.

Rules:
- Always include a "Confidence" line (High / Med / Low) in your response.
- Always cite evidence from tools ("Telemetry query showed…", "Change context indicated…").
- Use short, crisp bullets. Keep prose minimal.
- Include a "Next best question" if confidence is not High.
- Light humor is OK (roast ambiguous requests, not people).
- ALL data is synthetic. Include disclaimer when presenting results.

Work IQ disclaimer (include when using work context):
"We're simulating Work IQ outputs in this demo. Work IQ is in public preview and requires
Microsoft 365 Copilot licensing + admin consent."
"""

    def __init__(self, config: Settings | None = None) -> None:
        if config is None:
            config = Settings.from_env()
        self.config = config
        self._agent: Any = None  # Azure AI Agent handle (set after connect())
        self._client: Any = None  # AIProjectClient handle

    # ------------------------------------------------------------------
    # Tool registration (pure Python — no Azure dependency)
    # ------------------------------------------------------------------

    def get_tool_functions(self) -> dict[str, Any]:
        """Return the dict of callable tool functions to register with the agent.

        Work IQ tools are conditionally included based on enable_work_iq setting.
        """
        tools: dict[str, Any] = {
            "query_telemetry": query_telemetry_sync,
            "propose_change": propose_change,
            "request_approval": request_approval,
        }

        if self.config.enable_work_iq:
            tools["get_change_events"] = get_change_events
            tools["get_decisions"] = get_decisions
            tools["get_ownership"] = get_ownership
            tools["get_runbooks"] = get_runbooks
            tools["get_full_context"] = get_full_context

        return tools

    # ------------------------------------------------------------------
    # Azure connection (requires credentials — skipped in test mode)
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Connect to Azure AI Foundry and create/retrieve the agent.

        Raises:
            RuntimeError: If Azure credentials are not configured.
        """
        if not self.config.azure_ai_project_connection_string or not self.config.azure_openai_endpoint:
            raise RuntimeError(
                "Azure credentials are not configured. "
                "Set AZURE_AI_PROJECT_CONNECTION_STRING and AZURE_OPENAI_ENDPOINT."
            )

        try:
            from azure.ai.projects import AIProjectClient
            from azure.ai.projects.models import FunctionTool, ToolSet
            from azure.identity import DefaultAzureCredential
        except ImportError as exc:
            raise RuntimeError(
                f"Azure AI SDK not installed: {exc}. Run: pip install azure-ai-projects azure-identity"
            ) from exc

        self._client = AIProjectClient.from_connection_string(
            credential=DefaultAzureCredential(),
            conn_str=self.config.azure_ai_project_connection_string,
        )

        functions = FunctionTool(functions=set(self.get_tool_functions().values()))
        toolset = ToolSet()
        toolset.add(functions)

        self._agent = self._client.agents.create_agent(
            model=self.config.azure_openai_deployment,
            name="agentic-ops-advisor",
            instructions=self.SYSTEM_PROMPT,
            toolset=toolset,
        )

    def ask(self, query: str) -> str:
        """Send a query to the agent and return the response text.

        Args:
            query: Natural-language question from the operator.

        Returns:
            Agent response text.

        Raises:
            RuntimeError: If the agent is not connected (call connect() first).
        """
        if self._agent is None or self._client is None:
            raise RuntimeError("Agent is not connected. Call connect() first.")

        thread = self._client.agents.create_thread()
        self._client.agents.create_message(
            thread_id=thread.id,
            role="user",
            content=query,
        )
        self._client.agents.create_and_process_run(
            thread_id=thread.id,
            agent_id=self._agent.id,
        )
        messages = self._client.agents.list_messages(thread_id=thread.id)
        # Return the last assistant message
        for msg in messages.data:
            if msg.role == "assistant":
                return msg.content[0].text.value if msg.content else ""
        return ""

    def close(self) -> None:
        """Clean up Azure resources."""
        if self._agent and self._client:
            try:
                self._client.agents.delete_agent(self._agent.id)
            except Exception:  # noqa: BLE001
                pass
        self._agent = None
        self._client = None
