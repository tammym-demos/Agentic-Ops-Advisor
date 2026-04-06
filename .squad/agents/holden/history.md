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

### 2025-07-25: Deploy RBAC Issue Triage (Issue #65)
- **Context:** Deploy run #34 failed with RBAC error — service principal lacks `Microsoft.CognitiveServices/accounts/AIServices/agents/read` data-plane action.
- **Root cause:** Contributor role is management-plane only; Azure AI Foundry Agent Service requires Azure AI Developer role for data-plane access.
- **Action:** Created GitHub issue #65 documenting the manual prerequisite (one-time `az role assignment create` command) and noting that Amos is automating this in deploy.yml/deploy.sh.
- **Blocks:** Issue #62 (integration testing against real ACR).
- **Why:** Clear separation of concerns — team lead documents the infrastructure gap, Amos implements the automation fix, owner runs the manual RBAC setup.

### 2026-04-06: RBAC Fix Completed — Amos (DevOps)
- **Outcome:** ✅ Automated RBAC fix merged in commit `0ba8ec6`.
- **Changes:** 
  - `.github/workflows/deploy.yml` — Step 5c: best-effort RBAC assignment for Deploy SP + Managed Identity (uses `continue-on-error: true`; SP lacks `Microsoft.Authorization/roleAssignments/write` so can't self-assign)
  - `infra/deploy.sh` — Step 6 (pre-flight): RBAC assignment that succeeds when run locally by Owner
  - Header documentation added with role IDs and scope references
- **Admin action required:** One-time role assignment by Owner/User Access Administrator (CLI command in issue #65).
- **Risk:** Low — role assignments are idempotent, CI workflow never breaks.
- **Status:** Deploy workflow can now progress. Awaiting manual RBAC grant before first deploy run.
