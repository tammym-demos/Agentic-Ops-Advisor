# Decision: Option B — Replace SDK deploy with `az cognitiveservices agent create`

**Author:** Naomi (Backend Dev)
**Date:** 2026-06-01
**Status:** Implemented
**Commit:** d91908e

## Context

Option A (4 surgical fixes to deploy.yml) was applied but hit two server-side blockers:
1. Container won't start: `az cognitiveservices agent start` reports "Deployment failed with status 'Failed': No error details available" — no container replicas running.
2. ARM `/applications` returns `SystemError` from `managementfrontend` in eastus — a Foundry platform bug we can't fix from code.

## Decision

Replace the two-step deploy flow (`deploy_agent.py` SDK `create_version` → `az cognitiveservices agent start`) with a single `az cognitiveservices agent create` command that handles version creation + container deployment + startup in one shot.

**Key rationale:**
- `agent create` may use a different internal code path that avoids the deployment failure
- Passing all env vars via `--env` ensures the container receives its runtime config (a possible root cause of the startup failure)
- `--protocol responses --protocol-version v1` sets up the Responses protocol directly, potentially making ARM publish unnecessary
- Single command = fewer failure points

## Fallback Strategy

If `agent create` fails:
1. Fall back to `deploy_agent.py` (SDK `create_version`)
2. Fall back to `az cognitiveservices agent start`
3. ARM publish still attempted if Responses endpoint probe fails

`deploy_agent.py` is retained — not deleted.

## Impact

- **deploy.yml Steps 6+7** fully rewritten
- Header comment updated to reflect CLI-first approach
- No code changes outside deploy.yml
- No test changes needed (341 pass)

## What to Watch

- Deploy Run triggered by push — check if container starts successfully
- If `agent create` command not recognized (CLI < 2.80), fallback to SDK path should activate
- If ARM `/applications` SystemError persists, the Responses probe may skip it entirely (good)
