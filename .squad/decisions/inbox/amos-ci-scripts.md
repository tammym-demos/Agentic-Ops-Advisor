# Decision: Tool Schemas Are Now Inline in Client Scripts

**Date:** 2026-07-25  
**Author:** Amos (DevOps)  
**Status:** IMPLEMENTED  

## Context

The tool modules (`tools/sql_telemetry.py`, `tools/action_stub.py`, `tools/work_context_stub.py`) previously exported `TOOL_DEFINITIONS` / `ACTION_STUB_TOOL_DEFINITIONS` / `TOOL_SCHEMA` constants — OpenAI-format JSON dicts describing each tool's parameters. These were consumed by client scripts for PromptAgent registration.

Those constants were removed during the framework migration. The tool modules now export only callable functions.

## Decision

Client-side scripts that need tool schemas for SDK registration (e.g., `run_foundry_agent.py` PromptAgent mode) define the schemas inline rather than importing them from tool modules.

## Rationale

- Tool modules are now pure function surfaces — cleaner separation of concerns
- Schema definitions for SDK registration are a client concern, not a tool concern
- `serve.py` (production path) uses the Agent Framework which auto-discovers tool schemas from function signatures — no constants needed

## Impact

- Any future client script that registers tools with the Foundry SDK must define its own `FunctionTool` schemas
- If tool signatures change, update both the tool module AND any client-side schemas
- The production path (`serve.py` + Agent Framework) is unaffected — it uses function introspection
