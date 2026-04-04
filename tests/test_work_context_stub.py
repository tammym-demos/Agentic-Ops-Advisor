"""Unit tests for tools/work_context_stub.py."""

from __future__ import annotations

import os


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DISCLAIMER_FRAGMENT = "Work IQ pattern simulation using synthetic data"


def _reload_stub():
    """Import (or re-use) the stub module and clear its context cache."""
    import tools.work_context_stub as mod

    mod._clear_context_cache()  # reset cache between tests
    return mod


# ---------------------------------------------------------------------------
# Feature-flag tests
# ---------------------------------------------------------------------------


class TestFeatureFlag:
    def test_disabled_when_false(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WORK_IQ", "false")
        mod = _reload_stub()
        result = mod.get_work_context("change_events")
        assert result["status"] == "disabled"
        assert DISCLAIMER_FRAGMENT in result["disclaimer"]

    def test_disabled_when_zero(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WORK_IQ", "0")
        mod = _reload_stub()
        result = mod.get_work_context("ownership")
        assert result["status"] == "disabled"

    def test_disabled_when_off(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WORK_IQ", "off")
        mod = _reload_stub()
        result = mod.get_work_context("runbook")
        assert result["status"] == "disabled"

    def test_enabled_by_default(self, monkeypatch):
        monkeypatch.delenv("ENABLE_WORK_IQ", raising=False)
        mod = _reload_stub()
        result = mod.get_work_context("ownership")
        assert result["status"] == "ok"

    def test_enabled_when_true(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WORK_IQ", "true")
        mod = _reload_stub()
        result = mod.get_work_context("ownership")
        assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# Disclaimer tests
# ---------------------------------------------------------------------------


class TestDisclaimer:
    def test_disclaimer_in_ok_response(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WORK_IQ", "true")
        mod = _reload_stub()
        result = mod.get_work_context("ownership")
        assert DISCLAIMER_FRAGMENT in result["disclaimer"]

    def test_disclaimer_in_disabled_response(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WORK_IQ", "false")
        mod = _reload_stub()
        result = mod.get_work_context("ownership")
        assert DISCLAIMER_FRAGMENT in result["disclaimer"]

    def test_disclaimer_in_error_response(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WORK_IQ", "true")
        mod = _reload_stub()
        result = mod.get_work_context("invalid_type")
        assert DISCLAIMER_FRAGMENT in result["disclaimer"]


# ---------------------------------------------------------------------------
# change_events query tests
# ---------------------------------------------------------------------------


class TestChangeEvents:
    def setup_method(self):
        os.environ["ENABLE_WORK_IQ"] = "true"
        self.mod = _reload_stub()

    def test_returns_all_events_no_filter(self):
        result = self.mod.get_work_context("change_events")
        assert result["status"] == "ok"
        assert result["result_count"] > 0

    def test_service_filter(self):
        result = self.mod.get_work_context("change_events", service="gpu-scheduler")
        assert result["status"] == "ok"
        for evt in result["results"]:
            assert "gpu-scheduler" in evt["service"]

    def test_time_range_filter(self):
        result = self.mod.get_work_context(
            "change_events",
            start_time="2025-03-29T00:00:00Z",
            end_time="2025-03-30T00:00:00Z",
        )
        assert result["status"] == "ok"
        for evt in result["results"]:
            ts = evt["timestamp"]
            assert ts >= "2025-03-29T00:00:00Z"
            assert ts <= "2025-03-30T23:59:59Z"

    def test_time_range_returns_empty_for_future(self):
        result = self.mod.get_work_context(
            "change_events",
            start_time="2099-01-01T00:00:00Z",
            end_time="2099-12-31T23:59:59Z",
        )
        assert result["status"] == "ok"
        assert result["result_count"] == 0

    def test_service_and_time_filter_combined(self):
        result = self.mod.get_work_context(
            "change_events",
            service="inference-api",
            start_time="2025-03-29T00:00:00Z",
            end_time="2025-04-05T00:00:00Z",
        )
        assert result["status"] == "ok"
        for evt in result["results"]:
            assert "inference-api" in evt["service"]


# ---------------------------------------------------------------------------
# ownership query tests
# ---------------------------------------------------------------------------


class TestOwnership:
    def setup_method(self):
        os.environ["ENABLE_WORK_IQ"] = "true"
        self.mod = _reload_stub()

    def test_returns_all_owners_no_filter(self):
        result = self.mod.get_work_context("ownership")
        assert result["status"] == "ok"
        assert result["result_count"] > 0

    def test_service_filter_exact(self):
        result = self.mod.get_work_context("ownership", service="inference-api")
        assert result["status"] == "ok"
        assert result["result_count"] >= 1
        for rec in result["results"]:
            assert "inference-api" in rec["service"]

    def test_service_filter_partial(self):
        result = self.mod.get_work_context("ownership", service="gpu")
        assert result["status"] == "ok"
        assert result["result_count"] >= 1

    def test_nonexistent_service_returns_empty(self):
        result = self.mod.get_work_context("ownership", service="nonexistent-service-xyz")
        assert result["status"] == "ok"
        assert result["result_count"] == 0

    def test_ownership_record_has_required_fields(self):
        result = self.mod.get_work_context("ownership", service="gpu-scheduler")
        assert result["result_count"] >= 1
        rec = result["results"][0]
        for field in ("service", "team", "primary_owner", "slack_channel"):
            assert field in rec


# ---------------------------------------------------------------------------
# runbook query tests
# ---------------------------------------------------------------------------


class TestRunbook:
    def setup_method(self):
        os.environ["ENABLE_WORK_IQ"] = "true"
        self.mod = _reload_stub()

    def test_returns_all_runbooks_no_filter(self):
        result = self.mod.get_work_context("runbook")
        assert result["status"] == "ok"
        assert result["result_count"] > 0

    def test_service_filter(self):
        result = self.mod.get_work_context("runbook", service="gpu-scheduler")
        assert result["status"] == "ok"
        assert result["result_count"] >= 1
        for rb in result["results"]:
            assert "gpu-scheduler" in rb["service"]

    def test_keyword_filter(self):
        result = self.mod.get_work_context("runbook", topic_keywords="latency")
        assert result["status"] == "ok"
        assert result["result_count"] >= 1

    def test_multi_keyword_filter(self):
        result = self.mod.get_work_context("runbook", topic_keywords="gpu,utilization")
        assert result["status"] == "ok"
        assert result["result_count"] >= 1

    def test_runbook_has_steps(self):
        result = self.mod.get_work_context("runbook", service="gpu-scheduler")
        assert result["result_count"] >= 1
        rb = result["results"][0]
        assert "steps" in rb
        assert len(rb["steps"]) > 0

    def test_nonexistent_keyword_returns_empty(self):
        result = self.mod.get_work_context("runbook", topic_keywords="zzznomatch")
        assert result["status"] == "ok"
        assert result["result_count"] == 0


# ---------------------------------------------------------------------------
# decisions query tests
# ---------------------------------------------------------------------------


class TestDecisions:
    def setup_method(self):
        os.environ["ENABLE_WORK_IQ"] = "true"
        self.mod = _reload_stub()

    def test_returns_all_decisions_no_filter(self):
        result = self.mod.get_work_context("decisions")
        assert result["status"] == "ok"
        assert result["result_count"] > 0

    def test_service_filter(self):
        result = self.mod.get_work_context("decisions", service="gpu-scheduler")
        assert result["status"] == "ok"
        assert result["result_count"] >= 1

    def test_keyword_filter_capacity(self):
        result = self.mod.get_work_context("decisions", topic_keywords="capacity")
        assert result["status"] == "ok"
        assert result["result_count"] >= 1

    def test_time_range_filter(self):
        result = self.mod.get_work_context(
            "decisions",
            start_time="2025-03-27T00:00:00Z",
            end_time="2025-04-01T00:00:00Z",
        )
        assert result["status"] == "ok"
        assert result["result_count"] >= 1

    def test_combined_service_and_keyword(self):
        result = self.mod.get_work_context(
            "decisions",
            service="inference-api",
            topic_keywords="batching",
        )
        assert result["status"] == "ok"
        assert result["result_count"] >= 1


# ---------------------------------------------------------------------------
# Error / edge case tests
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def setup_method(self):
        os.environ["ENABLE_WORK_IQ"] = "true"
        self.mod = _reload_stub()

    def test_invalid_query_type(self):
        result = self.mod.get_work_context("bad_query_type")
        assert result["status"] == "error"
        assert DISCLAIMER_FRAGMENT in result["disclaimer"]

    def test_missing_data_file(self, monkeypatch, tmp_path):
        # Point the module at a non-existent file
        mod = _reload_stub()
        monkeypatch.setattr(mod, "_DATA_PATH", tmp_path / "does_not_exist.json")
        mod._clear_context_cache()
        result = mod.get_work_context("change_events")
        assert result["status"] == "error"
        assert DISCLAIMER_FRAGMENT in result["disclaimer"]


# ---------------------------------------------------------------------------
# Tool definition schema tests
# ---------------------------------------------------------------------------


class TestToolDefinition:
    def test_tool_definition_structure(self):
        from tools.work_context_stub import TOOL_DEFINITION

        assert TOOL_DEFINITION["type"] == "function"
        fn = TOOL_DEFINITION["function"]
        assert fn["name"] == "get_work_context"
        assert "description" in fn
        params = fn["parameters"]
        assert params["type"] == "object"
        assert "query_type" in params["properties"]
        assert "query_type" in params["required"]

    def test_enum_values_in_schema(self):
        from tools.work_context_stub import TOOL_DEFINITION

        enum_vals = TOOL_DEFINITION["function"]["parameters"]["properties"]["query_type"]["enum"]
        for expected in ("change_events", "ownership", "runbook", "decisions"):
            assert expected in enum_vals

    def test_optional_params_present(self):
        from tools.work_context_stub import TOOL_DEFINITION

        props = TOOL_DEFINITION["function"]["parameters"]["properties"]
        for param in ("service", "start_time", "end_time", "topic_keywords"):
            assert param in props
