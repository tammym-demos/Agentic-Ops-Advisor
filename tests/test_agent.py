"""Unit tests for agent configuration loading and AgentOpsAdvisor tool registration.

These tests run entirely locally — no Azure resources required.
"""

from __future__ import annotations

import pytest

from agent.agent import AgentOpsAdvisor
from agent.config import Settings, _get_bool


# ===========================================================================
# Settings / configuration tests
# ===========================================================================


class TestSettingsDefaults:
    """Tests for Settings default values (instantiated directly)."""

    def test_deployment_defaults(self):
        """Default deployment should be gpt-4.1."""
        s = Settings(
            azure_ai_project_connection_string="https://test.openai.azure.com/;project=test",
            azure_openai_endpoint="https://test.openai.azure.com/",
        )
        assert s.azure_openai_deployment == "gpt-4.1"

    def test_enable_work_iq_defaults_to_true(self, monkeypatch):
        """ENABLE_WORK_IQ should default to True when the env var is absent."""
        monkeypatch.delenv("ENABLE_WORK_IQ", raising=False)
        monkeypatch.setenv("AZURE_AI_PROJECT_CONNECTION_STRING", "conn")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        s = Settings.from_env()
        assert s.enable_work_iq is True

    def test_enable_mcp_defaults_to_false(self, monkeypatch):
        """ENABLE_MCP should default to False when the env var is absent."""
        monkeypatch.delenv("ENABLE_MCP", raising=False)
        monkeypatch.setenv("AZURE_AI_PROJECT_CONNECTION_STRING", "conn")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        s = Settings.from_env()
        assert s.enable_mcp is False

    def test_content_recording_disabled_by_default(self, monkeypatch):
        """Content recording should be OFF by default (privacy)."""
        monkeypatch.delenv("AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", raising=False)
        monkeypatch.setenv("AZURE_AI_PROJECT_CONNECTION_STRING", "conn")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        s = Settings.from_env()
        assert s.azure_tracing_gen_ai_content_recording_enabled is False


class TestSettingsFromEnv:
    """Tests for Settings.from_env() — reading from environment variables."""

    def test_raises_when_project_connection_missing(self, monkeypatch):
        """from_env() should raise ValueError if AZURE_AI_PROJECT_CONNECTION_STRING is absent."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.delenv("AZURE_AI_PROJECT_CONNECTION_STRING", raising=False)
        with pytest.raises(ValueError, match="AZURE_AI_PROJECT_CONNECTION_STRING"):
            Settings.from_env()

    def test_raises_when_openai_endpoint_missing(self, monkeypatch):
        """from_env() should raise ValueError if AZURE_OPENAI_ENDPOINT is absent."""
        monkeypatch.setenv("AZURE_AI_PROJECT_CONNECTION_STRING", "conn")
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
            Settings.from_env()

    def test_feature_flags_read_from_env(self, monkeypatch):
        """Feature flag env vars should be read correctly."""
        monkeypatch.setenv("AZURE_AI_PROJECT_CONNECTION_STRING", "conn")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("ENABLE_WORK_IQ", "false")
        monkeypatch.setenv("ENABLE_MCP", "true")
        s = Settings.from_env()
        assert s.enable_work_iq is False
        assert s.enable_mcp is True

    def test_deployment_read_from_env(self, monkeypatch):
        """AZURE_OPENAI_DEPLOYMENT should be read from env."""
        monkeypatch.setenv("AZURE_AI_PROJECT_CONNECTION_STRING", "conn")
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        s = Settings.from_env()
        assert s.azure_openai_deployment == "gpt-4o-mini"


class TestGetBoolHelper:
    """Tests for the _get_bool helper used by Settings."""

    def test_truthy_values(self, monkeypatch):
        """'true', '1', 'yes' should all parse as True."""
        for val in ("true", "True", "TRUE", "1", "yes"):
            monkeypatch.setenv("TEST_FLAG", val)
            assert _get_bool("TEST_FLAG", default=False) is True

    def test_falsy_values(self, monkeypatch):
        """'false', '0', 'no' should all parse as False."""
        for val in ("false", "False", "FALSE", "0", "no"):
            monkeypatch.setenv("TEST_FLAG", val)
            assert _get_bool("TEST_FLAG", default=True) is False

    def test_missing_uses_default(self, monkeypatch):
        """Missing env var should return the provided default."""
        monkeypatch.delenv("TEST_FLAG", raising=False)
        assert _get_bool("TEST_FLAG", default=True) is True
        assert _get_bool("TEST_FLAG", default=False) is False


# ===========================================================================
# AgentOpsAdvisor tool registration tests
# ===========================================================================


class TestAgentToolRegistration:
    """Tests for AgentOpsAdvisor tool registration (no Azure required)."""

    def _make_settings(self, **kwargs) -> Settings:
        base = {
            "azure_ai_project_connection_string": "https://test.openai.azure.com/;project=test",
            "azure_openai_endpoint": "https://test.openai.azure.com/",
        }
        base.update(kwargs)
        return Settings(**base)

    def test_core_tools_always_registered(self):
        """Core tools (telemetry, propose_change, request_approval) are always present."""
        advisor = AgentOpsAdvisor(config=self._make_settings())
        tools = advisor.get_tool_functions()
        assert "query_telemetry" in tools
        assert "propose_change" in tools
        assert "request_approval" in tools

    def test_work_iq_tools_registered_when_enabled(self):
        """Work IQ tools are present when enable_work_iq=True."""
        advisor = AgentOpsAdvisor(config=self._make_settings(enable_work_iq=True))
        tools = advisor.get_tool_functions()
        assert "get_change_events" in tools
        assert "get_decisions" in tools
        assert "get_ownership" in tools
        assert "get_runbooks" in tools
        assert "get_full_context" in tools

    def test_work_iq_tools_absent_when_disabled(self):
        """Work IQ tools are NOT present when enable_work_iq=False."""
        advisor = AgentOpsAdvisor(config=self._make_settings(enable_work_iq=False))
        tools = advisor.get_tool_functions()
        assert "get_change_events" not in tools
        assert "get_decisions" not in tools

    def test_all_tool_functions_are_callable(self):
        """All registered tool functions should be callable."""
        advisor = AgentOpsAdvisor(config=self._make_settings())
        for name, fn in advisor.get_tool_functions().items():
            assert callable(fn), f"Tool '{name}' is not callable"

    def test_tool_count_with_work_iq_on(self):
        """With Work IQ enabled, there should be at least 8 registered tools (3 core + 5 Work IQ)."""
        advisor = AgentOpsAdvisor(config=self._make_settings(enable_work_iq=True))
        tools = advisor.get_tool_functions()
        assert len(tools) >= 8

    def test_tool_count_with_work_iq_off(self):
        """With Work IQ disabled, there should be exactly 3 core tools."""
        advisor = AgentOpsAdvisor(config=self._make_settings(enable_work_iq=False))
        tools = advisor.get_tool_functions()
        assert len(tools) == 3


# ===========================================================================
# AgentOpsAdvisor error handling tests
# ===========================================================================


class TestAgentErrorHandling:
    """Tests for agent error handling with missing or invalid configuration."""

    def test_connect_raises_without_credentials(self):
        """connect() should raise RuntimeError when Azure credentials are empty."""
        advisor = AgentOpsAdvisor(
            config=Settings(
                azure_ai_project_connection_string=None,
                azure_openai_endpoint=None,
            )
        )
        with pytest.raises(RuntimeError, match="Azure credentials are not configured"):
            advisor.connect()

    def test_ask_raises_before_connect(self):
        """ask() should raise RuntimeError if the agent is not connected."""
        advisor = AgentOpsAdvisor(
            config=Settings(
                azure_ai_project_connection_string="conn",
                azure_openai_endpoint="https://test.openai.azure.com/",
            )
        )
        with pytest.raises(RuntimeError, match="not connected"):
            advisor.ask("What happened to the GPU cluster?")

    def test_close_is_safe_when_not_connected(self):
        """close() should not raise an error even if the agent was never connected."""
        advisor = AgentOpsAdvisor(
            config=Settings(
                azure_ai_project_connection_string="conn",
                azure_openai_endpoint="https://test.openai.azure.com/",
            )
        )
        advisor.close()  # Should not raise

    def test_system_prompt_is_non_empty(self):
        """The system prompt should be a non-empty string with meaningful content."""
        assert AgentOpsAdvisor.SYSTEM_PROMPT
        assert len(AgentOpsAdvisor.SYSTEM_PROMPT) > 50
        assert "Confidence" in AgentOpsAdvisor.SYSTEM_PROMPT
