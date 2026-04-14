# Agent Framework Migration Plan

> **Last updated:** 2025-07-17 — Verified against `microsoft-foundry/foundry-samples` and official SDK docs.
> **Status:** Gap analysis complete · 13 findings documented · Ready for implementation

## Problem

The Agentic Ops Advisor currently uses a **custom `FoundryCBAgent` subclass** (`scripts/serve.py`, 873 lines) that manually implements:
- The 9-event SSE streaming protocol (~250 lines)
- Manual OpenAI function-calling loop with tool dispatch (~170 lines)
- Custom response building and error handling (~100 lines)

This causes two production issues:
1. **Streaming truncation** — Foundry gateway truncates at 3 SSE events (works locally, fails through gateway)
2. **Maintenance burden** — Any protocol change requires manual updates to our custom SSE code

### Decision: Container-Only Demo

**This is a container-only deployment.** All local dev mode artifacts are removed:
- Delete `scripts/run_local.py` entirely
- Remove `aiohttp` fallback from `serve.py`
- Remove `MODE=cli` code path
- Delete `tests/test_local_scripts.py` and `tests/test_health_endpoint.py`

Rationale: local dev mode added complexity with zero production value. The demo runs in a Foundry-hosted container or not at all.

---

## Verified Agent Framework API Pattern

> Verified against `microsoft-foundry/foundry-samples` (official Microsoft samples repo).

The correct migration target uses three core APIs:

### 1. `AzureOpenAIChatClient` — Model Client

```python
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
chat_client = AzureOpenAIChatClient(
    endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1"),
    credential=credential,
    credential_scope="https://cognitiveservices.azure.com/.default",
)
```

### 2. `chat_client.create_agent()` — Agent Construction

```python
agent = chat_client.create_agent(
    name="agentic-ops-advisor",
    instructions=open("agent/system_prompt.md").read(),
    tools=[query_telemetry, get_work_context, propose_change, request_approval],
)
```

> **Note:** `create_agent()` is a method on the chat client, NOT a static method on `Agent`.
> Tools are plain Python functions — `@ai_function` decorator is optional (only for schema customization).

### 3. `from_agent_framework().run()` — Hosted Execution

```python
from azure.ai.agentserver.agentframework import from_agent_framework

from_agent_framework(agent).run()
# Handles: HTTP server on port 8088, SSE streaming, /responses endpoint
```

### Key Import Map

| Concept | Old (Current Code) | New (Agent Framework) |
|---------|-------------------|----------------------|
| Model client | `openai.AsyncAzureOpenAI` | `agent_framework.azure.AzureOpenAIChatClient` |
| Agent construction | `FoundryCBAgent` (custom subclass) | `chat_client.create_agent()` |
| Tool definition | Manual JSON schema + `_call_tool` dispatch | Plain functions with type hints (auto-generates schema) |
| Hosting | Custom SSE + aiohttp server | `from_agent_framework(agent).run()` |
| Auth | `DefaultAzureCredential` | `DefaultAzureCredential` (unchanged) |
| Token scope | Manual | `credential_scope="https://cognitiveservices.azure.com/.default"` |

## Proposed Approach

### Phase 1: Foundation — Dependencies & Cleanup (Gaps 7, 12, 13, 1)

Update the dependency stack and remove local-only code that won't exist in the new model.

**Add:**
- `agent-framework-foundry>=1.0.1,<2.0.0` (GA, selective install — pulls in `agent-framework` core)
- `azure-ai-agentserver-agentframework>=1.0.0,<2.0.0` (hosting adapter, beta — but used by official samples)

**Remove:**
- `aiohttp`, `aiohttp-cors` (adapter handles HTTP; no local fallback needed)
- `azure-ai-projects>=2.0.0` (replaced by agent-framework)
- `azure-ai-agentserver-core>=1.0.0b17` (replaced by azure-ai-agentserver-agentframework)
- `openai>=2.8.0` (pulled transitively by agent-framework)
- Any direct `agent-framework-core` / `agent-framework-azure-ai` refs (deprecated names)
- `scripts/run_local.py` (container-only — see Gap 1)

**Verify:**
- `openai` is pulled transitively by `agent-framework-foundry`. Confirm it satisfies our version needs.
- `uvicorn`, `starlette` — confirm whether the adapter bundles these or we still need them explicitly.

### Phase 2: Tool Surface Migration (Gap 5)

Current tools export three things per module: `TOOL_SCHEMA`, `TOOL_DEFINITIONS`, and `TOOL_CALLABLES`. All three are removed.

Tools become **plain Python functions with type annotations** passed directly to `create_agent(tools=[...])`:

```python
# Before (manual JSON schema + dispatch):
TOOL_SCHEMA = {...}
TOOL_DEFINITIONS = [{"type": "function", "function": {"name": "query_telemetry", ...}}]
TOOL_CALLABLES = {"query_telemetry": query_telemetry_impl}
async def _call_tool(name, arguments): ...

# After (Agent Framework auto-generates schema from type annotations):
async def query_telemetry(
    table: str | None = None,
    aggregate: str | None = None,
    sql: str | None = None,
    limit: int = 100,
    filters: dict[str, str] | None = None,
) -> str:
    """Query synthetic infrastructure telemetry data stored in SQL.
    Covers GPU utilisation, network throughput/latency, cost, and incidents."""
    ...

# @ai_function decorator is OPTIONAL — only needed for schema customization
# (e.g., overriding parameter descriptions, adding enum constraints)
```

**Files affected:** `tools/sql_telemetry.py`, `tools/work_context_stub.py`, `tools/action_stub.py`

Remove all `TOOL_SCHEMA`, `TOOL_DEFINITIONS`, and `TOOL_CALLABLES` exports. Remove `_call_tool` dispatch from `serve.py`.

### Phase 3: Core Rewrite — serve.py + Client + Init (Gaps 6, 9, 4)

The ~873-line serve.py collapses to ~150-200 lines using the verified pattern:

```python
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import DefaultAzureCredential
from azure.ai.agentserver.agentframework import from_agent_framework

# 1. Seed DB (unchanged)
_ensure_db()

# 2. Client — uses AZURE_OPENAI_ENDPOINT (already in our config)
credential = DefaultAzureCredential()
chat_client = AzureOpenAIChatClient(
    endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    model=os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1"),
    credential=credential,
    credential_scope="https://cognitiveservices.azure.com/.default",
)

# 3. Load system prompt
system_prompt = Path("agent/system_prompt.md").read_text()

# 4. Agent — factory method on client, NOT Agent(client=..., tools=[...])
agent = chat_client.create_agent(
    name="agentic-ops-advisor",
    instructions=system_prompt,
    tools=[query_telemetry, get_work_context, propose_change, request_approval],
)

# 5. Serve — confirmed to serve /responses on port 8088
from_agent_framework(agent).run()
```

**Keep:** `_ensure_db()`, `_parse_input_to_messages()`, `_log_startup_diagnostics()`

**Remove:**
- `AgenticOpsAgent` class and all SSE code
- `_stream_with_keepalive`, `_stream_text`, `_build_response`
- `_run_agent_conversation`, `_call_tool`
- All SSE event imports
- `MODE=cli` code path
- aiohttp fallback server

**Unknown:** Whether `from_agent_framework(agent).run()` exposes `/readiness` and `/liveness` health endpoints, or only `/responses`. If not, we may need a thin wrapper. **This needs testing.**

### Phase 4: Agent Manifest & Prompt (Gaps 3, 4)

- Clean `agent.yaml` — remove manual tool JSON schemas (now auto-generated by framework from function signatures)
- `instructions_file` field: evaluate whether Foundry Agent Service manifest still consumes this, or if `create_agent(instructions=...)` is the sole mechanism
- Retain container, model, and protocol sections (still needed for deployment manifest)
- Review for stale references to old class names or config keys

### Phase 5: Tests, Setup Scripts & CI/CD (Gaps 2, 8, 11)

The test suite needs a **near-complete rewrite** due to the scope of changes:

**Delete:**
- `tests/test_health_endpoint.py` — health endpoints change (or disappear) with the adapter
- `tests/test_local_scripts.py` — `run_local.py` is being deleted

**Rewrite:**
- `tests/test_serve.py` — all mocks target the old `AgenticOpsAgent` / `FoundryCBAgent` / aiohttp patterns. Rewrite to test the `AzureOpenAIChatClient` + `create_agent()` + `from_agent_framework()` pattern.

**Keep (with adjustments):**
- `tests/test_tools.py` — tool logic is unchanged; remove imports of `TOOL_DEFINITIONS` / `TOOL_CALLABLES`
- `tests/test_data.py` — data generation is unchanged
- Integration / eval tests — review for broken imports but logic is stable

**CI/CD:**
- Update `deploy.yml` pip install steps for new package names
- Remove references to `run_local.py` from workflows
- Audit all `scripts/` for old imports (`azure.ai.projects` → `agent_framework`)

### Phase 6: Deployment & Validation (Gap 10)

- Update Bicep templates for any new Foundry Agent Service resource properties
- `requirements.txt` updated per Phase 1
- Remove `scripts/run_local.py` (container-only decision)
- SQLite seeding at build time stays exactly the same
- `EXPOSE 8088` stays the same
- `ENTRYPOINT ["python", "scripts/serve.py"]` stays the same
- Verify no Dockerfile references to `aiohttp` or `run_local.py`
- Deploy and verify in Foundry Playground

### Phase 7: Copilot SDK Assessment (no code changes)

**Verdict: Not viable for production container, useful for local dev tooling.**

| Use Case | Viable? | Why |
|----------|---------|-----|
| Core agent backend | ❌ | BYOK requires API keys (disabled by policy); GitHub auth uses premium quota |
| Container deployment | ❌ | Requires bundling ~100MB CLI binary in Docker image |
| Local dev companion | ✅ | Use user's GitHub Copilot subscription for code analysis |
| Evaluation harness | ⚠️ | `GitHubCopilotAgent` as eval judge, but adds complexity vs current eval |
| Multi-agent workflow | ⚠️ | Future: ops advisor (Foundry) + code reviewer (Copilot) in Agent Framework Workflow |

The Copilot SDK has a first-class Agent Framework integration (`agent-framework-github-copilot` package, `GitHubCopilotAgent` class). If API key policy changes in the future, we could add Copilot as a second provider in a multi-agent workflow.

### Cross-Cutting Items

These don't fit cleanly into a single phase but must be addressed:

1. **Tracing migration** — Current OpenTelemetry instrumentation likely hooks into the old `FoundryCBAgent` code. Verify Agent Framework provides its own OTel hooks or adapt our instrumentation.

2. **`agent/config.py` adaptation** — Config module may export old class names, tool schemas, or mode flags (`MODE=cli`). Simplify to match the new pattern.

3. **`scripts/run_foundry_agent.py` review** — If this exists, check whether it duplicates the new pattern or should be deleted.

4. **`eval/` and `scripts/regression_demo.py` review** — These may import from serve.py or tools in ways that break after migration. Audit imports.

---

## Gap Analysis — 13 Findings

> Findings from verification against `microsoft-foundry/foundry-samples` and current codebase audit.

### Gap 1: Remove `run_local.py` — Container-Only Demo

| Field | Value |
|-------|-------|
| **File** | `scripts/run_local.py` |
| **Confidence** | 🟢 High |
| **Phase** | 1 (Foundation) |
| **Dependencies** | None |
| **Effort** | Small |

**Finding:** `run_local.py` provides a standalone local runner that bypasses the container hosting
model. In the Agent Framework pattern, `from_agent_framework(agent).run()` handles both local dev
and production hosting. Keeping `run_local.py` creates confusion about the correct entry point.

**Action:** Delete `scripts/run_local.py`. Update any documentation referencing local runner.

---

### Gap 2: Rewrite Test Suite for New Agent Framework APIs

| Field | Value |
|-------|-------|
| **Files** | `tests/test_serve.py`, `tests/test_tools.py`, `tests/test_agent.py` |
| **Confidence** | 🟢 High |
| **Phase** | 5 (Tests & CI/CD) |
| **Dependencies** | Gap 6 (client migration), Gap 9 (initialization rewrite) |
| **Effort** | Medium |

**Finding:** Current tests mock `openai.AsyncAzureOpenAI` and the custom `FoundryCBAgent` class.
These mocks will break when we switch to `AzureOpenAIChatClient` and `create_agent()`.

**Action:** Replace all `FoundryCBAgent`/aiohttp mocks with `AzureOpenAIChatClient` + `create_agent()` pattern. Test tool schema auto-generation. Add adapter wiring integration test.

---

### Gap 3: Clean Up `agent.yaml` — Remove Deprecated Fields

| Field | Value |
|-------|-------|
| **File** | `agent.yaml` |
| **Confidence** | 🟡 Medium |
| **Phase** | 4 (Manifest & Prompt) |
| **Dependencies** | Gap 5 (tool definitions) |
| **Effort** | Small |

**Finding:** `agent.yaml` currently contains full manual tool JSON schemas (lines 63–183) that
duplicate what the Agent Framework will auto-generate from function signatures. The `instructions_file`
field (line 56) may also need updating depending on how the manifest is consumed.

**Action:** Remove manual `tools:` section. Evaluate `instructions_file` usage. Retain container, model, and protocol sections. Test empirically — no canonical JSON schema exists for this manifest.

---

### Gap 4: Update System Prompt Integration

| Field | Value |
|-------|-------|
| **Files** | `agent/system_prompt.md`, `scripts/serve.py` |
| **Confidence** | 🟢 High |
| **Phase** | 3 (Core Rewrite) |
| **Dependencies** | Gap 9 (initialization rewrite) |
| **Effort** | Small |

**Finding:** System prompt is currently loaded in the custom `FoundryCBAgent.__init__` and passed
to the OpenAI chat completion API. In the Agent Framework pattern, it's passed to
`create_agent(instructions=...)`. System prompt content itself does not need changes — only the loading mechanism.

**Action:** Load `agent/system_prompt.md` at startup and pass as `instructions` parameter to `chat_client.create_agent()`. Remove custom prompt-loading logic.

---

### Gap 5: Update Tool Definitions to Agent Framework Format

| Field | Value |
|-------|-------|
| **Files** | `tools/sql_telemetry.py`, `tools/work_context_stub.py`, `tools/action_stub.py` |
| **Confidence** | 🟢 High |
| **Phase** | 2 (Tool Surface Migration) |
| **Dependencies** | Gap 7 (requirements update) |
| **Effort** | Medium |

**Finding:** Tools currently export manual JSON schema dicts (`TOOL_SCHEMA`, `TOOL_DEFINITIONS`, `TOOL_CALLABLES`) and are dispatched via a `_call_tool()` function in `serve.py`. The Agent Framework auto-generates schemas from Python type hints and docstrings.

**Action:** Remove all schema exports. Add full type hints to all parameters. Ensure docstrings are complete (framework uses first line as description). Pass tool functions directly to `create_agent(tools=[...])`.

---

### Gap 6: Migrate from Old Client to `AzureOpenAIChatClient`

| Field | Value |
|-------|-------|
| **Files** | `scripts/serve.py` |
| **Confidence** | 🟢 High |
| **Phase** | 3 (Core Rewrite) |
| **Dependencies** | Gap 7 (requirements update) |
| **Effort** | Medium |

**Finding:** Current code uses `openai.AsyncAzureOpenAI` directly for chat completions with
manual function-calling loop management. The verified pattern uses `AzureOpenAIChatClient`
from `agent_framework.azure` with `credential_scope` for token acquisition.

**Action:** Replace `openai.AsyncAzureOpenAI(...)` with `AzureOpenAIChatClient(endpoint, model, credential, credential_scope)`. Remove direct OpenAI chat completion calls and the manual function-calling loop.

---

### Gap 7: Update `requirements.txt` with Correct Packages

| Field | Value |
|-------|-------|
| **File** | `requirements.txt` |
| **Confidence** | 🟢 High |
| **Phase** | 1 (Foundation) |
| **Dependencies** | None |
| **Effort** | Small |

**Finding:** Current `requirements.txt` references `azure-ai-projects`, `azure-ai-agentserver-core`,
`aiohttp`, `aiohttp-cors`, and `openai` directly. These need to be replaced with Agent Framework packages.

**Action:**
```
Add:
  agent-framework-foundry>=1.0.1,<2.0.0
  azure-ai-agentserver-agentframework>=1.0.0,<2.0.0

Remove:
  azure-ai-projects>=2.0.0,<3.0.0      # Replaced by agent-framework
  azure-ai-agentserver-core>=1.0.0b17   # Replaced by azure-ai-agentserver-agentframework
  aiohttp>=3.9.0                         # HTTP now handled by adapter
  aiohttp-cors>=0.7.0                   # CORS now handled by adapter
  openai>=2.8.0,<3.0.0                  # Pulled transitively

Keep:
  azure-identity, azure-monitor-opentelemetry, opentelemetry-*
  python-dotenv, pyodbc, aiosqlite
  uvicorn, starlette (verify if still needed)
  pytest, pytest-asyncio, ruff
  azure-ai-evaluation, promptflow-core
```

---

### Gap 8: Update Setup Scripts for New Workflow

| Field | Value |
|-------|-------|
| **Files** | `scripts/*.py`, `Dockerfile` |
| **Confidence** | 🟡 Medium |
| **Phase** | 5 (Tests & CI/CD) |
| **Dependencies** | Gap 7 (requirements update) |
| **Effort** | Small |

**Finding:** Setup scripts may reference old package names or initialization patterns.
DB seeding logic itself is unchanged, but any scripts that import from `azure.ai.projects`
or instantiate the old client need updating.

**Action:** Audit all scripts in `scripts/` for old imports. Update references to `azure.ai.projects` → `agent_framework`. DB seeding (`_ensure_db()`) stays the same — it's SQLite-native, no SDK dependency.

---

### Gap 9: Rewrite Initialization Sequence

| Field | Value |
|-------|-------|
| **File** | `scripts/serve.py` |
| **Confidence** | 🟢 High |
| **Phase** | 3 (Core Rewrite) |
| **Dependencies** | Gap 5 (tool definitions), Gap 6 (client migration), Gap 7 (requirements) |
| **Effort** | Large |

**Finding:** The current initialization sequence is: load env → seed DB → create `AsyncAzureOpenAI` client → build tool defs manually → instantiate `AgenticOpsAgent(FoundryCBAgent)` → start custom aiohttp server.

**New sequence:** load env → seed DB → create `AzureOpenAIChatClient` → load system prompt → `chat_client.create_agent()` → `from_agent_framework(agent).run()`. Removes ~600 lines of custom SSE, OpenAI loop, and response building. Target: ~150-200 lines.

---

### Gap 10: Update Deployment Scripts (Bicep/ARM)

| Field | Value |
|-------|-------|
| **Files** | `infra/*.bicep` |
| **Confidence** | 🟡 Medium |
| **Phase** | 6 (Deployment) |
| **Dependencies** | Gap 3 (agent.yaml cleanup) |
| **Effort** | Medium |

**Finding:** Bicep templates may reference old resource properties or container configurations
that change with the Agent Framework migration. The container image, port, and health check
endpoints should remain the same, but agent registration properties may differ.

**Action:** Audit `infra/` Bicep templates for agent-specific resource properties. Verify manifest compatibility. Test in staging before production.

---

### Gap 11: Update CI/CD Workflows

| Field | Value |
|-------|-------|
| **Files** | `.github/workflows/deploy.yml`, `.github/workflows/ci.yml` |
| **Confidence** | 🟢 High |
| **Phase** | 5 (Tests & CI/CD) |
| **Dependencies** | Gap 7 (requirements), Gap 2 (tests) |
| **Effort** | Small |

**Finding:** CI/CD workflows install old package names and may run tests that reference
the old client classes. Package install steps and test commands need updating.

**Action:** Update pip install steps. Ensure test steps pass with rewritten test suite. Remove workflow references to `run_local.py`.

---

### Gap 12: Remove Local Runner Dependencies

| Field | Value |
|-------|-------|
| **Files** | `scripts/run_local.py`, `requirements.txt`, docs |
| **Confidence** | 🟢 High |
| **Phase** | 1 (Foundation) |
| **Dependencies** | Gap 1 (remove run_local.py) |
| **Effort** | Small |

**Finding:** `run_local.py` imports `aiohttp` and `aiohttp-cors` for a standalone HTTP server.
These packages are only needed for the local runner pattern, which is superseded by
`from_agent_framework(agent).run()`.

**Action:** Remove `aiohttp` and `aiohttp-cors` from `requirements.txt` (part of Gap 7). Remove conditional imports or code paths that check for local-runner mode. Update README and docs.

---

### Gap 13: Add Agent Framework Version Constraints

| Field | Value |
|-------|-------|
| **Files** | `requirements.txt`, `pyproject.toml` |
| **Confidence** | 🟢 High |
| **Phase** | 1 (Foundation) |
| **Dependencies** | None |
| **Effort** | Small |

**Finding:** The Agent Framework is at 1.0.1 GA but is actively evolving. Without upper-bound
version constraints, a future breaking change could silently break the build.

**Action:** Pin `agent-framework-foundry>=1.0.1,<2.0.0` and `azure-ai-agentserver-agentframework>=1.0.0,<2.0.0`. Add a comment in `requirements.txt` noting the version constraint rationale.

---

## Gap Dependency Graph

```
Phase 1 — Foundation (start here, no dependencies)
  Gap 13 (version constraints) ──┐
  Gap 7  (requirements.txt)  ────┤── No dependencies
  Gap 1  (remove run_local.py) ──┤
  Gap 12 (remove local deps)  ───┘── Depends on Gap 1

Phase 2 — Tool Surface
  Gap 5  (tool definitions)  ──────── Depends on Gap 7

Phase 3 — Core Rewrite
  Gap 6  (client migration)  ──┐
  Gap 9  (init sequence)     ──┤──── Depends on Gaps 5, 6, 7
  Gap 4  (system prompt)     ──┘──── Depends on Gap 9

Phase 4 — Manifest
  Gap 3  (agent.yaml)        ──────── Depends on Gap 5

Phase 5 — Tests & CI/CD
  Gap 2  (test suite)        ──┐
  Gap 8  (setup scripts)    ──┤──── Depends on Gaps 6, 9
  Gap 11 (CI/CD workflows)  ──┘──── Depends on Gaps 2, 7

Phase 6 — Deployment
  Gap 10 (Bicep/ARM)         ──────── Depends on Gap 3
```

## Architecture After Migration

```
┌─────────────────────────────────────────────────────────┐
│ Container (Docker, port 8088)                            │
│                                                          │
│  scripts/serve.py (~150 lines)                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Agent Framework (≥1.0.1)                            │ │
│  │                                                     │ │
│  │  AzureOpenAIChatClient (agent_framework.azure)      │ │
│  │    - endpoint: AZURE_OPENAI_ENDPOINT (env var)      │ │
│  │    - model: gpt-4.1                                 │ │
│  │    - credential: DefaultAzureCredential()           │ │
│  │    - scope: cognitiveservices.azure.com/.default     │ │
│  │         ↓                                           │ │
│  │  chat_client.create_agent(                          │ │
│  │    name="agentic-ops-advisor",                      │ │
│  │    instructions=system_prompt,                      │ │
│  │    tools=[                                          │ │
│  │        query_telemetry,     # plain function        │ │
│  │        get_work_context,    # plain function        │ │
│  │        propose_change,      # plain function        │ │
│  │        request_approval,    # plain function        │ │
│  │    ],                                               │ │
│  │  )                                                  │ │
│  │         ↓                                           │ │
│  │  from_agent_framework(agent).run()                  │ │
│  │    - HTTP server (port 8088)                        │ │
│  │    - SSE streaming (9-event protocol)               │ │
│  │    - /responses endpoint (confirmed)                │ │
│  │    - /readiness, /liveness (⚠️ unconfirmed)         │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  data/telemetry.db (SQLite, seeded at build time)        │
│  agent/system_prompt.md                                  │
│  tools/ (plain Python functions, no decorators needed)   │
└─────────────────────────────────────────────────────────┘
```

## Implementation Todos (Updated with Gaps)

| # | ID | Title | Phase | Gap | Confidence | Effort | Dependencies | Description |
|---|-----|-------|-------|-----|-----------|--------|-------------|-------------|
| 1 | version-constraints | Add version constraints | 1 | 13 | 🟢 High | S | — | Pin `agent-framework-foundry>=1.0.1,<2.0.0`, `azure-ai-agentserver-agentframework>=1.0.0,<2.0.0`. |
| 2 | update-deps | Update requirements.txt | 1 | 7 | 🟢 High | S | #1 | Replace deprecated packages. Remove `aiohttp`, `aiohttp-cors`, `openai`, `azure-ai-projects`, `azure-ai-agentserver-core`. |
| 3 | remove-local-runner | Remove run_local.py | 1 | 1, 12 | 🟢 High | S | — | Delete `scripts/run_local.py`. Remove local runner deps. Update docs. |
| 4 | convert-tools | Convert tools to plain functions | 2 | 5 | 🟢 High | M | #2 | Remove `TOOL_SCHEMA`/`TOOL_DEFINITIONS`/`TOOL_CALLABLES`. Add type hints. Pass functions to `create_agent()`. |
| 5 | migrate-client | Migrate to AzureOpenAIChatClient | 3 | 6 | 🟢 High | M | #2 | Replace `openai.AsyncAzureOpenAI` with `AzureOpenAIChatClient` from `agent_framework.azure`. |
| 6 | rewrite-init | Rewrite initialization sequence | 3 | 9 | 🟢 High | L | #4, #5 | Rewrite serve.py: load env → seed DB → create client → load prompt → `create_agent()` → `from_agent_framework(agent).run()`. |
| 7 | update-prompt | Update system prompt integration | 3 | 4 | 🟢 High | S | #6 | Load `system_prompt.md`, pass as `instructions` to `create_agent()`. |
| 8 | clean-agent-yaml | Clean up agent.yaml | 4 | 3 | 🟡 Medium | S | #4 | Remove manual tool schemas. Evaluate `instructions_file`. Keep container/model/protocol. |
| 9 | rewrite-tests | Rewrite test suite | 5 | 2 | 🟢 High | M | #6 | Mock `AzureOpenAIChatClient` + `create_agent()`. Delete stale test files. |
| 10 | update-setup | Update setup scripts | 5 | 8 | 🟡 Medium | S | #2 | Audit `scripts/` for old imports. Update `azure.ai.projects` → `agent_framework`. |
| 11 | update-cicd | Update CI/CD workflows | 5 | 11 | 🟢 High | S | #2, #9 | Update pip install steps, test commands, remove `run_local.py` refs. |
| 12 | update-bicep | Update deployment scripts | 6 | 10 | 🟡 Medium | M | #8 | Audit Bicep for agent resource properties. Test in staging. |
| 13 | deploy-verify | Deploy and verify in Foundry | 6 | — | 🟢 High | M | #9, #12 | Deploy via CI, verify in Foundry Playground. Validate streaming, tools, health. |
| 14 | update-lessons | Document in lessons_learned | — | — | 🟢 High | S | — | Write Copilot SDK assessment + Agent Framework migration notes. |

## Key Risks & Mitigations

| Risk | Status | Mitigation |
|------|--------|-----------|
| `from_agent_framework(agent).run()` doesn't serve `/responses` | ✅ **Confirmed** — official samples use this exact pattern on port 8088 | N/A — verified |
| `AzureOpenAIChatClient` import path | ✅ **Confirmed** — `from agent_framework.azure import AzureOpenAIChatClient` | N/A — verified |
| Token scope mismatch | ✅ **Confirmed** — `https://cognitiveservices.azure.com/.default` matches existing auth config | N/A — verified |
| Health endpoints (`/readiness`, `/liveness`) not exposed by adapter | ⚠️ **Unknown** | Test with adapter; may need thin wrapper or Dockerfile HEALTHCHECK fallback |
| `azure-ai-agentserver-agentframework` is beta | ⚠️ **Risk** | Used by official samples, so unlikely to break. Pin version. Monitor for GA release. |
| `openai` transitive dependency version conflict | ⚠️ **Unknown** | Run `pip install` and check resolved version against our needs |
| Streaming still truncated after migration | **Mitigated** | Using official adapter gives us support leverage. If gateway is the root cause, the fix is the same either way. |
| Tool schema generation differs from manual schemas | **Mitigated** | Test each tool locally. Agent Framework uses type annotations — our functions already have them. |
| DB seeding timing with new adapter | **Mitigated** | Keep synchronous `_ensure_db()` call before `from_agent_framework().run()` |
| Near-complete test rewrite scope | ⚠️ **Risk** | Large effort. Prioritize `test_serve.py` rewrite; `test_tools.py` changes are minimal. |
| Agent Framework breaking changes in minor versions | **Mitigated** | Pin `>=1.0.1,<2.0.0`. Run CI on every dependency update. |

## Reference Links

- [Agent Framework Overview](https://learn.microsoft.com/en-us/agent-framework/overview/?pivots=programming-language-python)
- [Foundry Agent Service Overview](https://learn.microsoft.com/en-us/azure/foundry/agents/overview)
- [Hosted Agents Concept](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/hosted-agents)
- [Hosted Agent Quickstart](https://learn.microsoft.com/en-us/azure/foundry/agents/quickstarts/quickstart-hosted-agent?pivots=programming-language-python)
- [Agent Framework + Foundry Provider](https://learn.microsoft.com/en-us/agent-framework/agents/providers/microsoft-foundry?pivots=programming-language-python)
- [Agent Framework Tools](https://learn.microsoft.com/en-us/agent-framework/agents/tools/?pivots=programming-language-python)
- [Official Hosted Agent Sample (foundry-samples)](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/python/hosted-agents/agent-framework/agent-with-foundry-tools/)
- [Copilot SDK](https://github.com/github/copilot-sdk)
- [Copilot SDK + Agent Framework Integration](https://github.com/github/copilot-sdk/blob/main/docs/integrations/microsoft-agent-framework.md)
