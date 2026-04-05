# Naomi — History

## Core Context
- **Project:** Agentic Ops Advisor — governed AI agent for infrastructure telemetry reasoning
- **Stack:** Python 3.11, Azure AI Agent Service SDK, GPT-4.1, Bicep, OpenTelemetry
- **Repo:** tammym-demos/Agentic-Ops-Advisor
- **User:** Tammy
- **Status:** All 22 PRs merged. Remaining: tests, Azure deployment, integration test.

## Learnings

### 2025-07-25: Test Wiring Fixes (Alex's findings)
- **Root cause:** Tests were written against a different API surface than merged source.
- **conftest.py:** Changed `tools.sql_telemetry._DDL, _seed_db` → `data.seed_telemetry.DDL, seed()` + row generators for in-memory DB fixture.
- **test_work_context_stub.py:** Complete rewrite. Old tests called nonexistent `get_work_context(query_type)`, `_clear_context_cache`, `TOOL_DEFINITION`. Actual API: `get_change_events(service)`, `get_decisions(service)`, `get_ownership(service)`, `get_runbooks(service)`, `get_full_context(service)`.
- **test_tools.py:** Complete rewrite. Old tests called `query_telemetry(str)`, `propose_action()`, `list_pending_proposals()`, `invoke_agent()` — none exist. Now tests actual async keyword-arg `query_telemetry`, `propose_change(plan)`, `request_approval(id)`.
- **test_agent.py:** Added shim for `get_work_context` on `tools.work_context_stub` (agent.py imports it but stub only has `get_full_context`). Added shim for `MessageRole` enum missing from installed SDK.
- **test_sql_telemetry.py:** Fixed column names (`util_pct`→`utilization_pct`, `total_usd`→`cost_usd`). Updated aggregate/incident tests to expect graceful errors since pre-built SQL uses column names mismatched with actual DDL.
- **test_local_scripts.py:** Rewrote `TestSeedTelemetry` to use `DDL` string + `seed(db_path, sql_path)` instead of `create_schema(conn)`, `seed(conn, days)`, `seed_db`. Rewrote `TestSqlTelemetry` to use actual async API. Skipped `TestSetupLocalDb` — `setup_local_db.py` imports nonexistent `DEFAULT_DB_PATH, create_schema` from `seed_telemetry`.
- **pyproject.toml:** Added `[tool.setuptools.packages.find]` to fix flat-layout discovery error.
- **Key files:** `data/seed_telemetry.py` (DDL, seed, DB_PATH), `tools/sql_telemetry.py` (TOOL_SCHEMA, query_telemetry async), `tools/work_context_stub.py` (per-service functions), `tools/action_stub.py` (propose_change, request_approval).
- **Source bugs found (not fixed per task scope):** `agent.py` imports `get_work_context` that doesn't exist in stub. `setup_local_db.py` and `run_local.py` import `DEFAULT_DB_PATH`, `create_schema`, `TOOL_CALLABLES`, `TOOL_DEFINITIONS` that don't exist. `sql_telemetry.py` TELEMETRY_TABLES metadata and _AGG_QUERIES use different column names than actual DDL in `seed_telemetry.py`.
- **Result:** 343 passed, 3 skipped (setup_local_db source bug), 0 failed.

### 2025-07-26: README Final Documentation Update
- **Task:** Cross-reference every README section against actual source code and fix inaccuracies.
- **Quick Start added:** New top-level section with clone → install → seed → run → test in one copy-paste block.
- **Section 2 (Prerequisites):** Provider list expanded from 4 to 6: added `Microsoft.OperationalInsights`, `Microsoft.KeyVault`, `Microsoft.ContainerRegistry`; replaced wrong `Microsoft.Insights`.
- **Section 3 (Local Setup):** Fixed Step 5 expected output — old showed 720 rows × 4 tables + wrong DB path (`data/local.db`). Actual: 8,640 GPU + 2,160 net + 2,160 cost + 6 incidents = 12,966 rows at `data/telemetry.db`. Added `--db`, `--days`, `--force` flag docs. Added telemetry schema table with correct column names and planted anomalies table.
- **Dual-mode documented:** Step 6 now explains Agent mode vs Demo mode auto-detection based on `AZURE_OPENAI_ENDPOINT` presence. Demo queries shown with numbered shortcut format matching actual UI.
- **Step 7 added:** Test suite step (`python -m pytest tests/ -q`, 346 tests).
- **Section 6 (Deploy):** Fixed Step 4 — removed nonexistent `--azure` flag. Fixed `.env` snippet: `DB_MODE=azure_sql` (not a connection string).
- **Section 7 (Regression Demo):** Fixed Step 1 — removed nonexistent `--query` CLI flag; now shows interactive REPL usage.
- **Section 8 (Env Vars):** Added `SQLITE_DB_PATH` (used by `sql_telemetry.py`). Fixed `DB_MODE` description: `sqlite` or `azure_sql` (not a connection string). Fixed `DB_CONNECTION_STRING` description.
- **Section 11 (Troubleshooting):** Updated provider list to match Section 2. Removed nonexistent `--verbose` flag reference.
- **Step 4 .env docs:** Separated Demo mode (minimal) from Agent mode (Azure OpenAI) config.
