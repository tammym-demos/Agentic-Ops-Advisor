"""Unit tests for SRE Agent configuration defaults in agent.config."""

from __future__ import annotations

from dataclasses import fields

import pytest

from agent.config import Settings

_EXPECTED_SRE_RESOURCE_ID = "59f0a04a-b322-4310-adc9-39ac41e9631e"
_HAS_SRE_FIELDS = {
    "enable_sre_agent",
    "sre_agent_url",
    "sre_agent_resource_id",
}.issubset({field.name for field in fields(Settings)})

pytestmark = pytest.mark.skipif(
    not _HAS_SRE_FIELDS,
    reason="Waiting for ENABLE_SRE_AGENT config field",
)


class TestSREAgentSettings:
    def test_enable_sre_agent_defaults_to_false(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
        monkeypatch.delenv("ENABLE_SRE_AGENT", raising=False)
        monkeypatch.delenv("SRE_AGENT_URL", raising=False)
        monkeypatch.delenv("SRE_AGENT_RESOURCE_ID", raising=False)

        settings = Settings.from_env()

        assert settings.enable_sre_agent is False

    def test_enable_sre_agent_true_enables_flag(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
        monkeypatch.setenv("ENABLE_SRE_AGENT", "true")
        monkeypatch.delenv("SRE_AGENT_URL", raising=False)
        monkeypatch.delenv("SRE_AGENT_RESOURCE_ID", raising=False)

        settings = Settings.from_env()

        assert settings.enable_sre_agent is True

    def test_sre_agent_url_defaults_to_none(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
        monkeypatch.delenv("ENABLE_SRE_AGENT", raising=False)
        monkeypatch.delenv("SRE_AGENT_URL", raising=False)
        monkeypatch.delenv("SRE_AGENT_RESOURCE_ID", raising=False)

        settings = Settings.from_env()

        assert settings.sre_agent_url is None

    def test_sre_agent_resource_id_has_expected_default(self, monkeypatch):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com/")
        monkeypatch.delenv("ENABLE_SRE_AGENT", raising=False)
        monkeypatch.delenv("SRE_AGENT_URL", raising=False)
        monkeypatch.delenv("SRE_AGENT_RESOURCE_ID", raising=False)

        settings = Settings.from_env()

        assert settings.sre_agent_resource_id == _EXPECTED_SRE_RESOURCE_ID
