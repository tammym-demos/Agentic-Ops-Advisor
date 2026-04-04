"""Agent configuration — loads settings from environment variables with sensible defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class AgentConfig:
    """All configuration needed to instantiate the AgentOpsAdvisor."""

    # Azure AI Foundry / OpenAI
    project_connection_string: str = field(default="")
    openai_endpoint: str = field(default="")
    openai_deployment: str = field(default="gpt-4.1")
    openai_api_version: str = field(default="2025-01-01-preview")

    # Database
    db_mode: str = field(default="sqlite")  # "sqlite" or Azure SQL connection string
    sqlite_db_path: str = field(default="agentops.db")

    # Feature flags
    enable_work_iq: bool = field(default=True)
    enable_mcp: bool = field(default=False)

    # Observability
    app_insights_connection_string: str = field(default="")
    content_recording_enabled: bool = field(default=False)

    @classmethod
    def from_env(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        return cls(
            project_connection_string=os.environ.get("AZURE_AI_PROJECT_CONNECTION_STRING", ""),
            openai_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            openai_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1"),
            openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
            db_mode=os.environ.get("DB_MODE", "sqlite"),
            sqlite_db_path=os.environ.get("SQLITE_DB_PATH", "agentops.db"),
            enable_work_iq=os.environ.get("ENABLE_WORK_IQ", "true").lower() in ("1", "true", "yes"),
            enable_mcp=os.environ.get("ENABLE_MCP", "false").lower() in ("1", "true", "yes"),
            app_insights_connection_string=os.environ.get(
                "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
            ),
            content_recording_enabled=os.environ.get(
                "AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", "false"
            ).lower()
            in ("1", "true", "yes"),
        )

    @classmethod
    def for_testing(cls, **overrides) -> "AgentConfig":
        """Return a config instance suitable for unit tests (no Azure credentials needed)."""
        defaults = {
            "project_connection_string": "",
            "openai_endpoint": "",
            "openai_deployment": "gpt-4.1",
            "db_mode": "sqlite",
            "sqlite_db_path": ":memory:",
            "enable_work_iq": True,
            "enable_mcp": False,
            "app_insights_connection_string": "",
            "content_recording_enabled": False,
        }
        defaults.update(overrides)
        return cls(**defaults)

    @property
    def has_azure_credentials(self) -> bool:
        """True if Azure AI project credentials are configured."""
        return bool(self.project_connection_string and self.openai_endpoint)

    def validate(self) -> list[str]:
        """Return a list of validation error messages (empty = valid)."""
        errors: list[str] = []
        if not self.openai_deployment:
            errors.append("openai_deployment must not be empty")
        if self.db_mode not in ("sqlite",) and not self.db_mode.startswith("Driver="):
            # db_mode should be "sqlite" or an ODBC connection string
            errors.append(
                "db_mode must be 'sqlite' or a valid ODBC connection string"
            )
        return errors
