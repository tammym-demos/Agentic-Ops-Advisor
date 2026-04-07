# Decision: Fix hybrid deploy — correct SDK params, extract deploy script, remove host:containerapp

**Author:** Amos (DevOps)
**Date:** 2026-07-27
**Status:** Implemented

## Context

The initial hybrid deploy (commit 1741a86) replaced `azd deploy` but had incorrect SDK parameter names (`body=` instead of `definition=`, `protocol_name/protocol_version` instead of `protocol/version`), wrong `az cognitiveservices` command syntax, and left `host: containerapp` in azure.yaml. The workflow was also 727 lines (over 650 target).

## Decision

1. **Extract inline Python to `scripts/deploy_agent.py`** — adds retry logic (5 attempts with backoff), proper SDK params matching the old working deploy, and exports `DEPLOYED_AGENT_ID` to `GITHUB_ENV` for downstream steps.

2. **Fix SDK parameters** — `create_version(definition=..., description=..., metadata=...)` matches the working pattern from pre-simplification deploy.yml.

3. **Fix `az cognitiveservices agent start`** — use `--project-name`, `--name`, `--agent-version`, `--min-replicas`, `--max-replicas` (not `account agent start`).

4. **Remove `host: containerapp` from azure.yaml** — prevents accidental `azd deploy` from targeting Container Apps.

5. **Use `AZURE_CONTAINER_REGISTRY_NAME` env var** — replaces `resolve_names` step that derived ACR name from parameters.json. Simpler, more explicit.

## Impact

- Workflow: 727 → 644 lines
- New file: `scripts/deploy_agent.py` (reusable for local deploy too)
- No impact on Bicep infra, tests, or smoke test
