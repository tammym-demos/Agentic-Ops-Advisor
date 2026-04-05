# Amos — History

## Core Context
- **Project:** Agentic Ops Advisor — governed AI agent for infrastructure telemetry reasoning
- **Stack:** Python 3.11, Azure AI Agent Service SDK, GPT-4.1, Bicep, OpenTelemetry
- **Repo:** tammym-demos/Agentic-Ops-Advisor
- **User:** Tammy
- **Status:** All 22 PRs merged. Remaining: tests, Azure deployment, integration test.

## Learnings

### 2026-04-04: Deployment Readiness Audit
- **az CLI:** Authenticated to subscription `ME-MngEnvMCAP960375-tmcclell-1` (e0b48569-...), state Enabled
- **Bicep structure:** `infra/main.bicep` is subscription-scoped, deploys 6 modules: identity, loganalytics, appinsights, sql, openai, aifoundry
- **Key file paths:** `infra/deploy.sh` (deploy script), `infra/parameters.json` (params with KV ref), `.github/workflows/deploy.yml` (CI/CD)
- **Blocker — Key Vault missing:** `rg-secrets/kv-agentic-ops-secrets` referenced in parameters.json does not exist; SQL admin password secret not created
- **Blocker — 6 resource providers not registered:** Sql, CognitiveServices, MachineLearningServices, OperationalInsights, KeyVault, ContainerRegistry
- **Blocker — deploy.yml scope mismatch:** Workflow uses `az deployment group create` but main.bicep is subscription-scoped; needs `az deployment sub create`
- **Resource group `rg-agentic-ops-advisor`:** Does not exist yet (expected — Bicep creates it)
- **deploy.sh:** Has built-in pre-flight, provider registration, --what-if mode, and auto-generates .env from deployment outputs
