# Decision: Data-Plane RBAC Fix for Foundry Agent Deploy

**Date:** 2026-04-07
**Author:** Amos (DevOps)
**Triggered by:** Deploy workflow Run #34 failure — `PermissionDenied` on `client.list_agents()`

## Problem

The GitHub Actions service principal has `Contributor` scoped to `rg-agentic-ops-advisor`. Contributor only grants management-plane (ARM) access. Foundry Agent Service APIs (`list_agents`, `create_agent`, etc.) are **data-plane** operations on `Microsoft.CognitiveServices/accounts` resources, requiring the `Azure AI Developer` role (ID: `64702f94-c441-49e6-a78b-ef80e0188fee`).

## Decision

Assign `Azure AI Developer` imperatively (not via Bicep) to both:
1. **Deploy SP** — for CI/CD agent deployment operations
2. **Managed identity (`id-agentops-prod`)** — for runtime container agent operations

### Why imperative, not Bicep?

The actual AI Hub (`hub-agentops-prod`) is `Microsoft.CognitiveServices/accounts` (kind: AIServices), created manually via Azure Portal. The Bicep template (`aifoundry.bicep`) still defines a `MachineLearningServices/workspaces` Hub that was never successfully deployed via ARM. Adding role assignments to the Bicep module would target a resource that doesn't match the live infrastructure.

### Why `continue-on-error` in CI?

The SP has `Contributor` which lacks `Microsoft.Authorization/roleAssignments/write`. It **cannot** self-assign roles. The workflow step is best-effort: it will succeed if someone has already elevated the SP to Owner, but gracefully warns otherwise. The real fix is an admin one-time pre-assignment.

## Changes

| File | What |
|------|------|
| `.github/workflows/deploy.yml` | Header: documented Azure AI Developer prerequisite. New Step 5c: RBAC assignment (best-effort) for SP + MI. |
| `infra/deploy.sh` | New pre-flight step 6: RBAC assignment for SP (if `AZURE_CLIENT_ID` set) + MI. Succeeds when run by Owner. |

## Admin Action Required

An admin with **Owner** or **User Access Administrator** must run:

```bash
# For the deploy SP:
az role assignment create \
  --assignee-object-id d30fcff3-4eab-4b85-a366-f9a17142be39 \
  --assignee-principal-type ServicePrincipal \
  --role "64702f94-c441-49e6-a78b-ef80e0188fee" \
  --scope /subscriptions/e0b48569-71a2-40fe-9b7a-2fb859f31288/resourceGroups/rg-agentic-ops-advisor/providers/Microsoft.CognitiveServices/accounts/hub-agentops-prod

# For the managed identity (get principal ID first):
MI_ID=$(az identity show -n id-agentops-prod -g rg-agentic-ops-advisor --query principalId -o tsv)
az role assignment create \
  --assignee-object-id "$MI_ID" \
  --assignee-principal-type ServicePrincipal \
  --role "64702f94-c441-49e6-a78b-ef80e0188fee" \
  --scope /subscriptions/e0b48569-71a2-40fe-9b7a-2fb859f31288/resourceGroups/rg-agentic-ops-advisor/providers/Microsoft.CognitiveServices/accounts/hub-agentops-prod
```

Or equivalently, run `./infra/deploy.sh` locally as an Owner — the new pre-flight step 6 handles both assignments.

## Risk

Low. Role assignments are idempotent (`az role assignment create` is a no-op if already assigned). The `continue-on-error: true` in CI ensures the workflow never breaks on RBAC attempts.
