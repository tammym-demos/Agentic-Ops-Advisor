"""Unit tests for agent.config — configuration and feature flag module."""

from __future__ import annotations

import os
import pytest

from agent.config import Settings, _get_bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REQUIRED_ENV = {
    "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/",
}


def _make_settings(**overrides: str) -> Settings:
    """Return a Settings built from the minimal required env, plus any overrides."""
    env = {**REQUIRED_ENV, **overrides}
    old = {k: os.environ.pop(k, None) for k in env}
    try:
        for k, v in env.items():
            os.environ[k] = v
        return Settings.from_env()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ---------------------------------------------------------------------------
# _get_bool helper
# ---------------------------------------------------------------------------


class TestGetBool:
    def test_missing_uses_default_true(self, monkeypatch):
        monkeypatch.delenv("SOME_FLAG", raising=False)
        assert _get_bool("SOME_FLAG", default=True) is True

    def test_missing_uses_default_false(self, monkeypatch):
        monkeypatch.delenv("SOME_FLAG", raising=False)
        assert _get_bool("SOME_FLAG", default=False) is False

    @pytest.mark.parametrize("raw", ["true", "True", "TRUE", "1", "yes", "YES"])
    def test_truthy_values(self, monkeypatch, raw):
        monkeypatch.setenv("SOME_FLAG", raw)
        assert _get_bool("SOME_FLAG", default=False) is True

    @pytest.mark.parametrize("raw", ["false", "False", "FALSE", "0", "no", "NO"])
    def test_falsy_values(self, monkeypatch, raw):
        monkeypatch.setenv("SOME_FLAG", raw)
        assert _get_bool("SOME_FLAG", default=True) is False


# ---------------------------------------------------------------------------
# Settings.from_env — required variable validation
# ---------------------------------------------------------------------------


class TestSettingsValidation:
    def test_succeeds_without_agents_endpoint(self, monkeypatch):
        """AZURE_AI_AGENTS_ENDPOINT is optional — only needed for Foundry deployments."""
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
        monkeypatch.delenv("AZURE_AI_PROJECT_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_AI_AGENTS_ENDPOINT", raising=False)
        s = Settings.from_env()
        assert s.azure_ai_agents_endpoint is None
        assert s.azure_ai_project_connection_string is None

    def test_raises_when_openai_endpoint_missing(self, monkeypatch):
        monkeypatch.setenv(
            "AZURE_AI_PROJECT_CONNECTION_STRING",
            "https://example.openai.azure.com/;project=demo",
        )
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
            Settings.from_env()

    def test_raises_when_only_required_missing(self, monkeypatch):
        monkeypatch.delenv("AZURE_AI_PROJECT_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_AI_AGENTS_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        with pytest.raises(ValueError) as exc_info:
            Settings.from_env()
        msg = str(exc_info.value)
        assert "AZURE_OPENAI_ENDPOINT" in msg

    def test_error_message_mentions_env_example(self, monkeypatch):
        monkeypatch.delenv("AZURE_AI_PROJECT_CONNECTION_STRING", raising=False)
        monkeypatch.delenv("AZURE_AI_AGENTS_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        with pytest.raises(ValueError, match=".env.example"):
            Settings.from_env()


# ---------------------------------------------------------------------------
# Settings.from_env — defaults
# ---------------------------------------------------------------------------


class TestSettingsDefaults:
    def test_db_mode_defaults_to_sqlite(self, monkeypatch):
        monkeypatch.delenv("DB_MODE", raising=False)
        s = _make_settings()
        assert s.db_mode == "sqlite"

    def test_db_connection_string_defaults_to_none(self, monkeypatch):
        monkeypatch.delenv("DB_CONNECTION_STRING", raising=False)
        s = _make_settings()
        assert s.db_connection_string is None

    def test_deployment_defaults(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_VERSION", raising=False)
        s = _make_settings()
        assert s.azure_openai_deployment == "gpt-4.1"
        assert s.azure_openai_api_version == "2025-01-01-preview"

    def test_enable_work_iq_defaults_to_true(self, monkeypatch):
        monkeypatch.delenv("ENABLE_WORK_IQ", raising=False)
        s = _make_settings()
        assert s.enable_work_iq is True

    def test_enable_mcp_defaults_to_false(self, monkeypatch):
        monkeypatch.delenv("ENABLE_MCP", raising=False)
        s = _make_settings()
        assert s.enable_mcp is False

    def test_content_recording_defaults_to_false(self, monkeypatch):
        monkeypatch.delenv("AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", raising=False)
        s = _make_settings()
        assert s.azure_tracing_gen_ai_content_recording_enabled is False

    def test_appinsights_defaults_to_none(self, monkeypatch):
        monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
        s = _make_settings()
        assert s.applicationinsights_connection_string is None


# ---------------------------------------------------------------------------
# Settings.from_env — explicit values round-trip
# ---------------------------------------------------------------------------


class TestSettingsValues:
    def test_db_mode_from_env(self):
        s = _make_settings(DB_MODE="azure_sql")
        assert s.db_mode == "azure_sql"

    def test_db_connection_string_from_env(self):
        conn = "Driver={ODBC};Server=tcp:myserver.database.windows.net"
        s = _make_settings(DB_CONNECTION_STRING=conn)
        assert s.db_connection_string == conn

    def test_feature_flags_from_env(self):
        s = _make_settings(ENABLE_WORK_IQ="false", ENABLE_MCP="true")
        assert s.enable_work_iq is False
        assert s.enable_mcp is True

    def test_content_recording_enabled(self):
        s = _make_settings(AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED="true")
        assert s.azure_tracing_gen_ai_content_recording_enabled is True

    def test_appinsights_from_env(self):
        conn = "InstrumentationKey=abc123"
        s = _make_settings(APPLICATIONINSIGHTS_CONNECTION_STRING=conn)
        assert s.applicationinsights_connection_string == conn

    def test_azure_metadata_from_env(self):
        s = _make_settings(
            AZURE_SUBSCRIPTION_ID="sub-123",
            AZURE_RESOURCE_GROUP="rg-ops",
            AZURE_LOCATION="eastus2",
        )
        assert s.azure_subscription_id == "sub-123"
        assert s.azure_resource_group == "rg-ops"
        assert s.azure_location == "eastus2"


# ---------------------------------------------------------------------------
# Frozen / immutable
# ---------------------------------------------------------------------------


class TestSettingsFrozen:
    def test_settings_are_immutable(self):
        s = _make_settings()
        with pytest.raises((AttributeError, TypeError)):
            s.db_mode = "something_else"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Singleton import
# ---------------------------------------------------------------------------


class TestSingletonImport:
    def test_settings_importable_as_module_attribute(self):
        import agent.config as cfg

        # settings may be None if env vars are absent in the test environment,
        # but the attribute must exist.
        assert hasattr(cfg, "settings")

    def test_settings_type_when_env_present(self, monkeypatch):
        for k, v in REQUIRED_ENV.items():
            monkeypatch.setenv(k, v)

        # Re-run factory directly (singleton is already built at import time)
        from agent.config import _build_settings

        result = _build_settings()
        assert isinstance(result, Settings)
