"""Unit tests for agent configuration and tool registration.

These tests run entirely locally — no Azure resources required.
"""

from __future__ import annotations


import pytest

from agent.agent import AgentOpsAdvisor
from agent.config import AgentConfig


# ===========================================================================
# AgentConfig tests
# ===========================================================================


class TestAgentConfig:
    """Tests for AgentConfig loading and validation."""

    def test_for_testing_returns_valid_config(self):
        """AgentConfig.for_testing() returns a config with sensible defaults."""
        cfg = AgentConfig.for_testing()
        assert cfg.openai_deployment == "gpt-4.1"
        assert cfg.db_mode == "sqlite"
        assert cfg.enable_work_iq is True
        assert cfg.enable_mcp is False

    def test_for_testing_overrides_applied(self):
        """Keyword overrides in for_testing() are respected."""
        cfg = AgentConfig.for_testing(enable_work_iq=False, openai_deployment="gpt-4o")
        assert cfg.enable_work_iq is False
        assert cfg.openai_deployment == "gpt-4o"

    def test_from_env_reads_environment_variables(self, monkeypatch: pytest.MonkeyPatch):
        """AgentConfig.from_env() reads values from environment variables."""
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4-turbo")
        monkeypatch.setenv("ENABLE_WORK_IQ", "false")
        monkeypatch.setenv("ENABLE_MCP", "true")
        monkeypatch.setenv("DB_MODE", "sqlite")

        cfg = AgentConfig.from_env()
        assert cfg.openai_deployment == "gpt-4-turbo"
        assert cfg.enable_work_iq is False
        assert cfg.enable_mcp is True

    def test_has_azure_credentials_false_when_empty(self):
        """has_azure_credentials is False when connection string and endpoint are empty."""
        cfg = AgentConfig.for_testing()
        assert cfg.has_azure_credentials is False

    def test_has_azure_credentials_true_when_set(self):
        """has_azure_credentials is True when both required fields are set."""
        cfg = AgentConfig.for_testing(
            project_connection_string="eastus2.api.azureml.ms;xxx;xxx;xxx",
            openai_endpoint="https://myresource.openai.azure.com/",
        )
        assert cfg.has_azure_credentials is True

    def test_validate_passes_for_default_config(self):
        """Validation of default test config should return no errors."""
        cfg = AgentConfig.for_testing()
        errors = cfg.validate()
        assert errors == []

    def test_validate_fails_for_empty_deployment(self):
        """Validation should fail when openai_deployment is empty."""
        cfg = AgentConfig.for_testing(openai_deployment="")
        errors = cfg.validate()
        assert any("openai_deployment" in e for e in errors)

    def test_content_recording_disabled_by_default(self):
        """Content recording should be OFF by default (privacy)."""
        cfg = AgentConfig.for_testing()
        assert cfg.content_recording_enabled is False

    def test_from_env_feature_flag_variations(self, monkeypatch: pytest.MonkeyPatch):
        """Feature flags should parse '1', 'true', 'yes' as True; anything else as False."""
        for truthy in ("1", "true", "True", "TRUE", "yes"):
            monkeypatch.setenv("ENABLE_WORK_IQ", truthy)
            cfg = AgentConfig.from_env()
            assert cfg.enable_work_iq is True, f"Expected True for ENABLE_WORK_IQ={truthy!r}"

        for falsy in ("0", "false", "False", "no", "off", ""):
            monkeypatch.setenv("ENABLE_WORK_IQ", falsy)
            cfg = AgentConfig.from_env()
            assert cfg.enable_work_iq is False, f"Expected False for ENABLE_WORK_IQ={falsy!r}"


# ===========================================================================
# AgentOpsAdvisor tool registration tests
# ===========================================================================


class TestAgentToolRegistration:
    """Tests for AgentOpsAdvisor tool registration (no Azure required)."""

    def test_core_tools_always_registered(self):
        """Core tools (telemetry, propose_change, request_approval) are always present."""
        advisor = AgentOpsAdvisor(config=AgentConfig.for_testing())
        tools = advisor.get_tool_functions()
        assert "query_telemetry" in tools
        assert "propose_change" in tools
        assert "request_approval" in tools

    def test_work_iq_tools_registered_when_enabled(self):
        """Work IQ tools are present when enable_work_iq=True."""
        cfg = AgentConfig.for_testing(enable_work_iq=True)
        advisor = AgentOpsAdvisor(config=cfg)
        tools = advisor.get_tool_functions()
        assert "get_work_context" in tools
        assert "get_runbook" in tools

    def test_work_iq_tools_absent_when_disabled(self):
        """Work IQ tools are NOT present when enable_work_iq=False."""
        cfg = AgentConfig.for_testing(enable_work_iq=False)
        advisor = AgentOpsAdvisor(config=cfg)
        tools = advisor.get_tool_functions()
        assert "get_work_context" not in tools
        assert "get_runbook" not in tools

    def test_tool_functions_are_callable(self):
        """All registered tool functions should be callable."""
        advisor = AgentOpsAdvisor(config=AgentConfig.for_testing())
        tools = advisor.get_tool_functions()
        for name, fn in tools.items():
            assert callable(fn), f"Tool '{name}' is not callable"

    def test_tool_count_with_work_iq_on(self):
        """With Work IQ enabled, there should be at least 5 registered tools."""
        cfg = AgentConfig.for_testing(enable_work_iq=True)
        advisor = AgentOpsAdvisor(config=cfg)
        tools = advisor.get_tool_functions()
        assert len(tools) >= 5

    def test_tool_count_with_work_iq_off(self):
        """With Work IQ disabled, there should be exactly 3 core tools."""
        cfg = AgentConfig.for_testing(enable_work_iq=False)
        advisor = AgentOpsAdvisor(config=cfg)
        tools = advisor.get_tool_functions()
        assert len(tools) == 3


# ===========================================================================
# AgentOpsAdvisor error handling tests
# ===========================================================================


class TestAgentErrorHandling:
    """Tests for agent error handling with missing or invalid config."""

    def test_connect_raises_without_credentials(self):
        """connect() should raise RuntimeError when Azure credentials are missing."""
        advisor = AgentOpsAdvisor(config=AgentConfig.for_testing())
        with pytest.raises(RuntimeError, match="Azure credentials are not configured"):
            advisor.connect()

    def test_ask_raises_before_connect(self):
        """ask() should raise RuntimeError if the agent is not connected."""
        advisor = AgentOpsAdvisor(config=AgentConfig.for_testing())
        with pytest.raises(RuntimeError, match="not connected"):
            advisor.ask("What happened to the GPU cluster?")

    def test_close_is_safe_when_not_connected(self):
        """close() should not raise an error even if the agent was never connected."""
        advisor = AgentOpsAdvisor(config=AgentConfig.for_testing())
        advisor.close()  # Should not raise

    def test_default_config_loaded_when_none_provided(self, monkeypatch: pytest.MonkeyPatch):
        """AgentOpsAdvisor with no config arg should call AgentConfig.from_env()."""
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        advisor = AgentOpsAdvisor()
        assert advisor.config.openai_deployment == "gpt-4o-mini"

    def test_system_prompt_is_non_empty(self):
        """The system prompt should be a non-empty string."""
        assert AgentOpsAdvisor.SYSTEM_PROMPT
        assert len(AgentOpsAdvisor.SYSTEM_PROMPT) > 50
