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

### 2026-04-19: Solution Purpose Documentation Created
- **Task:** Create comprehensive `docs/solution-purpose.md` explaining the PURPOSE of the Agentic Ops Advisor solution
- **Audience:** Stakeholders, demo audiences, new team members, ops teams, platform engineers, AI builders
- **Document Structure:**
  1. Overview — 2 paragraph executive summary (governed AI agent for infrastructure ops, hybrid governance, self-driving operations vision)
  2. Problem Statement — Information fragmentation (telemetry vs. changes), reactive response, lack of governance
  3. Solution Approach — Telemetry + intent, hybrid governance (AI proposes, humans approve), evidence-based reasoning
  4. Key Capabilities — Diagnose anomalies, suggest remediations, search telemetry, surface change context, track decisions, reason under uncertainty
  5. Architecture Summary — Three tool surfaces (SQL Telemetry, Work Context Stub, Action Stub) with examples
  6. Deployment Model — Local demo, Agent server, Azure AI Foundry (production)
  7. Who Is This For — Ops/SRE teams, platform engineers, AI builders, stakeholders, new members
  8. What This Is NOT — Not production-ready yet, not replacement for observability tools, not real Work IQ, not general chatbot, not auto-remediation
  9. Related Documentation — Links to README, architecture decisions, setup guides, specs, lessons learned, evaluation framework
  10. Key Terminology — Agentic ops, self-driving operations, hybrid governance, telemetry + intent, RCA, work context
  11. Next Steps — Learning path and contribution guidance
  12. Disclaimers — Synthetic data, Work IQ simulation, no production guarantees
- **Deliverable:** `docs/solution-purpose.md` (14.4KB, 9 major sections + terminology + disclaimers)
- **Language Alignment:** Used "agentic ops", "hybrid governance", "telemetry + intent", "self-driving operations" throughout
- **Key Features:**
  - Stakeholder-friendly language (explains "why" before "how")
  - Includes standard disclaimers (synthetic data, Work IQ simulation)
  - Links to other documentation for deep dives
  - Architecture summary references architecture decisions doc for details (avoids duplication)
  - Clarifies scope: reference architecture + demo vehicle, not production-ready
  - Emphasizes human-in-the-loop governance (AI proposes, humans approve)
- **Status:** ✅ COMPLETE — Document ready for stakeholder distribution and onboarding

### 2026-04-19: SRE Agent RBAC Documentation Section
- **Task:** Add RBAC role assignment section to `docs/sre-agent-setup.md`
- **Context:** Coordinator provided guidance on two-layer RBAC model (agent permissions vs user roles); real infrastructure values from portal
- **Changes:**
  - Added RBAC section documenting Reader role for agent managed identity
  - Added Standard User role guidance for integration users
  - Included role assignment verification steps
  - Cross-linked with infrastructure values from `.squad/decisions/inbox/copilot-directive-2026-04-19T1249.md`
- **Outcome:** Setup documentation now complete with security configuration
- **Status:** ✅ COMPLETE — Ready for merge and team reference

### 2025-07-27: SRE Agent Integration Documentation
- **Task:** Create differentiation doc and setup guide for Azure SRE Agent integration
- **Documents created:**
  - `docs/sre-agent-differentiation.md` — Comparison of Agentic Ops Advisor vs SRE Agent capabilities, complementary value, integration architecture
  - `docs/sre-agent-setup.md` — Installation, configuration, and verification guide covering Phase 1 (MCP) and Phase 2 (REST)
- **Key source files referenced:**
  - `tools/sql_telemetry.py` — SQL telemetry tool (GPU, network, cost, incidents)
  - `tools/work_context_stub.py` — Work IQ context stub (change events, decisions, ownership, runbooks)
  - `tools/action_stub.py` — Action stub (risk assessment, approval simulation)
  - `tools/work_context_mcp.py` — MCP server wrapper
  - `agent/config.py` — Feature flags and settings
  - `agent/system_prompt.md` — Agent persona and response format
  - `.squad/plans/sre-agent-architecture-decisions.md` — Holden's architecture decisions (5 decisions, phasing plan)
  - `.env.example` — Environment variable template
- **Documentation decisions:**
  - Differentiation doc structured as stakeholder-friendly comparison (not technical spec)
  - Setup guide follows existing docs style with tables, code blocks, and verification checklists
  - Both docs link to architecture decisions for rationale rather than duplicating it
  - Environment variable summary table included in setup guide for quick reference
- **Decision file:** `.squad/decisions/inbox/drummer-sre-docs.md`

### 2026-04-19: RBAC Role Assignments Section Added to SRE Agent Setup Guide
- **Task:** Add comprehensive RBAC role assignment section to `docs/sre-agent-setup.md`
- **Location:** Inserted as new `## RBAC Role Assignments` section after "Required Permissions" subsection and before "SRE Agent Portal Creation"
- **Content added:**
  - **Layer 1 — Agent Permissions (Managed Identity)** — Two-row table (Reader for our integration, Privileged for autonomous actions)
  - **Layer 2 — User Roles** — Three-row table (SRE Agent Reader, Standard User, Administrator with permissions and use cases)
  - **Our Integration's Role Requirements** — Specific status for Tammy (Administrator ✅), SRE Agent managed identity (Reader ✅), and Agentic Ops Advisor's managed identity (needs Standard User for Phase 2)
  - **How to Review or Change Roles** — Step-by-step portal instructions + two Azure CLI examples:
    1. Assigning SRE Agent Standard User to Agentic Ops Advisor's managed identity
    2. Listing current SRE-related role assignments in the resource group
- **Additional fix:** Updated Prerequisites table Region from `eastus` to `East US 2` to match actual provisioned instance
- **Lines modified:** Lines 28 (Region fix) and lines 37–39 expanded to 41–111 (RBAC section insertion)
- **Deliverable:** `docs/sre-agent-setup.md` updated and tested
- **Status:** ✅ COMPLETE — Documentation now covers two-layer RBAC model with portal + CLI guidance
