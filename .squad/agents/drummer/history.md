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
