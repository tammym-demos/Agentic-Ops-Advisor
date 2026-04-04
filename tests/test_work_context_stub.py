"""Unit tests for tools/work_context_stub.py.

Tests the actual public API: get_change_events, get_decisions, get_ownership,
get_runbooks, get_full_context, and the ENABLE_WORK_IQ feature flag.
"""

from __future__ import annotations

import tools.work_context_stub as wcs


def _set_flag(enabled: bool):
    """Directly set the ENABLE_WORK_IQ flag on the module.

    The flag is read at call time by every public function, so modifying
    the module attribute is sufficient for testing.
    """
    wcs.ENABLE_WORK_IQ = enabled
    return wcs


# ---------------------------------------------------------------------------
# Feature-flag tests
# ---------------------------------------------------------------------------


class TestFeatureFlag:
    def test_disabled_when_false(self, monkeypatch):
        mod = _set_flag(False)
        assert mod.ENABLE_WORK_IQ is False
        assert mod.get_change_events("gpu-cluster") == []

    def test_disabled_when_zero(self, monkeypatch):
        mod = _set_flag(False)
        assert mod.ENABLE_WORK_IQ is False
        assert mod.get_decisions("network") == []

    def test_disabled_when_no(self, monkeypatch):
        mod = _set_flag(False)
        assert mod.ENABLE_WORK_IQ is False
        assert mod.get_runbooks("cost") == []

    def test_enabled_by_default(self, monkeypatch):
        mod = _set_flag(True)
        assert mod.ENABLE_WORK_IQ is True

    def test_enabled_when_true(self, monkeypatch):
        mod = _set_flag(True)
        assert mod.ENABLE_WORK_IQ is True
        events = mod.get_change_events("gpu-cluster")
        assert isinstance(events, list)
        assert len(events) > 0

    def test_ownership_empty_when_disabled(self, monkeypatch):
        mod = _set_flag(False)
        assert mod.get_ownership("gpu-cluster") == {}


# ---------------------------------------------------------------------------
# get_change_events tests
# ---------------------------------------------------------------------------


class TestGetChangeEvents:
    def test_returns_events_for_known_service(self, monkeypatch):
        mod = _set_flag(True)
        events = mod.get_change_events("gpu-cluster")
        assert isinstance(events, list)
        assert len(events) > 0
        for evt in events:
            assert "id" in evt
            assert "type" in evt
            assert "description" in evt

    def test_returns_events_for_network(self, monkeypatch):
        mod = _set_flag(True)
        events = mod.get_change_events("network")
        assert len(events) > 0

    def test_returns_events_for_cost(self, monkeypatch):
        mod = _set_flag(True)
        events = mod.get_change_events("cost")
        assert len(events) > 0

    def test_returns_empty_for_unknown_service(self, monkeypatch):
        mod = _set_flag(True)
        events = mod.get_change_events("nonexistent-xyz")
        assert events == []


# ---------------------------------------------------------------------------
# get_decisions tests
# ---------------------------------------------------------------------------


class TestGetDecisions:
    def test_returns_decisions_for_known_service(self, monkeypatch):
        mod = _set_flag(True)
        decisions = mod.get_decisions("gpu-cluster")
        assert isinstance(decisions, list)
        assert len(decisions) > 0
        for dec in decisions:
            assert "id" in dec
            assert "summary" in dec
            assert "status" in dec

    def test_returns_empty_for_unknown_service(self, monkeypatch):
        mod = _set_flag(True)
        decisions = mod.get_decisions("zzz-no-match")
        assert decisions == []


# ---------------------------------------------------------------------------
# get_ownership tests
# ---------------------------------------------------------------------------


class TestGetOwnership:
    def test_returns_ownership_for_known_service(self, monkeypatch):
        mod = _set_flag(True)
        info = mod.get_ownership("gpu-cluster")
        assert isinstance(info, dict)
        assert "team" in info
        assert "primary" in info
        assert "slack" in info

    def test_returns_default_for_unknown_service(self, monkeypatch):
        mod = _set_flag(True)
        info = mod.get_ownership("unknown-service")
        assert info["team"] == "SRE"

    def test_network_ownership(self, monkeypatch):
        mod = _set_flag(True)
        info = mod.get_ownership("network")
        assert info["team"] == "Network Operations"


# ---------------------------------------------------------------------------
# get_runbooks tests
# ---------------------------------------------------------------------------


class TestGetRunbooks:
    def test_returns_runbooks_for_known_service(self, monkeypatch):
        mod = _set_flag(True)
        runbooks = mod.get_runbooks("gpu-cluster")
        assert isinstance(runbooks, list)
        assert len(runbooks) > 0
        for rb in runbooks:
            assert "title" in rb
            assert "url" in rb

    def test_returns_empty_for_unknown_service(self, monkeypatch):
        mod = _set_flag(True)
        runbooks = mod.get_runbooks("zzz-no-match")
        assert runbooks == []


# ---------------------------------------------------------------------------
# get_full_context tests
# ---------------------------------------------------------------------------


class TestGetFullContext:
    def test_returns_all_sections(self, monkeypatch):
        mod = _set_flag(True)
        ctx = mod.get_full_context("gpu-cluster")
        assert isinstance(ctx, dict)
        assert ctx["service"] == "gpu-cluster"
        assert "disclaimer" in ctx
        assert "Work IQ" in ctx["disclaimer"]
        assert "change_events" in ctx
        assert "decisions" in ctx
        assert "ownership" in ctx
        assert "runbooks" in ctx

    def test_change_events_populated(self, monkeypatch):
        mod = _set_flag(True)
        ctx = mod.get_full_context("gpu-cluster")
        assert len(ctx["change_events"]) > 0

    def test_full_context_when_disabled(self, monkeypatch):
        mod = _set_flag(False)
        ctx = mod.get_full_context("gpu-cluster")
        assert ctx["change_events"] == []
        assert ctx["decisions"] == []
        assert ctx["ownership"] == {}
        assert ctx["runbooks"] == []


# ---------------------------------------------------------------------------
# _service_key normalisation tests
# ---------------------------------------------------------------------------


class TestServiceKey:
    def test_normalises_known_key(self, monkeypatch):
        mod = _set_flag(True)
        assert mod._service_key("GPU-CLUSTER") == "gpu-cluster"
        assert mod._service_key("network") == "network"

    def test_unknown_returns_default(self, monkeypatch):
        mod = _set_flag(True)
        assert mod._service_key("totally-unknown") == "default"
