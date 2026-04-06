# Holden — History

## Core Context
- **Project:** Agentic Ops Advisor — governed AI agent for infrastructure telemetry reasoning
- **Stack:** Python 3.11, Azure AI Agent Service SDK, GPT-4.1, Bicep, OpenTelemetry
- **Repo:** tammym-demos/Agentic-Ops-Advisor
- **User:** Tammy
- **Status:** All 22 PRs merged. Remaining: tests, Azure deployment, integration test.

## Learnings

### 2025-07-25: DoD Audit (Issue #54)
- Audited all 7 Definition of Done criteria from `customerfriendly-plan.md` Section 8.
- **5 PASS, 2 PARTIAL.** Core agent code, eval pipeline, tracing, deployment IaC, regression demo, and synthetic data posture are all solid.
- **Gap 1:** Demo mode (`run_local.py`) doesn't call the work-context stub — only Agent mode does. Small fix needed.
- **Gap 2:** Test suite is broken (62 failures, 31 errors) — all test-layer mismatches, zero source bugs. Alex diagnosed; needs Naomi to fix.
- **Gap 3:** GitHub Pages site exists (`docs/`) but no evidence it's deployed. Need to verify or add a workflow.
- Decision written to `.squad/decisions/inbox/holden-dod-audit.md`.
- Recommendation: #54 stays open until test suite passes, demo-mode work-context is wired, and Pages is verified. ~3-4h effort.
