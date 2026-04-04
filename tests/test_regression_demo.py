"""Tests for scripts/run_regression_demo.py.

These tests exercise the core logic of the regression demo without
producing terminal output or requiring any Azure credentials.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Add the repo root so that `scripts` is importable even when running from
# outside the package (e.g. `pytest tests/` from the repo root).
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_regression_demo import (  # noqa: E402
    EVALUATORS,
    TEST_CASES,
    CorrectnessEvaluator,
    EvidenceQualityEvaluator,
    GroundednessEvaluator,
    RegressionDemo,
    SafetyEvaluator,
    ToolCallSimulator,
    _aggregate,
    run_eval_suite,
    simulate_agent_response,
)


# ── ToolCallSimulator ─────────────────────────────────────────────────────────


class TestToolCallSimulator:
    def test_sql_telemetry_returns_rows_by_default(self) -> None:
        sim = ToolCallSimulator()
        result = sim.call_sql_telemetry("GPU utilization query")
        assert "rows" in result
        assert len(result["rows"]) > 0

    def test_sql_telemetry_raises_after_break(self) -> None:
        sim = ToolCallSimulator()
        sim.break_sql_telemetry()
        with pytest.raises(RuntimeError, match="OperationalError"):
            sim.call_sql_telemetry("any query")

    def test_fix_restores_sql_telemetry(self) -> None:
        sim = ToolCallSimulator()
        sim.break_sql_telemetry()
        sim.fix_sql_telemetry()
        # Should not raise
        result = sim.call_sql_telemetry("GPU utilization query")
        assert result["rows"]

    def test_is_sql_broken_flag(self) -> None:
        sim = ToolCallSimulator()
        assert sim.is_sql_broken is False
        sim.break_sql_telemetry("test reason")
        assert sim.is_sql_broken is True
        assert "test reason" in sim.break_reason
        sim.fix_sql_telemetry()
        assert sim.is_sql_broken is False

    def test_work_context_returns_change_events(self) -> None:
        sim = ToolCallSimulator()
        ctx = sim.call_work_context("inference-svc")
        assert "change_events" in ctx
        assert len(ctx["change_events"]) > 0

    def test_action_stub_returns_proposal(self) -> None:
        sim = ToolCallSimulator()
        result = sim.call_action_stub("scale GPU cluster")
        assert result["status"] == "pending_approval"
        assert "proposal_id" in result


# ── Evaluators ────────────────────────────────────────────────────────────────


class TestEvaluators:
    def setup_method(self) -> None:
        self.sim = ToolCallSimulator()
        self.tc = TEST_CASES[0]  # GPU utilization drop

    def _make_tool_outputs(self, broken: bool = False) -> dict:
        if broken:
            return {"sql_error": "OperationalError: no such column", "change_events": []}
        return {
            "sql_rows": [{"utilization_pct": 12.3}],
            "anomaly": "utilization_drop",
            "change_events": [{"description": "driver update"}],
        }

    def test_correctness_high_when_themes_present(self) -> None:
        ev = CorrectnessEvaluator()
        response = "GPU utilization anomaly detected — utilization dropped below threshold."
        result = ev(tc=self.tc, response=response, tool_outputs=self._make_tool_outputs())
        assert result.score >= 0.7
        assert result.passed

    def test_correctness_zero_when_sql_broken(self) -> None:
        ev = CorrectnessEvaluator()
        result = ev(tc=self.tc, response="I cannot provide analysis.", tool_outputs=self._make_tool_outputs(broken=True))
        assert result.score == 0.0
        assert not result.passed

    def test_evidence_full_score_with_both_sources(self) -> None:
        ev = EvidenceQualityEvaluator()
        result = ev(tc=self.tc, response="", tool_outputs=self._make_tool_outputs())
        assert result.score == 1.0

    def test_evidence_zero_when_sql_broken(self) -> None:
        ev = EvidenceQualityEvaluator()
        result = ev(tc=self.tc, response="", tool_outputs=self._make_tool_outputs(broken=True))
        assert result.score == 0.0

    def test_safety_passes_clean_response(self) -> None:
        ev = SafetyEvaluator()
        result = ev(tc=self.tc, response="Recommend GPU drain. Risk: medium.", tool_outputs={})
        assert result.score == 1.0
        assert result.passed

    def test_safety_fails_on_unsafe_pattern(self) -> None:
        ev = SafetyEvaluator()
        result = ev(tc=self.tc, response="Run: sudo rm -rf /var/log", tool_outputs={})
        assert result.score == 0.0
        assert not result.passed

    def test_groundedness_high_when_sql_healthy(self) -> None:
        ev = GroundednessEvaluator()
        result = ev(tc=self.tc, response="Telemetry shows drop.", tool_outputs=self._make_tool_outputs())
        assert result.score >= 0.7

    def test_groundedness_partial_when_sql_broken_no_hallucination(self) -> None:
        ev = GroundednessEvaluator()
        result = ev(
            tc=self.tc,
            response="I could not retrieve data due to a tool error.",
            tool_outputs=self._make_tool_outputs(broken=True),
        )
        assert result.score == 0.5  # hedged appropriately

    def test_groundedness_zero_on_hallucination(self) -> None:
        ev = GroundednessEvaluator()
        result = ev(
            tc=self.tc,
            response="The data shows exactly 12% utilization was recorded.",
            tool_outputs=self._make_tool_outputs(broken=True),
        )
        assert result.score == 0.0

    def test_all_evaluators_registered(self) -> None:
        assert set(EVALUATORS.keys()) == {"correctness", "evidence_quality", "safety", "groundedness"}

    def test_evaluators_have_id_attribute(self) -> None:
        for name, cls in EVALUATORS.items():
            instance = cls()
            assert instance.id == name


# ── simulate_agent_response ───────────────────────────────────────────────────


class TestSimulateAgentResponse:
    def test_healthy_response_contains_themes(self) -> None:
        sim = ToolCallSimulator()
        tc = TEST_CASES[0]
        response, tool_outputs, latency_ms, trace_id = simulate_agent_response(tc, sim)
        assert "gpu" in response.lower() or "anomaly" in response.lower()
        assert "sql_rows" in tool_outputs
        assert latency_ms > 0
        assert len(trace_id) == 16

    def test_broken_response_is_error_message(self) -> None:
        sim = ToolCallSimulator()
        sim.break_sql_telemetry()
        tc = TEST_CASES[0]
        response, tool_outputs, _, _ = simulate_agent_response(tc, sim)
        assert "sql_error" in tool_outputs
        assert "tool error" in response.lower()


# ── run_eval_suite ────────────────────────────────────────────────────────────


class TestRunEvalSuite:
    def test_baseline_all_pass(self) -> None:
        sim = ToolCallSimulator()
        results = run_eval_suite(sim)
        assert len(results) == len(TEST_CASES)
        assert all(r.passed for r in results), "Baseline should have all test cases passing"

    def test_broken_suite_has_failures(self) -> None:
        sim = ToolCallSimulator()
        sim.break_sql_telemetry()
        results = run_eval_suite(sim)
        assert any(not r.passed for r in results), "Broken tool should cause eval failures"

    def test_fixed_suite_recovers(self) -> None:
        sim = ToolCallSimulator()
        sim.break_sql_telemetry()
        sim.fix_sql_telemetry()
        results = run_eval_suite(sim)
        assert all(r.passed for r in results), "After fix, all test cases should pass again"

    def test_scores_drop_when_broken(self) -> None:
        sim = ToolCallSimulator()
        baseline = run_eval_suite(sim)
        sim.break_sql_telemetry()
        broken = run_eval_suite(sim)

        agg_baseline = _aggregate(baseline)
        agg_broken = _aggregate(broken)

        # Correctness and evidence_quality should regress
        assert agg_broken["correctness"] < agg_baseline["correctness"]
        assert agg_broken["evidence_quality"] < agg_baseline["evidence_quality"]

    def test_each_run_has_four_scores(self) -> None:
        sim = ToolCallSimulator()
        results = run_eval_suite(sim)
        for run in results:
            assert len(run.scores) == len(EVALUATORS)


# ── _aggregate ────────────────────────────────────────────────────────────────


class TestAggregate:
    def test_empty_returns_empty(self) -> None:
        assert _aggregate([]) == {}

    def test_mean_correctness(self) -> None:
        sim = ToolCallSimulator()
        results = run_eval_suite(sim)
        agg = _aggregate(results)
        assert 0.0 <= agg["correctness"] <= 1.0
        assert 0.0 <= agg["safety"] <= 1.0


# ── RegressionDemo integration ────────────────────────────────────────────────


class TestRegressionDemo:
    """Integration-level tests that run the full demo in auto mode with a zero delay."""

    def test_full_demo_returns_zero(self) -> None:
        demo = RegressionDemo(auto=True, step_delay=0.0)
        exit_code = demo.run()
        assert exit_code == 0

    def test_baseline_all_pass_after_step1(self) -> None:
        demo = RegressionDemo(auto=True, step_delay=0.0)
        demo.step_1_baseline()
        assert len(demo.baseline) == len(TEST_CASES)
        assert all(r.passed for r in demo.baseline)

    def test_broken_results_populated_after_step3(self) -> None:
        demo = RegressionDemo(auto=True, step_delay=0.0)
        demo.step_1_baseline()
        demo.step_2_introduce_regression()
        demo.step_3_detect_regression()
        assert len(demo.broken) == len(TEST_CASES)
        # At least some failures expected
        assert any(not r.passed for r in demo.broken)

    def test_fixed_results_recover_after_step6(self) -> None:
        demo = RegressionDemo(auto=True, step_delay=0.0)
        demo.step_1_baseline()
        demo.step_2_introduce_regression()
        demo.step_3_detect_regression()
        demo.step_4_show_observability()
        demo.step_5_apply_fix()
        demo.step_6_verify_recovery()

        passed_baseline = sum(1 for r in demo.baseline if r.passed)
        passed_fixed = sum(1 for r in demo.fixed if r.passed)
        assert passed_fixed >= passed_baseline

    def test_tool_broken_after_step2(self) -> None:
        demo = RegressionDemo(auto=True, step_delay=0.0)
        demo.step_1_baseline()
        demo.step_2_introduce_regression()
        assert demo.tool_sim.is_sql_broken is True

    def test_tool_fixed_after_step5(self) -> None:
        demo = RegressionDemo(auto=True, step_delay=0.0)
        demo.step_1_baseline()
        demo.step_2_introduce_regression()
        demo.step_3_detect_regression()
        demo.step_4_show_observability()
        demo.step_5_apply_fix()
        assert demo.tool_sim.is_sql_broken is False

    def test_step_durations_recorded(self) -> None:
        demo = RegressionDemo(auto=True, step_delay=0.0)
        demo.run()
        # 6 steps means 6 durations
        assert len(demo._step_durations) == 6  # noqa: SLF001
        assert all(d >= 0 for d in demo._step_durations)
