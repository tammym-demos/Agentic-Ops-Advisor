# Lessons Learned: Foundry Hosted Agent Deployment

**Project:** Agentic Ops Advisor  
**Dates:** April 12–13, 2026  
**Deploys:** Runs #130–#143 (14 deployment attempts)  
**Final Status:** ✅ Agent responding with real LLM output in production

---

## Executive Summary

Deploying a custom Python container as an Azure AI Foundry hosted agent required solving **7 distinct, cascading issues** across 14 CI/CD runs. Each fix revealed a new hidden problem. The final deployment (#143) produced a working agent after correcting all layers from container startup to OpenAI credential configuration.

---

## Issue #1: Blocking Startup — `DefaultAzureCredential` Hangs at Import

| | |
|---|---|
| **Runs** | #129–#130 |
| **Symptom** | `RequestTimedOut` — Foundry gateway 100s timeout, no TCP connection to container |
| **Root Cause** | `DefaultAzureCredential().get_token()` was called **synchronously at startup** before the HTTP server started. In the Foundry container environment, the IMDS (Instance Metadata Service) probe hangs for ~120s when no managed identity is immediately available. |
| **Fix** | Moved all auth to request-time. Used `asyncio.Event()` readiness gate + `on_startup` async hook. HTTP server starts in <1s, auth happens lazily per-request. |
| **Commit** | `1a21343` |
| **Lesson** | **Never perform credential probes at startup in container environments.** Azure managed identity may not be available until after the sidecar initializes. Start the HTTP listener first, gate readiness separately, authenticate lazily. |

---

## Issue #2: Invalid CLI Flag — `--target-port` Doesn't Exist

| | |
|---|---|
| **Runs** | #130–#132 |
| **Symptom** | `RequestTimedOut` persists despite startup fix |
| **Root Cause** | The `az cognitiveservices agent create` command included `--target-port 8088`, which is **not a valid flag**. Exit code 2 on every deploy since inception. The workflow silently fell through to an SDK fallback that created the agent version but couldn't configure Container App networking. |
| **Fix** | Removed `--target-port`. Added `agent delete` before `agent create` for clean Container App creation. Port auto-configured from Dockerfile `EXPOSE 8088`. |
| **Commit** | `07ebfe6` |
| **Lesson** | **Validate all CLI flags against `--help` before committing them to CI.** The `continue-on-error: true` on the deploy step masked the failure — the pipeline showed "success" while the deploy was fundamentally broken. Also: **never use `continue-on-error: true` on critical deploy steps** without a separate validation gate. |

---

## Issue #3: Wrong Server Framework — Raw aiohttp vs. Foundry Hosting Adapter

| | |
|---|---|
| **Runs** | #132–#133 |
| **Symptom** | CLI create succeeded (first time!), container was "active", but still `RequestTimedOut` — TCP connection never established |
| **Root Cause** | The container used raw `aiohttp` to serve HTTP, but Foundry's sidecar/data-proxy infrastructure expects the **official hosting adapter** (`azure-ai-agentserver-core` package with `FoundryCBAgent`). The adapter handles sidecar integration, protocol translation, health probing, and CORS that raw HTTP doesn't. |
| **Fix** | Migrated `serve.py` to use `FoundryCBAgent` (uvicorn + Starlette) for production. Kept aiohttp as fallback for local dev and existing test suite. |
| **Commit** | `5777540` |
| **Lesson** | **Always use the official hosting adapter package for Foundry hosted agents.** The packages are: `azure-ai-agentserver-core`, `azure-ai-agentserver-agentframework`, `azure-ai-agentserver-langgraph`. Raw HTTP frameworks won't work — the sidecar requires specific integration points. |

---

## Issue #4: Streaming Protocol — `'Response' object has no attribute 'anext'`

| | |
|---|---|
| **Runs** | #133–#136 |
| **Symptom** | Container started, adapter loaded, but immediate error: `'Response' object has no attribute 'anext'` |
| **Root Cause** | The Foundry Playground **always** sends `stream: true`. When streaming, the adapter calls `__anext__()` on the return value of `agent_run()`, expecting an **async generator**. Our code returned a plain `Response` object (not iterable). |
| **Fix** | Made `agent_run()` check `context.stream`. When True, return an async generator yielding the full SSE event sequence (ResponseCreatedEvent → InProgressEvent → ... → CompletedEvent). When False, return a `FoundryResponse` object. |
| **Commit** | `a9c9196` |
| **Lesson** | **Foundry Playground always streams.** Your `agent_run()` must handle `context.stream == True` by returning an async generator of `ResponseStreamEvent` objects. Non-streaming responses are only used by programmatic SDK callers. |

---

## Issue #5: Silent Hang — OpenAI Call Blocks Before SSE Events Start

| | |
|---|---|
| **Runs** | #136–#137 |
| **Symptom** | No error, but response never arrives. Container appears to hang indefinitely. |
| **Root Cause** | The `agent_run()` method `await`ed the entire OpenAI call (30s+) **before** returning the async generator. During this time, no SSE events flowed, so the adapter's keep-alive mechanism (`_iter_with_keep_alive`) never activated. The gateway's 100s timeout closed the connection while the OpenAI call was still running. |
| **Fix** | Restructured: return the async generator **immediately**. Yield `response.created` and `response.in_progress` first (fast, no I/O), THEN do the OpenAI call inside the generator where keep-alives are active. |
| **Commit** | `19bc764` |
| **Lesson** | **Return the async generator INSTANTLY.** The adapter only sends keep-alive SSE comments while iterating. Any blocking work before `return` means no keep-alives, which means gateway timeout. Structure: yield early events → do heavy work → yield completion event. |

---

## Issue #6: App Insights Exporter Flooding stderr

| | |
|---|---|
| **Runs** | #137–#138 |
| **Symptom** | Repeating error in container logs: `azure.monitor.opentelemetry.exporter: Non-retryable server side error: Bad Request`. Agent response hangs. |
| **Root Cause** | The `FoundryCBAgent` adapter auto-configures Azure Monitor telemetry at two points: (1) logging via `config_logging()` at **module import time**, (2) tracing via `init_tracing()` at runtime. When the App Insights connection string is invalid or the resource rejects telemetry, the exporter retries on a background thread, flooding stderr and potentially starving async I/O. |
| **Fix** | (a) Set `ENABLE_APPLICATION_INSIGHTS_LOGGER=false` **before** the adapter import to skip log exporter setup. (b) Override `init_tracing()` in our `AgenticOpsAgent` subclass to create a no-op tracer (skips `AzureMonitorTraceExporter`). (c) Added both env vars to the deploy workflow. |
| **Commit** | `19eafd7` |
| **Lesson** | **Disable App Insights export until your agent is working end-to-end.** The adapter's auto-configured telemetry can cause blocking I/O if the connection string is invalid. Set `ENABLE_APPLICATION_INSIGHTS_LOGGER=false` before importing the adapter and override `init_tracing()` to create a no-op tracer. Re-enable once the agent is stable and the App Insights resource is validated. |

---

## Issue #7: SSE Stream Dies After 3 Events — Foundry Gateway Truncation

| | |
|---|---|
| **Runs** | #138–#139 |
| **Symptom** | Streaming returns exactly 3 of 9 SSE events (created, in_progress, output_item.added), then silently terminates. No error event. |
| **Root Cause** | The Foundry gateway data proxy (`ca-data-proxy-*.azurecontainerapps.io`) **silently truncates SSE streams** after a small number of events. Events 4–9 (content_part.added through response.completed) never reached the client. Tested exhaustively: all event constructors pass locally, adapter pipeline works in simulation — the truncation happens at the infrastructure layer. |
| **Fix** | Simplified streaming from 9 events to 3: `response.created` → `response.in_progress` → `response.completed`. The `completed` event carries the **full output payload** (response text in `output[].content[].text`), eliminating the need for intermediate content events. |
| **Commit** | `a50ab5e` |
| **Lesson** | **Use a minimal SSE event sequence for Foundry hosted agents.** The gateway may truncate long event streams. The 3-event pattern (created → in_progress → completed) is sufficient — the completed event includes all output. Do not rely on intermediate content/delta events being delivered. |

---

## Issue #8: Wrong Azure OpenAI Endpoint Format

| | |
|---|---|
| **Runs** | #139–#141 |
| **Symptom** | Agent responds with `"Error: DeploymentNotFound"` — container is alive but can't find the GPT-4.1 deployment |
| **Root Cause** | The `AZURE_OPENAI_ENDPOINT` GitHub secret pointed to the wrong URL format. Three endpoint formats exist for the same account, with very different behavior: |

**Azure OpenAI Endpoint Formats:**

| Format | Example | Response Time | Use For |
|--------|---------|--------------|---------|
| `openai.azure.com` | `https://hub-agentops-prod.openai.azure.com/` | ~1.9s | ✅ Azure OpenAI SDK calls |
| `cognitiveservices.azure.com` | `https://hub-agentops-prod.cognitiveservices.azure.com/` | ~2.6s | ✅ Cognitive Services REST API |
| `services.ai.azure.com` | `https://hub-agentops-prod.services.ai.azure.com/` | ~35s | ❌ AI Foundry API only — NOT for OpenAI calls |

| **Fix** | Updated the `AZURE_OPENAI_ENDPOINT` secret to `https://hub-agentops-prod.openai.azure.com/` |
|---|---|
| **Lesson** | **Use `*.openai.azure.com` for Azure OpenAI SDK calls.** The `*.services.ai.azure.com` endpoint is the Foundry project API — it's extremely slow for OpenAI calls and may not resolve deployments correctly. The `*.cognitiveservices.azure.com` endpoint also works but is slower. |

---

## Issue #9: Deployment Name Typo in GitHub Secret

| | |
|---|---|
| **Runs** | #141–#143 |
| **Symptom** | `DeploymentNotFound` persists even after endpoint correction |
| **Root Cause** | The `AZURE_OPENAI_DEPLOYMENT` GitHub secret was **6 characters** instead of 7 — likely `gpt-41` (missing the dot) instead of `gpt-4.1`. GitHub Actions masks all secret values with `***`, making it impossible to verify from CI logs. |
| **How We Found It** | Added diagnostic logging that outputs the **string length** and **parsed hostname** (neither matches the full secret value, so GitHub doesn't mask them). CI output showed `deployment length: 6` — immediately revealing the mismatch. |
| **Fix** | Corrected the secret to `gpt-4.1` (7 characters). Added permanent diagnostic logging for endpoint hostname and deployment length. |
| **Commits** | `cc19690` (diagnostics), `838105f` (redeploy) |
| **Lesson** | **Add diagnostic logging that reveals config shape without exposing secret values.** GitHub Actions masks the exact value of every secret. Log **string lengths**, **parsed hostnames**, and **expected vs actual** comparisons to debug config issues without leaking credentials. |

---

## Architecture Decisions Made

### 1. Port Configuration
- **Foundry sidecar occupies port 8080** inside the container environment
- Container must use **port 8088** (the hosting adapter default)
- Set via Dockerfile `EXPOSE 8088` — the CLI auto-configures from this

### 2. Authentication
- **API key disabled by policy** on the Azure OpenAI resource
- Container uses **project system-assigned managed identity**
- Token scope for OpenAI: `https://cognitiveservices.azure.com/.default`
- Token scope for Foundry API: `https://ai.azure.com/.default`
- `DefaultAzureCredential()` created **per-request**, never at startup

### 3. Error Response Format
- Always return `status: "completed"` — even for errors
- Using `status: "failed"` causes the Foundry gateway to **strip output text**
- Error details go in the response text, not the status

### 4. ARM Publish Endpoint
- The ARM REST API for `/applications` publish has a **persistent SystemError in eastus**
- All API versions fail: `2025-10-01-preview`, `2025-12-01`, `2026-01-15-preview`
- **Workaround:** Publish via the Azure AI Foundry Portal UI, or rely on the CLI `agent create --protocol responses` which auto-publishes

---

## Debugging Techniques That Worked

1. **String length diagnostics** — logged `${#SECRET_VAR}` in CI to reveal config mismatches without exposing values
2. **Parsed hostname logging** — extracted hostname from URL (not the full URL = not the full secret) to show endpoint identity
3. **Non-streaming test** — called the agent with `stream=False` to distinguish container issues from streaming issues
4. **Raw HTTP SSE test** — used `httpx` to observe raw SSE events and byte-level stream behavior
5. **Local adapter simulation** — ran the adapter's `_iter_with_keep_alive` + `_event_to_sse_chunk` pipeline locally to prove the issue was in the gateway, not the code
6. **Smoke test with `agent_reference`** — used `openai.responses.create()` with `extra_body={"agent_reference": ...}` pattern for reliable Foundry agent invocation

---

## CI/CD Pipeline Improvements Made

| Change | Why |
|--------|-----|
| Removed `--yes` from `agent delete` (invalid flag) | Was failing silently |
| Added endpoint hostname + deployment length echo | Debug masked secrets |
| Added `ENABLE_APPLICATION_INSIGHTS_LOGGER=false` env var | Prevent OTel export blocking |
| Added `AZURE_AI_PROJECT_ENDPOINT` env var | Required by hosting adapter |
| `SERVE_PORT=8088` explicit env var | Defense-in-depth for port config |

---

## CI/CD Pipeline Improvements Still Recommended

| Change | Why |
|--------|-----|
| Remove `continue-on-error: true` from deploy step | Currently masks deploy failures as successes |
| Add semantic smoke test validation | Check response text isn't an error message, not just `status: completed` |
| Add container log streaming on failure | Currently container logs are only visible during `--show-logs` window |
| Add retry with backoff on `DeploymentNotFound` | New deployments may take 1-5 min to propagate |

---

## Key Foundry Hosted Agent Constraints

| Constraint | Detail |
|------------|--------|
| Gateway timeout | 100 seconds (`HttpClient.Timeout`) |
| Container port | Must be 8088 (sidecar occupies 8080) |
| SSE streaming | Playground always sends `stream: true` |
| SSE event limit | Gateway may truncate long event streams — use minimal 3-event sequence |
| Error status | Always use `"completed"`, never `"failed"` |
| Hosting adapter | Required — raw HTTP frameworks don't integrate with sidecar |
| ARM publish (eastus) | Broken — use Portal UI or CLI `--protocol responses` flag |
| Auth in container | `DefaultAzureCredential` — never call at startup, always per-request |
| App Insights | Auto-configured by adapter — disable until stable |

---

## Timeline Summary

| Run | Issue Fixed | Result |
|-----|-----------|--------|
| #130 | Non-blocking startup | ❌ Still timeout (CLI flag broken) |
| #131 | Port routing theory | ❌ `--target-port` doesn't exist |
| #132 | Remove invalid flag, clean create | ❌ CLI works, still timeout (wrong framework) |
| #133 | Migrate to Foundry hosting adapter | ❌ `'anext'` error (no streaming) |
| #134-#135 | Various adapter fixes | ❌ Streaming protocol issues |
| #136 | Streaming support added | ❌ Silent hang (OpenAI blocks before events) |
| #137 | Early SSE events before OpenAI call | ❌ App Insights floods stderr |
| #138 | Disable App Insights export | ❌ Stream dies after 3 events |
| #139 | Simplify to 3-event streaming | ✅ Streaming works! But `DeploymentNotFound` |
| #140-#141 | Correct OpenAI endpoint | ❌ Still `DeploymentNotFound` (deployment name typo) |
| #142 | Add diagnostic logging | ❌ Revealed deployment length = 6 (should be 7) |
| #143 | Correct deployment secret | ✅ **Agent fully working — real LLM responses** |
