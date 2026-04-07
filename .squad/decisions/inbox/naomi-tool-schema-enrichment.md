# Decision: Tool Schema Enrichment Pattern

**Author:** Naomi (Backend Dev)
**Date:** 2025-07-26
**Issue:** #92

## Context
GPT-4.1 was generating wrong tool parameters because schemas lacked column names, dialect hints, and valid service enums.

## Decisions Made

1. **Dynamic schema descriptions from data dicts.** `TOOL_SCHEMA` for `query_telemetry` now builds the `table` description from `TELEMETRY_TABLES` at import time. If anyone adds a table or column, the schema stays in sync automatically.

2. **`work_context_stub.py` now owns its TOOL_SCHEMA.** Previously, `serve.py` had an inline dict. Moved to the module itself (`TOOL_SCHEMA`, `get_tool_definition()`, `TOOL_DEFINITIONS`, `TOOL_CALLABLES`) — same pattern as `sql_telemetry.py` and `action_stub.py`. `serve.py` now imports it.

3. **`_CLUSTER_TO_SERVICE` fuzzy mapping.** New dict maps common cluster/host name fragments (e.g. `prod-east`, `cdn`, `billing`) to service categories. `_service_key()` checks this before falling back to `"default"`.

## Impact
- All three tool modules now follow the same schema export pattern.
- `serve.py` is thinner — no more inline schema duplication.
- LLM should produce fewer wrong-dialect SQL queries and invalid service names.

## Team Notes
- Holden: No architecture change here — just enriching existing schemas and making them consistent. Let me know if you want the aggregate descriptions to be even more granular.
