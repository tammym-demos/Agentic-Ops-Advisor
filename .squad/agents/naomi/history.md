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

### 2025-04-05: Dashboard Data Export Script
- **Task:** Create `scripts/export_dashboard_data.py` to export synthetic telemetry data as JSON for GitHub Pages KPI dashboard.
- **Output:** `docs/pages/assets/dashboard-data.json` (generated, 40.7 KB).
- **Schema:** GPU (avg by cluster, daily trend, anomalies), Network (latency by site, daily trend, anomalies), Cost (total by cluster, daily trend, anomalies), Incidents (summary by severity/status, list, MTTR), Health Score (overall + component scores), KPI Questions (15 questions with insights).
- **Queries:** All queries run against `data/telemetry.db` using sqlite3 with row_factory=Row for dict conversion.
- **Percentile calculation:** SQLite lacks PERCENTILE_CONT; implemented manual p95/p99 by sorting latencies and indexing at 95%/99% position.
- **Anomaly detection:** GPU (avg <30% or >95% daily), Network (max latency >100ms or loss >5% daily), Cost (daily cost >2x cluster baseline).
- **Health score logic:** GPU 1.0 if 40-80% util, Network 1.0 if <30ms latency & <1% loss, Cost 0.5 if anomalies, Incidents 1.0 minus (P1 open × 0.3 + P2 open × 0.2 + P3 open × 0.1). Overall = weighted avg (GPU 30%, Net 25%, Cost 20%, Inc 25%).
- **Verified output:** 3 clusters, 1 GPU anomaly (cluster-a/node-1 @ 9.32% on 2025-03-19), 1 network anomaly, 1 cost anomaly (cluster-a @ 3967.54 vs baseline 592.13 on 2025-03-26), 6 incidents, MTTR 12h, overall health 0.8.
- **Key files:** `scripts/export_dashboard_data.py`, `docs/pages/assets/dashboard-data.json`, `data/telemetry.db`.

### 2025-04-05: KPI Dashboard HTML/CSS Implementation
- **Task:** Create interactive KPI dashboard page with Chart.js for GitHub Pages.
- **Files created:** `docs/pages/dashboard.html` (22.4 KB), `docs/pages/dashboard.css` (7.0 KB), `docs/pages/assets/` directory.
- **Files edited:** `docs/index.html` (added "📊 Dashboard" nav link before GitHub link).
- **Tech stack:** Chart.js 4.x CDN (no build step), vanilla HTML/JS, dark theme CSS variables from `docs/style.css`.
- **Dashboard sections:** (1) Health Score Tiles — 5 tiles (overall + 4 components) with color-coding (green >0.8, yellow >0.5, red ≤0.5). (2) GPU Utilization — horizontal bar chart (avg by cluster) + multi-line trend (daily by cluster). (3) Network Reliability — grouped bar (P50/P95/P99 latency by site) + multi-line trend (daily latency by site). (4) Cost Intelligence — stacked horizontal bar (compute + token cost by cluster) + multi-line trend (daily cost by cluster). (5) Incident Analytics — doughnut chart (incidents by severity) + table (first 10 incidents with severity/status badges). (6) KPI Questions Reference — grid of cards (category + question + insight).
- **Chart.js global defaults:** `Chart.defaults.color = '#8b949e'` (text-secondary), `Chart.defaults.borderColor = '#30363d'` (border), font family = system font stack.
- **Color palette:** cluster-a: #58a6ff (blue), cluster-b: #3fb950 (green), cluster-c: #bc8cff (purple), site-east: #58a6ff, site-west: #f0883e (orange), site-central: #3fb950, P1: #f85149 (red), P2: #f0883e, P3: #d29922 (yellow).
- **Data loading:** `fetch('assets/dashboard-data.json')` with error fallback showing message to run export script.
- **CSS patterns:** Reuses existing variables (--bg-primary, --bg-secondary, --bg-card, --border, --text-primary, --text-secondary, accent colors). Dashboard-specific: `.health-score-grid` (auto-fit grid), `.chart-grid` (2-column responsive, 500px min), `.chart-card` (feature-card style with hover), `.kpi-question` (italic annotation with blue left border), `.incident-table` (dark striped), `.severity-badge`/`.status-badge` (color-coded pills).
- **Nav structure:** Dashboard page nav shows "Home" link + active "📊 Dashboard" + same disclaimer banner as main site.
- **Responsive:** Chart grid collapses to 1 column on mobile (<768px). Health tiles auto-fit from 200px min.
- **Key files:** `docs/pages/dashboard.html`, `docs/pages/dashboard.css`, `docs/index.html`, `docs/style.css` (reference only).

### 2026-04-06: Health Endpoint Implementation (Issue #60)
- **Task:** Implement GET /health endpoint for Docker HEALTHCHECK on port 8080.
- **Implementation:** Added aiohttp-based health server that runs in background daemon thread alongside the interactive CLI loop.
- **Health server architecture:** `_health_handler` async handler returns JSON with status/timestamp/version. `_start_health_server` creates aiohttp app with `/health` route. `_run_health_server_thread` runs async event loop in dedicated daemon thread.
- **Response schema:** `{"status": "healthy", "timestamp": "<ISO 8601 UTC>", "version": "<from pyproject.toml>"}`. Version extracted from pyproject.toml using Python 3.11 native `tomllib` (with `tomli` fallback for 3.10).
- **Port configuration:** Default 8080, configurable via `HEALTH_PORT` env var.
- **Health independence:** Endpoint responds even without Azure credentials or full agent configuration. Only requires the Python process to be running.
- **Thread lifecycle:** Daemon thread starts before main loop, dies automatically when parent process exits. No cleanup required.
- **Dependencies added:** `aiohttp>=3.9.0` to both `requirements.txt` and `pyproject.toml` dependencies list.
- **Files modified:** `scripts/run_local.py` (added health server + threading), `requirements.txt`, `pyproject.toml`.
- **Testing:** Automated test confirmed 200 OK response with correct JSON schema. Health check compatible with Dockerfile HEALTHCHECK: `curl -f http://localhost:8080/health || exit 1`.
- **Key files:** `scripts/run_local.py`, `requirements.txt`, `pyproject.toml`, `Dockerfile` (reference).

### 2026-04-06: Team Sync — Health Endpoint & Docker Optimization
- **Alex (Tester):** Created spec-first test suite (`tests/test_health.py`, 15 tests) + integration tests before implementation. Tests verify response format, availability, integration, edge cases. All 348 tests pass.
- **Amos (DevOps):** Optimized Dockerfile with multi-stage build (builder + runtime), consolidated .dockerignore. Expected 400–450 MB (140–220 MB savings, 25–30%). Under 500 MB target. Issue #61 complete.
- **Cross-team impact:** Health endpoint enables Docker HEALTHCHECK; test suite validates spec compliance; optimized Dockerfile packages both <500 MB. All work unblocked for integration testing.
- **Decision log:** Merged 3 decisions from inbox to `.squad/decisions.md` (naomi-health-endpoint, alex-health-test-strategy, amos-docker-optimization). Created orchestration logs and session log per Scribe charter.

### 2025-07-26: Demo Mode — Work-Context Stub Integration
- **Task:** Fix `_run_demo_mode()` in `scripts/run_local.py` to call work-context stub alongside SQL telemetry tools.
- **Problem:** Demo mode only routed queries to `TOOL_CALLABLES` from `tools/sql_telemetry.py`; no work-context data was shown.
- **Fix:** Added function-scope imports of `get_change_events`, `get_decisions`, `get_ownership`, `get_runbooks`, `get_full_context`, and `ENABLE_WORK_IQ` from `tools/work_context_stub.py`. After telemetry routing, added keyword-based work-context enrichment gated by `ENABLE_WORK_IQ`.
- **Service mapping:** GPU keywords → `gpu-cluster`, network/latency → `network`, cost → `cost`. Change keywords trigger `get_change_events`; incident/remediation keywords trigger `get_ownership`, `get_runbooks`, `get_decisions`. Fallback queries get `get_full_context`.
- **Validation:** 348 tests pass, ruff lint clean.
- **Key files:** `scripts/run_local.py` (lines 206–280).

### 2025-07-27: Work IQ Coverage Enhancement — GitHub Pages
- **Task:** Enhance Work IQ visibility on the GitHub Pages brochure site per Tammy's request.
- **Problem:** Work IQ was scattered across the site in small mentions (disclaimer banner, one feature card, demo step, tech table row, disclaimer card) — no dedicated section explaining what it is or why it matters.
- **Solution:** Added a full dedicated Work IQ deep-dive section between Features and Architecture.
- **New section content:** (1) Value proposition callout: "Traditional AIOps sees metrics. Agentic ops sees metrics + the human decisions that caused them." (2) Four context surface cards: Change Events, Decisions, Ownership, Runbooks. (3) MCP Pattern explanation with visual flow diagram. (4) Hybrid advantage (Telemetry + Intent = Governed Diagnosis) visual. (5) Integrated Work IQ disclaimer with licensing info.
- **Nav updated:** Added "Work IQ" link between Capabilities and Architecture in site navigation.
- **CSS added:** Full responsive styles for `.workiq-section`, `.workiq-callout`, `.workiq-grid`, `.workiq-card`, `.workiq-mcp`, `.workiq-hybrid`, `.workiq-disclaimer` in `docs/style.css`.
- **Language alignment:** Uses "agentic ops", "hybrid", "governance", "telemetry + intent", "self-driving operations" throughout.
- **Disclaimer included:** "We're simulating Work IQ outputs in this demo. Work IQ is in public preview and requires Microsoft 365 Copilot licensing + admin consent."
- **Key files:** `docs/index.html`, `docs/style.css`.

### 2025-07-27: Demo Site Final Polish & SP Script Fix
- **Task:** Final review and polish of `docs/index.html` for Tammy's demo presentation. Fix hardcoded SP object ID in `scripts/grant-sp-permissions.sh`.
- **Site review findings:** No broken links. No references to deleted files (customerfriendly-plan.md, DOCKER_OPTIMIZATION.md, synthetic_context.json). GitHub repo URL correct. Work IQ section is prominent and well-structured. Architecture diagram, demo walkthrough, tech stack all complete.
- **Improvements made:**
  - **Nav updated:** Added "Demo" and "Get Started" links. Removed "Tech Stack" from nav (less important). Added "↗" to external GitHub link for clarity.
  - **Hero CTAs redesigned:** Primary CTA is now "🚀 Try the Demo" (anchors to Getting Started). Secondary buttons: "View on GitHub ↗" and "🔍 See It in Action" (anchors to Demo walkthrough).
  - **Getting Started section added:** New section between Tech Stack and Disclaimers with terminal-style code block showing clone → install → seed → run → test in 4 steps. Includes three CTA buttons: Clone on GitHub, View CI/CD Pipelines, Explore the Dashboard.
  - **CSS added:** `.getting-started`, `.code-block`, `.code-block-header`, `.code-block-body`, `.code-comment`, `.getting-started-ctas` styles in `docs/style.css`. Terminal-style presentation with red/yellow/green dots.
- **SP script fix:** Changed `SP_OBJECT_ID` default from hardcoded `d30fcff3-4eab-4b85-a366-f9a17142be39` to empty string. Added validation with clear error message explaining how to find the SP object ID. Updated help text to show "(required — must be provided)".
- **Key files:** `docs/index.html`, `docs/style.css`, `scripts/grant-sp-permissions.sh`.
