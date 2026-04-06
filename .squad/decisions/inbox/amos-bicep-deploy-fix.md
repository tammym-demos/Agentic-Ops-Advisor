# Decision: Bicep Deploy Fix — Subscription-Scope Fallback

**Date:** 2026-07-26
**By:** Amos (DevOps)
**Severity:** Critical — blocked all Bicep deployments since architecture rewrite
**Related:** Run #52 failure, Issue #63 (Foundry Hub)

## Problem

Deploy pipeline has never succeeded since the CognitiveServices architecture rewrite.
`az deployment sub create` requires subscription-scope Contributor, but the SP
(`d30fcff3-4eab-4b85-a366-f9a17142be39`) only has Contributor at RG scope
(`rg-agentic-ops-advisor`). Error: `AuthorizationFailed` on
`Microsoft.Resources/deployments/validate/action` over subscription scope.

## Solution

**Two-part approach — works with existing RG-scoped Contributor, no permission changes needed:**

1. **deploy.yml Step 4 — smart fallback:**
   - Tries `az deployment sub create` first (subscription-scoped, uses `main.bicep`)
   - If auth fails, falls back to `az group create` + `az deployment group create` with `main-rg.bicep`
   - Clear `echo` messages explain what happened and how to fix permanently

2. **infra/main-rg.bicep — resource-group-scoped template:**
   - Identical modules and outputs as `main.bicep`
   - `targetScope = 'resourceGroup'` instead of `'subscription'`
   - No `resource rg` block (RG created by `az group create` in the shell step)
   - Same parameters for `@infra/parameters.json` compatibility

3. **scripts/grant-sp-permissions.sh — optional permanent fix:**
   - Grants subscription-scope Contributor to the SP
   - Tammy can run this to avoid the fallback path entirely
   - Includes pre-flight checks, argument parsing, verification output

## Files Changed

| File | Change |
|------|--------|
| `.github/workflows/deploy.yml` | Step 4 rewritten with try/fallback, header docs updated, validation includes main-rg.bicep |
| `.github/workflows/ci-eval.yml` | Added main-rg.bicep to Bicep PR validation |
| `infra/main-rg.bicep` | NEW — RG-scoped variant of main.bicep |
| `scripts/grant-sp-permissions.sh` | NEW — one-command SP permission grant |

## Impact

- **Demo unblocked:** Pipeline will succeed with existing RG-scoped Contributor
- **No breaking changes:** Subscription-scoped path still preferred, fallback is transparent
- **BCP081 warning:** `Microsoft.CognitiveServices/accounts/projects@2024-10-01` is informational only, does not block deployment

## Next Steps

- [ ] Push to main, trigger workflow_dispatch with `force_infra=true`
- [ ] If fallback works, Tammy can optionally run `grant-sp-permissions.sh` later
- [ ] Consider deleting `infra/main.json` (dead compiled ARM output) in future cleanup
