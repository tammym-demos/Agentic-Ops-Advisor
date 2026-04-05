# Plan: KPI Metrics Dashboard — GitHub Pages

## Problem Statement

The Agentic Ops Advisor has rich synthetic telemetry data (GPU, network, cost,
incidents) and pre-built aggregate queries, but no visual dashboard for humans
to explore KPIs at a glance.  The existing GitHub Pages site (`docs/`) is a
brochure/marketing page only — it doesn't visualize any actual data.

## Proposed Approach

Build a **KPI Metrics Dashboard** as a new page in the GitHub Pages site
(`docs/pages/dashboard.html`) that:

1. Loads the synthetic telemetry data from a pre-exported JSON file
2. Renders interactive charts using **Chart.js** (lightweight, CDN-hosted, no build step)
3. Matches the existing dark-theme design system (`style.css`)
4. Includes curated "KPI questions humans would ask" tied to each visualization

## Data Pipeline

Create a Python script (`scripts/export_dashboard_data.py`) that:
- Reads `data/telemetry.db` using the existing `seed_telemetry` module
- Runs the 6 pre-built aggregate queries + custom KPI rollups
- Exports a single `docs/pages/assets/dashboard-data.json` file
- The JSON is committed and served statically (no server-side DB needed)

## KPI Categories & Recommended Human Questions

### 1. GPU Utilization Health
- **"What is my average GPU utilization across clusters?"** — Are we over/under-provisioned?
- **"Which nodes are running hot (>85%) or cold (<30%)?"** — Spot waste or capacity risk
- **"When did GPU utilization anomalies occur?"** — Timeline view with anomaly markers

### 2. Network Reliability
- **"What is my P50/P95/P99 network latency by site?"** — SLA compliance check
- **"Which sites have elevated packet loss?"** — Identify degraded links
- **"What is my throughput trend?"** — Capacity planning signal

### 3. Cost Intelligence
- **"What is my total spend by cluster?"** — Budget allocation view
- **"Are there cost spikes vs. the baseline?"** — Anomaly detection for FinOps
- **"What is my cost per GPU-hour?"** — Efficiency KPI (cost ÷ utilization)
- **"How do token costs compare to compute costs?"** — AI workload cost breakdown

### 4. Incident Analytics
- **"What is my Mean Time to Resolve (MTTR)?"** — Operational maturity signal
- **"How many open vs. resolved incidents by severity?"** — Current risk posture
- **"Are incidents correlated with recent changes?"** — Change-failure rate proxy

### 5. Operational Composite KPIs
- **"What is my overall infrastructure health score?"** — Weighted composite (GPU + net + cost + incidents)
- **"What is the change-failure correlation rate?"** — Incidents within 24h of a change event

## Dashboard Layout (Single Page)

| Section | Chart Type | Data Source |
|---|---|---|
| Header + disclaimer | — | Static |
| GPU Utilization by Cluster/Node | Stacked bar + line | `telemetry_gpu` |
| GPU Anomaly Timeline | Scatter/line with markers | `telemetry_gpu` aggregates |
| Network Latency by Site | Grouped bar (P50/P95/P99) | `telemetry_net` |
| Packet Loss & Throughput | Dual-axis line | `telemetry_net` |
| Cost by Cluster (24h) | Horizontal bar | `telemetry_cost` |
| Cost Trend Over Time | Line chart with anomaly band | `telemetry_cost` daily |
| Incident Summary | Doughnut (severity) + table | `incidents` |
| Health Score Card | Gauge / big number tiles | Composite |

## File Changes

| File | Action | Description |
|---|---|---|
| `scripts/export_dashboard_data.py` | Create | Python script to query telemetry.db and export JSON |
| `docs/pages/assets/dashboard-data.json` | Create | Pre-exported KPI data for the dashboard |
| `docs/pages/dashboard.html` | Create | Interactive KPI dashboard page with Chart.js |
| `docs/pages/dashboard.css` | Create | Dashboard-specific styles (extends main theme) |
| `docs/index.html` | Edit | Add "Dashboard" nav link |
| `docs/style.css` | Edit | Minor shared style additions if needed |

## Tech Choices

- **Chart.js 4.x** via CDN — zero build step, excellent dark-theme support, responsive
- **No framework** — vanilla HTML/JS, consistent with existing brochure site
- **Static JSON** — data baked at build time, works on GitHub Pages without a backend
- **Dark theme** — reuses CSS variables from existing `style.css`

## Todos

1. `export-script` — Create `scripts/export_dashboard_data.py` to extract KPI data from telemetry.db → JSON
2. `dashboard-data` — Run the export script to generate `docs/pages/assets/dashboard-data.json`
3. `dashboard-html` — Create `docs/pages/dashboard.html` with Chart.js visualizations and KPI question annotations
4. `dashboard-css` — Create `docs/pages/dashboard.css` for dashboard-specific styling
5. `nav-link` — Add "Dashboard" link to `docs/index.html` navigation
6. `verify` — Validate the dashboard loads correctly and charts render with the exported data

## Notes

- All data is synthetic — the dashboard must include the standard disclaimer
- The export script reuses the existing `data/seed_telemetry.py` module (no new DB schema)
- Chart.js chosen over Plotly for smaller bundle size and simpler CDN usage
- The dashboard is purely read-only visualization — no interaction with the agent
