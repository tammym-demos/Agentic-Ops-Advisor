# Decision: Publish Agent Application after create_version() (Issue #84)

**By:** Amos (DevOps)
**Date:** 2026-04-11
**Status:** ✅ Implemented — awaiting deploy run confirmation
**Scope:** `.github/workflows/deploy.yml`

## What

Added **Step 5e.2 — Publish Agent Application** to the deploy pipeline. After `create_version()` creates a hosted agent version, we now call the ARM REST API to:

1. **Create/update an Agent Application** (`Microsoft.CognitiveServices/accounts/projects/applications/{name}`) — wraps the agent with a stable endpoint, RBAC, and its own identity
2. **Create/update an Agent Deployment** (child resource) — references the specific agent version with `deploymentType: Hosted`, `protocols: [Responses]`, and replica config

This exposes the `/applications/{name}/protocols/openai/responses` endpoint that the Foundry Playground uses.

## Why

`create_version()` alone only creates the agent version inside the project. The Playground routes through the `/applications/` endpoint, which requires a separate ARM-level "publish" step. Without it, the Playground falls back to the legacy Agents API (threads/runs), which shows raw function-call JSON instead of container-processed results.

## Risk

**Low** — The publish step uses `continue-on-error: true`, so failures don't block the agent deployment. The agent remains functional via the project-level SDK pattern regardless.

**Identity caveat:** Publishing assigns a NEW Entra identity to the application. Any tools using agent identity auth need RBAC reassigned to the new identity. Our container uses API key env vars, so this is non-blocking for now.

## Team Impact

- **Naomi (Backend):** No changes to `serve.py`. The container's `/responses` endpoint is unchanged.
- **Holden (Lead):** Post-demo, consider adding managed identity permissions on the Agent Application identity for Azure OpenAI (replace API key fallback).
- **Tammy (PM):** After the next deploy run, the Playground should show analyzed results instead of raw JSON. Test by asking "What is the GPU utilization trend?" in the Agent Playground.

## RBAC Required

The deploy SP needs `Azure AI Project Manager` role on the Foundry resource to publish agents. The step auto-grants `Azure AI User` on the application for smoke test invocation.
