"""Centralized configuration and feature flag management for Agentic Ops Advisor."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load .env file if present (no-op when the file is absent)
load_dotenv(override=False)


def _get_bool(var: str, default: bool) -> bool:
    """Parse a boolean environment variable, accepting true/false/1/0 (case-insensitive)."""
    raw = os.getenv(var)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    """All application settings, loaded once from environment variables.

    Required variables must be set before the singleton is constructed;
    missing values raise ``ValueError`` with a clear diagnostic message.
    """

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    db_mode: str = "sqlite"
    """'sqlite' for local development, or an Azure SQL connection string."""

    db_connection_string: Optional[str] = None
    """Full ODBC/JDBC connection string used when db_mode != 'sqlite'."""

    # ------------------------------------------------------------------
    # Azure AI / OpenAI
    # ------------------------------------------------------------------
    azure_ai_agents_endpoint: Optional[str] = None
    """Azure AI Foundry project endpoint URL (v2 SDK).

    Example: https://hub-agentops-prod.services.ai.azure.com/api/projects/proj-agentops-prod
    """

    azure_ai_project_connection_string: Optional[str] = None
    """Legacy Azure AI Foundry project connection string (v1 SDK, deprecated).

    Kept for backward compatibility. If set and azure_ai_agents_endpoint is not,
    the connection string is parsed to construct the endpoint.
    """

    azure_openai_endpoint: Optional[str] = None
    """Azure OpenAI service endpoint URL."""

    azure_openai_deployment: str = "gpt-4.1"
    """Azure OpenAI model deployment name."""

    azure_openai_api_version: str = "2025-01-01-preview"
    """Azure OpenAI API version string."""

    # ------------------------------------------------------------------
    # Feature flags
    # ------------------------------------------------------------------
    enable_work_iq: bool = True
    """Enable simulated Work IQ context (default: True)."""

    enable_mcp: bool = False
    """Enable MCP wrapper for Work IQ (default: False)."""

    enable_sre_agent: bool = False
    """Enable SRE Agent integration (default: False)."""

    sre_agent_url: Optional[str] = None
    """SRE Agent endpoint URL for outbound integration."""

    sre_agent_resource_id: str = "59f0a04a-b322-4310-adc9-39ac41e9631e"
    """Azure resource ID / token audience used when authenticating to the SRE Agent."""

    mcp_require_auth: bool = True
    """Require MCP callers to present valid auth (default: True)."""

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------
    applicationinsights_connection_string: Optional[str] = None
    """Application Insights / Azure Monitor connection string."""

    azure_tracing_gen_ai_content_recording_enabled: bool = False
    """Whether to record LLM prompt/response content in traces (default: False)."""

    # ------------------------------------------------------------------
    # Azure deployment metadata (informational, not required at runtime)
    # ------------------------------------------------------------------
    azure_subscription_id: Optional[str] = None
    azure_resource_group: Optional[str] = None
    azure_location: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Settings":
        """Construct a :class:`Settings` instance by reading environment variables.

        Raises
        ------
        ValueError
            If any *required* variable is missing or empty.
        """
        # Collect missing required vars so we can surface them all at once
        missing: list[str] = []

        def _require(var: str) -> str:
            value = os.getenv(var, "").strip()
            if not value:
                missing.append(var)
            return value

        def _optional(var: str) -> Optional[str]:
            value = os.getenv(var, "").strip()
            return value if value else None

        # Required fields — must be present for the agent to function
        azure_ai_agents_endpoint = _optional("AZURE_AI_AGENTS_ENDPOINT")
        azure_ai_project_connection_string = _optional("AZURE_AI_PROJECT_CONNECTION_STRING")
        azure_openai_endpoint = _optional("AZURE_OPENAI_ENDPOINT") or ""

        # AZURE_OPENAI_ENDPOINT is required (used by AzureOpenAIChatClient).
        # AZURE_AI_AGENTS_ENDPOINT / AZURE_AI_PROJECT_CONNECTION_STRING are
        # optional — only needed for Foundry Agent Service deployments.
        if not azure_openai_endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")

        if missing:
            raise ValueError(
                "Missing required environment variable(s): "
                + ", ".join(missing)
                + ". Set them in your environment or in a .env file "
                "(see .env.example for the full list)."
            )

        return cls(
            # Database
            db_mode=os.getenv("DB_MODE", "sqlite").strip() or "sqlite",
            db_connection_string=_optional("DB_CONNECTION_STRING"),
            # Azure AI
            azure_ai_agents_endpoint=azure_ai_agents_endpoint,
            azure_ai_project_connection_string=azure_ai_project_connection_string,
            azure_openai_endpoint=azure_openai_endpoint or None,
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1").strip() or "gpt-4.1",
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview").strip()
            or "2025-01-01-preview",
            # Feature flags
            enable_work_iq=_get_bool("ENABLE_WORK_IQ", default=True),
            enable_mcp=_get_bool("ENABLE_MCP", default=False),
            enable_sre_agent=_get_bool("ENABLE_SRE_AGENT", default=False),
            sre_agent_url=_optional("SRE_AGENT_URL"),
            sre_agent_resource_id=_optional("SRE_AGENT_RESOURCE_ID")
            or "59f0a04a-b322-4310-adc9-39ac41e9631e",
            mcp_require_auth=_get_bool("MCP_REQUIRE_AUTH", default=True),
            # Observability
            applicationinsights_connection_string=_optional("APPLICATIONINSIGHTS_CONNECTION_STRING"),
            azure_tracing_gen_ai_content_recording_enabled=_get_bool(
                "AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", default=False
            ),
            # Azure deployment metadata
            azure_subscription_id=_optional("AZURE_SUBSCRIPTION_ID"),
            azure_resource_group=_optional("AZURE_RESOURCE_GROUP"),
            azure_location=_optional("AZURE_LOCATION"),
        )


def _build_settings() -> Optional[Settings]:
    """Build the singleton, returning None if required env vars are absent.

    We defer raising so that modules can be *imported* without env vars being
    set (e.g., during unit-test collection), and the error surfaces only when
    ``settings`` is actually *used*.
    """
    try:
        return Settings.from_env()
    except ValueError:
        # Return a sentinel; callers that access settings will get None and
        # should call Settings.from_env() explicitly with their own env vars.
        return None


# ---------------------------------------------------------------------------
# Singleton — import with:  from agent.config import settings
# ---------------------------------------------------------------------------
settings: Optional[Settings] = _build_settings()

__all__ = ["Settings", "settings"]
