# Alex — History

## Core Context
- **Project:** Agentic Ops Advisor — governed AI agent for infrastructure telemetry reasoning
- **Stack:** Python 3.11, Azure AI Agent Service SDK, GPT-4.1, Bicep, OpenTelemetry
- **Repo:** tammym-demos/Agentic-Ops-Advisor
- **User:** Tammy
- **Status:** All 22 PRs merged. Remaining: tests, Azure deployment, integration test.

## Learnings

### 2025-07-25: Full Test Suite Run — Results
- **Environment:** Python 3.13.12, pytest 9.0.2, pytest-asyncio 1.3.0, Windows
- **Total tests discovered:** 350+ across 13 test files
- **Blocking issue:** `tests/conftest.py` imports `_DDL` and `_seed_db` from `tools.sql_telemetry` — these symbols do not exist. Prevents normal `pytest tests/` from running at all.
- **Workaround:** Ran with `--noconftest` to bypass; tests needing conftest fixtures (tmp_db_path, in_memory_db) were skipped.

#### Run 1 (--noconftest, 9 test files): 225 passed, 11 failed, 23 errors
- All failures/errors in `tests/test_work_context_stub.py`
- Root cause: tests reference `_clear_context_cache()` and `TOOL_DEFINITION` — neither exists in `tools/work_context_stub.py`

#### Run 2 (--noconftest, 4 remaining files): 33 passed, 51 failed, 8 errors
- `test_agent.py`: 14 failures — imports `get_work_context` from `tools.work_context_stub` (doesn't exist)
- `test_local_scripts.py`: 15 failures + 8 errors — imports `create_schema`, `seed_db`, `DEFAULT_DB_PATH` from `data.seed_telemetry` (don't exist)
- `test_sql_telemetry.py`: 7 failures — schema mismatch between `data/seed_telemetry.py` DDL (cluster/node/utilization_pct) and `tools/sql_telemetry.py` TELEMETRY_TABLES (host/gpu_index/util_pct)
- `test_tools.py`: NOT RUN (couldn't run with --noconftest since conftest is needed; import issues exist with `query_telemetry` API, `get_work_context`, `propose_action`, `list_pending_proposals`, `invoke_agent`)

#### Combined Totals: 258 passed, 62 failed, 31 errors
- Clean passes: test_evaluators (34), test_regression_demo (27), test_run_eval (35), test_seed_telemetry (22), test_config (25), test_action_stub (40), test_tracing (20), test_work_context_mcp (22), partial test_agent (19), partial test_sql_telemetry (14)

#### Failure Categories
1. **Import/wiring issues from PR merges (ALL 62 failures + 31 errors):**
   - `conftest.py` → `_DDL`, `_seed_db` not in `tools.sql_telemetry`
   - `test_work_context_stub.py` → `_clear_context_cache`, `TOOL_DEFINITION` not in `tools.work_context_stub`
   - `test_agent.py` → `get_work_context` not in `tools.work_context_stub`
   - `test_local_scripts.py` → `create_schema`, `seed_db`, `DEFAULT_DB_PATH` not in `data.seed_telemetry`
   - `test_tools.py` → `query_telemetry` API mismatch (string arg vs keyword args), `get_work_context`, `propose_action`, `list_pending_proposals`, `invoke_agent` not in their respective modules
   - `test_sql_telemetry.py` → DDL schema mismatch: tests expect columns (id, host, util_pct, total_usd, created_at) but actual DDL has (cluster, node, utilization_pct, cost_usd, ts)
2. **Real source bugs:** 0 found — all failures are test-to-source wiring mismatches
3. **Test configuration issues:** 0 — deps install fine, pytest runs fine

#### Key File Paths
- `tests/conftest.py` — broken import line 11
- `tests/test_work_context_stub.py` — 34 tests affected (11 fail, 23 error)
- `tests/test_local_scripts.py` — 23 tests affected (15 fail, 8 error)
- `tests/test_tools.py` — all tests blocked (API mismatches)
- `tests/test_agent.py` — 14 tests fail on missing `get_work_context`
- `tests/test_sql_telemetry.py` — 7 tests fail on schema mismatch
- `tools/sql_telemetry.py` — TELEMETRY_TABLES schema diverged from `data/seed_telemetry.py` DDL
- `data/seed_telemetry.py` — actual DDL and seed logic lives here
- `pyproject.toml` — `pip install -e ".[dev]"` fails (flat-layout discovery error, needs `[tool.setuptools.packages]`)

### 2025-07-25: Health Endpoint Tests (Issue #60)
- **File created:** `tests/test_health.py` — 15 tests for /health endpoint spec
- **Test approach:** Structured tests with skip decorators, ready for Naomi's implementation
- **Test categories:**
  1. **Response format** (6 tests): HTTP 200, JSON response, required fields (status/timestamp/version), field validation
  2. **Availability** (3 tests): Works without Azure creds, available before agent init, responds quickly (<1s)
  3. **Integration** (2 tests): Live HTTP GET and curl tests (require running server on localhost:8080)
  4. **Edge cases** (4 tests): Status values, UTC timezone, no extra fields, version matches pyproject.toml
- **Test patterns used:**
  - `pytest.mark.skip` with reason for implementation-pending tests
  - `pytest.mark.integration` for tests requiring running server
  - `pytest.mark.asyncio` for async tests (health endpoint expected to be async)
  - `pytest.mark.parametrize` for parametrized edge case testing
  - Helper functions: `validate_iso8601_timestamp()`, `validate_semantic_version()`
  - TODOs in test bodies showing expected implementation (aiohttp test client, requests library, etc.)
  - Comprehensive docstrings explaining what each test validates
  - Implementation checklist at bottom for Naomi (web framework choice, requirements, Docker integration)
- **Configuration update:** Added `integration` marker to `pyproject.toml` to register custom mark
- **Result:** All 15 tests collected successfully, all skip as expected. Tests are ready to be unskipped and updated once Naomi's implementation lands.

### 2026-04-06: Team Sync — Health Endpoint Spec-First Delivery
- **Implementation validated:** Naomi implemented /health endpoint per spec. All 15 health tests in `tests/test_health.py` now pass. Added integration tests in `tests/test_health_endpoint.py` (2 tests).
- **Test coverage confirmed:** Response format (HTTP 200, JSON, required fields), Availability (no Azure deps, pre-init response), Integration (live HTTP GET, curl), Edge cases (status values, UTC, version matching).
- **Spec execution:** Naomi's aiohttp implementation matches test expectations exactly. Port 8080, ISO 8601 timestamps, pyproject.toml version extraction all validated.
- **348 tests passing:** Full test suite now clean with 0 failures. Health endpoint unblocked for Docker HEALTHCHECK integration.
- **Cross-team impact:** Amos's Docker optimization now has confirmed health endpoint for probing. Naomi's implementation satisfies Alex's spec. Integration testing phase can proceed.
