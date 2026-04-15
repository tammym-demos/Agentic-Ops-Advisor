# Decision: Use `deployment_name` for AzureOpenAIChatClient

**Date:** 2025-07-15
**Author:** Amos (DevOps)
**Status:** Implemented

## Context

The Foundry container was crashing on startup with `ServiceInitializationError` because
`AzureOpenAIChatClient` expects `deployment_name=`, not `model=`.

## Decision

1. Changed `model=` → `deployment_name=` in `scripts/serve.py`.
2. Added belt-and-suspenders env var bridge: `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` is set
   from `AZURE_OPENAI_DEPLOYMENT` early in `main()` so the SDK's env var fallback also works.
3. Added `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` to `agent.yaml` and `Dockerfile` for consistency.

## Rationale

The `agent_framework` SDK uses `deployment_name` as the constructor parameter and falls back
to `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` env var. Our existing `AZURE_OPENAI_DEPLOYMENT` env var
doesn't match the SDK's expected name, so both the parameter fix and env var bridge are needed.
