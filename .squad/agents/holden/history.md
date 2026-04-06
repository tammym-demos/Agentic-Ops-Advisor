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

### 2026-04-07: Infrastructure Alignment Review (Bicep vs Live Resources)
- **Context:** All 50 deploy runs failed with `invalid_engine_error: Failed to resolve model info`. Tammy requested architecture review of Bicep templates vs live infrastructure.
- **Root cause:** **Critical mismatch** — Bicep defines ML workspace-based Hub (`Microsoft.MachineLearningServices/workspaces`) + standalone OpenAI resource, but live Hub is `Microsoft.CognitiveServices/accounts` (AIServices) with native `gpt-4.1` deployment.
- **Risk:** If Bicep deploy runs now, it will create orphaned resources or fail with name collision. Agent can't discover model because it's looking on wrong Hub/resource.
- **Evidence:**
  - `infra/modules/aifoundry.bicep` line 93: Creates Hub as MachineLearningServices workspace (kind: Hub)
  - `infra/modules/openai.bicep` line 16: Creates standalone CognitiveServices resource `oai-agentops-prod` with `gpt-4.1`
  - deploy.yml line 212, 328: References `Microsoft.CognitiveServices/accounts/hub-agentops-prod` (live Hub is CognitiveServices, not ML workspace)
  - deploy.yml line 36 header: Documents that Hub is CognitiveServices, NOT MachineLearningServices
- **Analysis:** Wrote comprehensive review to `.squad/decisions/inbox/holden-infra-alignment-review.md` covering:
  - Architecture gap (Bicep vs reality)
  - Failure mode analysis (why model discovery fails)
  - Risk assessment (what happens if Bicep runs)
  - Three options: (1) Fix Bicep to match reality (4-6h), (2) Skip Bicep for AI resources + document manual setup (1-2h), (3) Tear down and rebuild (not recommended)
  - `from __future__ import annotations` risk assessment (verdict: low risk, current code is safe)
- **Recommendation:** **Hard-stop Bicep deploy** until IaC aligned. Option 1 (fix Bicep) preferred for long-term, Option 2 (skip + document) fastest to unblock Amos.
- **Assignment:** Tammy to decide Option 1 vs 2; Naomi (Backend) for Option 1 implementation, Amos (DevOps) for Option 2 gating.
- **Blocks:** Entire deploy pipeline until alignment resolved. Amos can't fix model reference until we know which endpoint/resource to target.
- **Cross-team note:** Amos's deploy.yml fix (commit `8ea32f7`) added model deployment diagnostics (Step 5c) that will expose the deployment name mismatch on next run. His non-fatal smoke test and hardened error handling complement this review. Final resolution depends on infrastructure alignment decision (Option 1: rewrite Bicep, Option 2: skip Bicep for AI).
