"""Tests for the SRE Agent REST integration tool."""

from __future__ import annotations

import pytest

from tools import sre_agent


@pytest.mark.asyncio
async def test_query_sre_agent_returns_synthetic_gpu_when_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_SRE_AGENT", "false")

    result = await sre_agent.query_sre_agent("Check GPU health in prod-east")

    assert result["source"] == "synthetic"
    assert result["diagnostics"]["category"] == "gpu"
    assert "synthetic" in result["disclaimer"].lower()


@pytest.mark.asyncio
async def test_query_sre_agent_falls_back_when_url_missing(monkeypatch):
    monkeypatch.setenv("ENABLE_SRE_AGENT", "true")
    monkeypatch.delenv("SRE_AGENT_URL", raising=False)
    monkeypatch.setattr(sre_agent, "app_settings", None)

    result = await sre_agent.query_sre_agent("Investigate network packet loss")

    assert result["source"] == "synthetic"
    assert result["diagnostics"]["category"] == "network"
    assert "missing" in result["diagnostics"]["fallback_reason"].lower()


@pytest.mark.asyncio
async def test_query_sre_agent_wraps_live_payload(monkeypatch):
    monkeypatch.setenv("ENABLE_SRE_AGENT", "true")
    monkeypatch.setenv("SRE_AGENT_URL", "https://demo-sre-agent.azuresre.ai")

    async def fake_fetch_live_sre_payload(*, question: str, chat_url: str, scope: str):
        assert question == "Investigate network latency"
        assert chat_url == "https://demo-sre-agent.azuresre.ai/api/v2/chat"
        assert scope == "59f0a04a-b322-4310-adc9-39ac41e9631e/.default"
        return {
            "messages": [{"role": "assistant", "content": "Latency is elevated on the east-west peering path."}],
            "diagnostics": {"packet_loss_pct": 0.7},
        }

    monkeypatch.setattr(sre_agent, "_fetch_live_sre_payload", fake_fetch_live_sre_payload)

    result = await sre_agent.query_sre_agent("Investigate network latency")

    assert result["source"] == "live"
    assert result["response"] == "Latency is elevated on the east-west peering path."
    assert result["diagnostics"]["mode"] == "live-rest-chat"
    assert result["diagnostics"]["diagnostics"]["packet_loss_pct"] == 0.7


def test_get_sre_diagnostics_alias_name():
    assert sre_agent.get_sre_diagnostics.__name__ == "get_sre_diagnostics"
    assert sre_agent.get_sre_diagnostics.__qualname__ == "get_sre_diagnostics"
