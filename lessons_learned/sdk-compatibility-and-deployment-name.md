# Lessons Learned: SDK Compatibility & Deployment Name Fix

**Project:** Agentic Ops Advisor  
**Dates:** April 15, 2026  
**Deploy:** Commit 6dcd6eb (Issue #1) + Commit 87118f4 (Issue #2)  
**Final Status:** ✅ Both fixes merged; smoke test PASSED for first time

---

## Executive Summary

Two distinct SDK integration issues blocked the hosted agent deployment on April 15, 2026:

1. **SDK Symbol Rename Incompatibility:** The `agent-framework-azure-ai` beta package (used by `from_agent_framework()`) references old symbol names from `azure.ai.projects.models`, but `azure-ai-projects>=2.0.0` renamed four key classes. This surfaced as an `ImportError` during the agent framework bootstrap.

2. **Wrong Constructor Parameter:** The `AzureOpenAIChatClient` from the agent framework expects `deployment_name=` parameter, but `serve.py` was passing `model=`. This caused a startup failure when the container attempted to instantiate the OpenAI client.

Both issues have been resolved via a **centralized SDK compatibility shim** (`scripts/patch_sdk_compat.py`) and a **parameter name correction** in `serve.py`. The smoke test now passes — the agent fully deploys and responds with real LLM output.

---

## Issue #1: SDK Compatibility Shim — `PromptAgentDefinitionText` ImportError

| | |
|---|---|
| **Runs** | copilot-setup-steps workflow + deploy run #6dcd6eb |
| **Symptom** | `ImportError: cannot import name 'PromptAgentDefinitionText' from 'azure.ai.projects.models'` — occurs during `from_agent_framework(agent)` in serve.py |
| **Root Cause** | The `agent-framework-azure-ai` beta package (versions >=1.0.0b251112, <=1.0.0b260107) was developed against an older version of `azure.ai.projects`. It imports old class names that were renamed in `azure-ai-projects>=2.0.0`. The import chain is: `azure.ai.agentserver.agentframework.__init__` → `_agent_framework.AgentFrameworkAgent` → `agent_framework.azure.AzureAIClient` → `agent_framework_azure_ai._client` → `from azure.ai.projects.models import PromptAgentDefinitionText` (old name, no longer exists) |
| **Symbol Mapping** | The renamed symbols are: |
| | • `PromptAgentDefinitionText` → `PromptAgentDefinitionTextOptions` |
| | • `ResponseTextFormatConfigurationJsonObject` → `TextResponseFormatJsonObject` |
| | • `ResponseTextFormatConfigurationJsonSchema` → `TextResponseFormatJsonSchema` |
| | • `ResponseTextFormatConfigurationText` → `TextResponseFormatText` |
| **Previous Approach** | Attempted inline Python shim in copilot-setup-steps.yml: `python -c "import azure.ai.projects.models as m; ..."` — this broke due to shell escaping issues and YAML indentation sensitivity |
| **Fix** | Created a **standalone, centralized SDK compatibility shim** at `scripts/patch_sdk_compat.py` that: (1) imports `azure.ai.projects.models` once, (2) uses `setattr()` to create aliases before any framework import, (3) validates the patch succeeded. Updated serve.py to call `from scripts.patch_sdk_compat import apply_compat_shim; apply_compat_shim()` at the very beginning (before any framework imports). |
| **Commit** | 6dcd6eb |
| **Lesson** | **Never use inline shell-escaped Python in CI YAML. Always centralize SDK compatibility shims as standalone Python scripts.** A centralized shim is: (1) testable locally before commit, (2) readable for future maintainers, (3) immune to YAML escaping bugs, (4) reusable across multiple entry points (serve.py, tests, scripts). The shim must run **before any framework import** — place it at the top of your main entry point, immediately after path setup and before any local imports. |

---

## Issue #2: Wrong Constructor Parameter — `model` vs `deployment_name`

| | |
|---|---|
| **Runs** | Deploy run #87118f4 (container startup crash) |
| **Symptom** | `ServiceInitializationError: Azure OpenAI deployment name is required. Set via 'deployment_name' parameter or 'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME' environment variable.` — container fails to start after the SDK compat shim is applied |
| **Root Cause** | The `AzureOpenAIChatClient` class from the `agent_framework` SDK has a **different parameter name** than the standard Azure OpenAI SDK. Standard SDK uses `model=`, but agent_framework's `AzureOpenAIChatClient` expects `deployment_name=`. The serve.py code instantiated the client with `model=settings.azure_openai_deployment`, which was silently ignored, and the `deployment_name` parameter fell back to environment variable lookup, which was also absent. |
| **Parameter Mismatch** | Standard Azure OpenAI SDK: `AzureOpenAI(model="gpt-4.1", ...)` — uses `model=` |
| | Agent Framework SDK: `AzureOpenAIChatClient(deployment_name="gpt-4.1", ...)` — uses `deployment_name=` |
| **Fix** | Changed serve.py line 189 from `model=settings.azure_openai_deployment` to `deployment_name=settings.azure_openai_deployment`. Additionally, added a **belt-and-suspenders fallback** (lines 169–172) to set the `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` environment variable if the config already sets `AZURE_OPENAI_DEPLOYMENT`. This ensures compatibility with the SDK's fallback lookup chain. |
| **Commit** | 87118f4 |
| **Lesson** | **The agent_framework SDK uses non-standard parameter names.** Before instantiating unfamiliar SDK clients, always: (1) check the SDK source code or docstring for exact parameter names, (2) do NOT assume they match the standard Azure OpenAI SDK, (3) add defensive env var fallbacks for parameters that have them. For agent_framework specifically, `AzureOpenAIChatClient` requires `deployment_name=` (not `model=`), and respects `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` env var as a fallback. |

---

## Architecture Decisions Made

### 1. Centralized SDK Compatibility Shim Location
- **Decision:** Store the shim in `scripts/patch_sdk_compat.py` rather than inline in YAML or as a utility function in the main module
- **Rationale:** (1) Standalone scripts are testable via CI without building the full agent, (2) reusable across entry points, (3) easy to document and version, (4) no dependency on YAML escaping logic
- **Import order in serve.py:** 
  1. Set default env vars (DB_MODE, ENABLE_WORK_IQ, ENABLE_MCP)
  2. Apply SDK compat shim
  3. Load .env file
  4. Configure logging
  5. Import and use framework + tools

### 2. Belt-and-Suspenders Env Var for Deployment Name
- **Decision:** In serve.py, explicitly set `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` if `AZURE_OPENAI_DEPLOYMENT` is set
- **Rationale:** The agent_framework SDK checks both the parameter AND the env var. Setting both ensures robustness if the deploy ever moves deployment name config to env vars
- **Lines:** 169–172 in serve.py

### 3. Diagnostic Logging at Startup
- **Why it matters:** After the previous hosted agent deployment issues (see foundry-hosted-agent-deployment.md), we learned the value of startup diagnostics. Logging endpoint, deployment name, and auth method at startup helps catch config errors early.
- **Implementation:** `_log_startup_diagnostics()` in serve.py logs AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT, and parsed hostname (safe to log without exposing secrets)

---

## Debugging Techniques That Worked

1. **Tracing the import chain** — The error message said `cannot import name 'PromptAgentDefinitionText'`, but didn't say where. We traced it: `from_agent_framework(agent)` → framework → azure client → agent_framework_azure_ai → azure.ai.projects.models import. This revealed the root cause was a version mismatch, not a missing package.

2. **Testing the shim standalone** — Created `scripts/patch_sdk_compat.py` with its own `__main__` block that tests both the patch and the framework import. This allowed us to validate the fix locally before pushing to CI.

3. **Parameter name validation via SDK source** — When the `ServiceInitializationError` mentioned `deployment_name` parameter, we checked the agent_framework SDK source (not just docstrings) to confirm the exact parameter name. The standard Azure OpenAI SDK uses `model=`, which was our initial assumption.

4. **Env var fallback chaining** — Documented the full fallback chain for deployment name: (1) `deployment_name=` parameter, (2) `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` env var, (3) error if neither set. This helped us add the belt-and-suspenders fix.

---

## CI/CD Updates Made

| File | Change | Why |
|------|--------|-----|
| `copilot-setup-steps.yml` | Added `python scripts/patch_sdk_compat.py` call before any framework imports | Ensure SDK compat shim runs at container startup |
| `scripts/serve.py` | (1) Import and call `apply_compat_shim()` at top; (2) Changed `model=` to `deployment_name=` in AzureOpenAIChatClient instantiation; (3) Added env var fallback for `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` | (1) Fix ImportError; (2) Fix ServiceInitializationError; (3) Defense-in-depth |
| `scripts/patch_sdk_compat.py` | New file | Centralized SDK compat shim for reusability and testability |
| `Dockerfile` | Added `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` env var (if deployment name config changes in future) | Ensure env var fallback is available in container |
| `agent.yaml` | Added `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` to container spec env vars | Match Dockerfile; ensure deploy has all config paths |

---

## Smoke Test Validation

**Before fixes:**
```
Error: ImportError: cannot import name 'PromptAgentDefinitionText' from 'azure.ai.projects.models'
```

**After SDK compat shim (Issue #1 only):**
```
Error: ServiceInitializationError: Azure OpenAI deployment name is required.
Set via 'deployment_name' parameter or 'AZURE_OPENAI_CHAT_DEPLOYMENT_NAME' environment variable.
```

**After both fixes (6dcd6eb + 87118f4):**
```
✓ Agent started on port 8088
✓ Received request: "What is the root cause of the recent GPU spike?"
✓ Queried telemetry database
✓ Generated response: [Real LLM output from GPT-4.1]
✓ Returned 200 OK with response text
```

---

## Timeline Summary

| Commit | Issue | Fix | Result |
|--------|-------|-----|--------|
| 6dcd6eb | ImportError: PromptAgentDefinitionText | SDK compat shim | ❌ ServiceInitializationError (missing `deployment_name` fix) |
| 87118f4 | ServiceInitializationError: deployment_name required | Parameter name + env var fallback | ✅ Agent fully working, smoke test PASSED |

---

## Key Takeaways

1. **SDK version mismatches are invisible until import time.** Always test framework imports early in CI, not just at the deploy stage.

2. **SDK parameter names vary by package.** The agent_framework uses different conventions than the standard Azure SDKs. Never assume — always check the source.

3. **Centralized compat shims beat inline workarounds.** A standalone Python script for SDK patches is testable, reusable, and maintainable.

4. **Belt-and-suspenders for critical parameters.** When a parameter has both a constructor argument and an env var fallback, set both to ensure robustness.

5. **Smoke tests catch integration issues.** This issue would have been caught in dev if we'd run the full agent startup (including framework imports and client instantiation) earlier in the CI pipeline.
