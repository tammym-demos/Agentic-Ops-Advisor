# Decision: Dynamic Seed Dates for Synthetic Telemetry

**Date:** 2026-04-07  
**Decided by:** Naomi (Backend Dev)  
**Status:** Implemented  

## Context

The demo is tomorrow and Tammy discovered a critical bug: all telemetry queries return 0 rows.

Root cause: `data/seed_telemetry.py` used hardcoded `BASE_DATE = datetime(2025, 3, 1, ...)`, generating all data with March 2025 timestamps. The aggregate queries in `tools/sql_telemetry.py` use relative time windows like `WHERE ts >= datetime('now', '-1 hour')`. Since today is April 2026, these queries matched 0 rows.

## Decision

Changed `BASE_DATE` from hardcoded to **dynamic**, calculated so that the last day of generated data ends near "now":

```python
BASE_DATE = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=DAYS - 1)
```

This makes:
- Data generation end ~today (last timestamp is very recent)
- Time-windowed queries (`-1 hour`, `-24 hours`) return rows
- Reproducibility preserved via `RANDOM_SEED = 42` (only timestamps change, random values are deterministic)
- Anomaly logic intact (day 18, 22, 25 relative to BASE_DATE)

## Rationale

1. **Demo requirement:** Queries must return data to showcase the agent's diagnostic capabilities.
2. **Local dev stability:** Every `python data/seed_telemetry.py` run produces current data — no manual date edits needed.
3. **Docker builds:** The Dockerfile calls `setup_local_db.py` → `seed_connection()` at build time, ensuring fresh data in every container.
4. **Azure SQL seeding:** Currently disabled (Azure SQL backend not deployed yet), but `seed_data.sql` is generated on every run and gitignored since it's now dynamic.

## Trade-offs

- **Pro:** Demo works without manual intervention. Queries return data. Docker builds always have fresh timestamps.
- **Pro:** Reproducible random values (seed=42) still allow deterministic testing.
- **Con:** `seed_data.sql` (1.2 MB) changes every run — added to `.gitignore` to avoid churn.
- **Con:** Data range drifts over time (30 days ending "today"). For absolute date testing, you'd need to mock `datetime.now()` or parameterize BASE_DATE.

## Implementation

- **File changed:** `data/seed_telemetry.py` (line 27)
- **Gitignore updated:** Added `data/seed_data.sql` with comment
- **Verification:** All 6 critical queries now return rows (gpu_avg_util_1h: 288, gpu_avg_util_24h: 576, net_avg_latency_1h: 72, cost_by_service_24h: 144, open_incidents: 2, recent_incidents_24h: 1)
- **Tests:** All 348 tests pass

## Alternatives Considered

1. **Keep static dates, update queries to use absolute dates:** Would require updating all aggregate query templates in `sql_telemetry.py` and break the demo's "right now" narrative.
2. **Parameterize BASE_DATE via env var:** Overengineering for a demo project. Dynamic default is simpler.
3. **Mock `datetime.now()` in tests:** Viable if we needed frozen time for regression tests, but not needed yet.

## Follow-up

- None required. Fix is complete and verified.
