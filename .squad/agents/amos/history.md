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

### 2026-04-05: Azure Infrastructure Deployment
- **Deployed 9 of 11 resources** to `rg-agentic-ops-advisor` in eastus (SQL in centralus)
- **Resources created:**
  - `id-agentops-prod` — User-assigned Managed Identity (eastus)
  - `log-agentops-prod` — Log Analytics Workspace (eastus)
  - `appi-agentops-prod` — Application Insights (eastus)
  - `oai-agentops-prod` — Azure OpenAI with gpt-4.1 deployment (eastus)
  - `sql-agentops-prod` — SQL Server + `agentops-telemetry` DB (centralus, AAD-only auth)
  - `kv-hub-agentops-prod` — Key Vault for AI Foundry Hub (eastus)
  - `sthubagentopsprod` — Storage Account for AI Foundry Hub (eastus)
  - `crhubagentopsprod` — Container Registry for AI Foundry Hub (eastus)
- **Key Vault prereqs:** Deployed `kv-agentic-ops-secrets` in `rg-secrets` with `enabledForTemplateDeployment: true`
- **Bicep fixes applied:**
  1. `keyvault.bicep`: Changed `enablePurgeProtection: false` → `null` (Azure rejects explicit false)
  2. `keyvault.bicep`: Added `enabledForTemplateDeployment: true` (required for ARM KV param refs)
  3. `sql.bicep`: Switched to Azure AD-only auth — MCAPS policy denies SQL auth (`SFI-ID4.2.2`)
  4. `aifoundry.bicep`: Changed OpenAI connection `authType: 'ManagedIdentity'` → `'AAD'`
  5. `aifoundry.bicep`: Added Key Vault Reader role for managed identity on hub KV
  6. `aifoundry.bicep`: Added `dependsOn: [kvReaderAssignment]` on project for RBAC propagation
  7. `main.bicep`: Added `sqlLocation` param for cross-region SQL when primary region has capacity issues
  8. `main.bicep`: Removed `sqlAdminLogin`/`sqlAdminPassword` (no longer needed with AAD-only auth)
  9. `parameters.json`: Removed Key Vault reference for SQL password
- **Remaining blocker — AI Foundry Hub:** `hub-agentops-prod` fails with persistent `InternalServerError` from Azure ML service. Not a template issue — all supporting resources deploy fine.
- **Region notes:** eastus2 and eastus both blocked SQL server creation during deployment window; centralus worked
- **All 10 resource providers now Registered**
