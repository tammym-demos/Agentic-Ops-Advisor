# Deployment Results — Azure Infrastructure

**Date:** 2026-04-05
**By:** Amos (DevOps)

## What Happened

Deployed Azure infrastructure for Agentic Ops Advisor. 9 of 11 resources deployed successfully.

## Decisions Made

1. **SQL switched to Azure AD-only auth** — MCAPS governance policy (`SFI-ID4.2.2`) denies SQL servers without `azureADOnlyAuthentication: true`. Removed SQL admin login/password entirely; using managed identity as Azure AD admin.

2. **SQL deployed to centralus** — Both `eastus` and `eastus2` were blocking new SQL server creation during this window. Added `sqlLocation` param to allow cross-region SQL deployment. Used `centralus` as override.

3. **Key Vault parameter reference requires `enabledForTemplateDeployment: true`** — ARM cannot resolve Key Vault secret references in `parameters.json` without this flag.

4. **OpenAI connection authType changed to `AAD`** — AI Foundry rejects `ManagedIdentity` as a valid authType; requires `AAD` instead.

## Remaining Blocker

**AI Foundry Hub (`hub-agentops-prod`) — persistent InternalServerError.** This is an Azure ML service-side issue, not a template problem. All supporting resources (storage, KV, container registry) deploy fine. The Hub workspace creation itself returns `InternalServerError` repeatedly. Tracked in issue #63.

## Impact on Team

- Parameters.json no longer has a Key Vault reference for SQL password — deploy.sh's KV pre-flight logic for SQL password is no longer needed
- The `.env` file needs the actual endpoints from the deployed resources (see verification section in history.md)
- Integration testing can't proceed until AI Foundry Hub + Project are created
