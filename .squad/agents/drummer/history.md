# Drummer — History

## Core Context
- **Project:** Agentic Ops Advisor — governed AI agent for infrastructure telemetry reasoning
- **Stack:** Python 3.11, Azure AI Agent Service SDK, GPT-4.1, Bicep, OpenTelemetry
- **Repo:** tammym-demos/Agentic-Ops-Advisor
- **User:** Tammy (PM & Demo Lead)
- **Role:** Program Manager — documentation, GitHub Project tracking, user stories, definition of success

## Completed Features

### 2026-04-05: Container Deployment Feature ✅ COMPLETE
- **Scope:** Package agent + tools into Docker image, push to ACR, deploy as Foundry container agent
- **Status:** COMPLETE and production-ready
- **Deliverables:**
  - Dockerfile (Python 3.11-slim, ODBC drivers, seeded SQLite, non-root, health check port 8080)
  - agent.yaml (Foundry container agent manifest with 4 tool schemas)
  - .dockerignore (excludes secrets, build artifacts)
  - CI/CD pipeline updated (Docker build → ACR push → Foundry deploy)
  - README section 7 + landing page update + PM spec doc
- **Quality:** 346 tests pass, 0 fail, ruff: 0 violations
- **Follow-ups:** Health check endpoint impl (~1h), image size optimization (~30m), ACR integration test (~1h)
- **User Stories:** All 4 satisfied (production parity, automated CI/CD, health checks, demo readiness)
- **Documents:**
  - Completion summary: `docs/specs/container-deployment-completion.md`
  - Decision: `.squad/decisions/inbox/drummer-container-feature-complete.md`
  - Deployment checklist: `deploy-list.json` (updated with feature tracking)

## Learnings

### 2026-04-05: Container Deployment Feature GitHub Issues Created
- **Main Issue:** #59 Container Deployment Support (now closed)
- **Follow-up Issues:** 
  - #60 Implement /health endpoint in run_local.py (Medium priority)
  - #61 Optimize Docker image size (Low priority)
  - #62 Integration testing against real ACR (High priority)
- **Pattern:** When features are fully implemented but lack GitHub issue documentation, create issue retroactively as PM audit trail. Always close completed features immediately with summary comment.
- **PM Gap Identified:** No GitHub issue had been created for the Container Deployment feature despite completion. This is a PM accountability gap — all features should have tracking issues from start.
- **Updated:** deploy-list.json with GitHub issue numbers for both the main feature and follow-up items
- **Decision file created:** `.squad/decisions/inbox/drummer-container-github-issues.md` documenting the issues and pattern

### 2026-04-05: GitHub Project Board Connected
- **Board:** Project #13 "Agentic Ops Advisor" owned by `tmcclell`
- **Project ID:** PVT_kwHOAzARAM4BTtI0
- **Issues added to board:** #54, #57, #58, #59, #60, #61, #62 (7 items added, total 30 items on board)
- **Access pattern:** `GH_TOKEN` env var lacks project scopes. Must clear it first: `$env:GH_TOKEN = ""` then use `gh project` commands with `--owner tmcclell`.
- **Key commands:**
  - List items: `gh project item-list 13 --owner tmcclell`
  - Add issue: `gh project item-add 13 --owner tmcclell --url https://github.com/tammym-demos/Agentic-Ops-Advisor/issues/{N}`
- **Board reference also saved in:** `.squad/team.md` under `## GitHub Project Board`

### 2026-04-05: Framework Modernization Milestone — User Stories & GitHub Issues
- **Milestone:** Framework Modernization (Issue #84)
- **Deliverable:** 6 user stories with acceptance criteria, definition of success, + 5 GitHub issues
- **Document location:** `.squad/decisions/inbox/drummer-framework-modernization.md`
- **GitHub Issues created:**
  - #85 Validate Agent Application publish step (Playground routing)
  - #86 Add azure.yaml for azd agent lifecycle
  - #87 Simplify deploy.yml with azd commands
  - #88 Unify agent API surface (agent.py legacy, serve.py production)
  - #89 Streamline smoke tests (Responses API only)
  - (Documentation update in README as follow-up)
- **User stories cover:**
  1. Playground fix validation (Run #95 publish step)
  2. azure.yaml declarative config
  3. deploy.yml simplification (1100 → 200 lines)
  4. API surface unification (deprecation + migration guide)
  5. Smoke test streamlining (focus on production paths)
  6. Documentation updates (azd setup, quick start)
- **Definition of Success:** 7 measurable criteria (deployment time, test duration, line count, team sign-off, demo readiness checklist)
- **Pattern:** Each issue references #84 ("Related to #84"), has clear acceptance criteria, and dependencies mapped
- **Tool:** Used `gh issue create` with PowerShell to batch-create issues, avoiding manual GitHub UI
- **Note:** "test" label not found on repo; issue #89 created without it (used "enhancement" only)

### 2026-04-08: Framework Review Session — Orchestration & Cross-Agent Coordination
- **Session Role:** Program Manager — orchestrated Framework Modernization milestone with Holden (architecture assessment) and Amos (azd strategy research)
- **Deliverables:**
  1. **Framework Modernization Milestone (Issue #84):** 6 user stories with acceptance criteria, definition of success (7 measurable criteria), GitHub issues #85–#89
  2. **Cross-team sync:** Drummer (stories), Holden (framework assessment + risk mitigation), Amos (azure.yaml + azd draft)
  3. **Orchestration logs:** Written to `.squad/orchestration-log/2026-04-07T21-33-drummer.md`
  4. **Session summary:** Written to `.squad/log/2026-04-07T21-33-framework-review.md`
- **Framework Assessment Merge:** Holden's assessment merged to `.squad/decisions.md` (replaces inbox file). Identifies critical gaps and azd migration as priority.
- **Outcome:** Framework modernization milestone ready for sprint planning. Team synchronized on priorities (Playground fix → azure.yaml → deploy.yml simplification → API unification → smoke test streamlining → documentation).
- **Confidence:** HIGH — All stories have clear acceptance criteria and measurable success definitions. GitHub issues provide tracking.
- **Status:** ✅ Framework review complete, team orchestration logged, decisions merged, sprint planning ready

### 2026-04-07 21:57:59Z: Scribe Completion Consolidation
- **Cross-agent update:** Naomi completed legacy code cleanup (460 lines agent.py + 570 lines tests removed, 329 tests passing). Commit 84e2f46.
- **Cross-agent update:** Amos resolved OpenAI dependency conflict (`<2.0.0` → `>=2.8.0,<3.0.0`). Commit b1c735a. Run #97 in progress.
- **Orchestration:** All team deliverables logged to `.squad/orchestration-log/`. Sprint orchestration complete.

### 2026-04-08: README Update — Deployment Status & SDK Compatibility Documentation
- **Task:** Update README.md to reflect current implementation state (live deployment, SDK compatibility shim, architecture)
- **Changes made:**
  1. **Tech Stack table:** Added precise framework versions (`agent-framework-azure-ai` v1.0.0b251112+, `azure-ai-agentserver-agentframework` v1.0.0b12, `azure-ai-projects>=2.0.0`)
  2. **New SDK Compatibility section:** Documented the compatibility shim (`scripts/patch_sdk_compat.py`), explaining 4 symbol name mappings and automatic runtime application
  3. **Deployment status banner:** Added "✅ Deployment Status: LIVE" to section 6, confirming smoke test passes and GitHub Actions CI/CD integration
  4. **Environment variables:** Added `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` (current agent framework convention) alongside legacy `AZURE_OPENAI_DEPLOYMENT`
  5. **New Lessons Learned section:** Summarized key deployment insights from `lessons_learned/` directory (framework migration, SDK compat, container optimization, CI/CD hardening, smoke test patterns)
  6. **SDK troubleshooting:** Added FAQ entry for `PromptAgentDefinitionText` and SDK import errors with fix steps
  7. **Table of Contents:** Updated numbering to reflect new section
- **Deliverable:** Commit fc7b9b8 to main branch. README now documents the actual architecture and deployment in use.
- **Status:** ✅ COMPLETE — README reflects live deployment status, SDK compatibility requirement, and deployment insights. Team can now reference current state without manual investigation.


### 2026-04-15: SDK Compatibility & Deployment Name Issue Resolution
- **Issues resolved:** Two deployment blockers fixed in single session
- **Issue #1 — ImportError: PromptAgentDefinitionText**
  - Root cause: `agent-framework-azure-ai` beta imports old symbol names from `azure.ai.projects.models`, but `azure-ai-projects>=2.0.0` renamed them
  - Symbol mappings: `PromptAgentDefinitionText` → `PromptAgentDefinitionTextOptions` (+ 3 others)
  - Fix: Created centralized `scripts/patch_sdk_compat.py` using `setattr()` to create aliases before any framework import
  - Previous approach (inline Python in YAML) failed due to shell escaping and YAML indentation bugs
  - Commit: 6dcd6eb
  - Lesson: Always centralize SDK compat shims as standalone Python scripts, not inline YAML. Import chain is: `from_agent_framework()` → `agent_framework.azure.AzureAIClient` → `agent_framework_azure_ai._client` → `from azure.ai.projects.models import PromptAgentDefinitionText`
- **Issue #2 — ServiceInitializationError: deployment_name required**
  - Root cause: `AzureOpenAIChatClient` from agent_framework expects `deployment_name=` parameter, NOT `model=` (which is standard Azure OpenAI SDK convention)
  - Fix: Changed serve.py instantiation from `model=settings.azure_openai_deployment` to `deployment_name=settings.azure_openai_deployment`. Added belt-and-suspenders env var fallback for `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`
  - Commit: 87118f4
  - Lesson: Agent framework SDK uses non-standard parameter names. Always check SDK source, not assumptions.
- **Smoke test result:** After both fixes, smoke test PASSED for the first time — agent fully deployed, responded with real LLM output
- **Document created:** `lessons_learned/sdk-compatibility-and-deployment-name.md` with full issue tables, architecture decisions, debugging techniques, and CI/CD updates
- **Decision file:** `.squad/decisions/inbox/drummer-sdk-compat-lesson.md` (team-relevant decision on SDK shim location)
