#!/usr/bin/env python3
"""Set up the local SQLite database for Agentic Ops Advisor development.

Usage:
    python scripts/setup_local_db.py [--db PATH] [--days N] [--force]

What it does:
    1. Creates the ``data/`` directory if it doesn't exist.
    2. Creates all four telemetry tables (idempotent).
    3. Runs ``data/seed_telemetry.py`` to populate 30 days of synthetic data.
    4. Verifies data integrity (table existence + minimum row counts).

All data is synthetic — no real infrastructure data is used.
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys

# ---------------------------------------------------------------------------
# Ensure repo root is on sys.path so sibling packages are importable
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from data.seed_telemetry import DEFAULT_DB_PATH, create_schema, seed  # noqa: E402

# ---------------------------------------------------------------------------
# Minimum expected row counts (used for verification)
# ---------------------------------------------------------------------------
MIN_ROW_COUNTS: dict[str, int] = {
    "telemetry_gpu": 500,
    "telemetry_net": 500,
    "telemetry_cost": 10,  # daily table: 2 clusters × ≥5 days
    "incidents": 3,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_header(text: str) -> None:
    width = 60
    print()
    print("=" * width)
    print(f"  {text}")
    print("=" * width)


def _print_step(step: str, detail: str = "") -> None:
    suffix = f"  ({detail})" if detail else ""
    print(f"  ▸ {step}{suffix}")


def _print_ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _print_warn(msg: str) -> None:
    print(f"  ⚠ {msg}", file=sys.stderr)


def _print_err(msg: str) -> None:
    print(f"  ✗ {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Core steps
# ---------------------------------------------------------------------------

def step_create_dirs(db_path: str) -> None:
    """Create parent directory for the database file if needed."""
    data_dir = os.path.dirname(db_path)
    os.makedirs(data_dir, exist_ok=True)
    _print_ok(f"Data directory ready: {data_dir}")


def step_create_schema(conn: sqlite3.Connection) -> None:
    """Create all telemetry tables (no-op if they already exist)."""
    create_schema(conn)
    _print_ok("Schema created / verified (4 tables)")


def step_seed(conn: sqlite3.Connection, days: int) -> dict[str, int]:
    """Insert synthetic rows into all tables and return counts."""
    counts = seed(conn, days=days)
    for table, n in counts.items():
        _print_ok(f"{table}: {n:,} rows inserted")
    return counts


def step_verify(conn: sqlite3.Connection) -> bool:
    """Verify table existence and minimum row counts. Returns True if all pass."""
    all_ok = True
    for table, min_rows in MIN_ROW_COUNTS.items():
        try:
            cur = conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            actual = cur.fetchone()[0]
            if actual >= min_rows:
                _print_ok(f"{table}: {actual:,} rows (≥ {min_rows} required)")
            else:
                _print_warn(f"{table}: only {actual:,} rows (< {min_rows} expected)")
                all_ok = False
        except sqlite3.OperationalError as exc:
            _print_err(f"{table}: {exc}")
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create and seed the local SQLite telemetry database.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python scripts/setup_local_db.py --days 30",
    )
    parser.add_argument(
        "--db",
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database file (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days of synthetic history to generate (default: 30)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete and recreate the database even if it already exists",
    )
    args = parser.parse_args(argv)

    _print_header("Agentic Ops Advisor — Local DB Setup")
    print(f"  Database : {args.db}")
    print(f"  History  : {args.days} days of synthetic data")

    # Handle --force: delete existing DB
    if args.force and os.path.exists(args.db):
        _print_step("Removing existing database (--force)")
        os.remove(args.db)
        _print_ok("Existing database removed")

    # Skip seeding if DB already has data (unless --force was used)
    if os.path.exists(args.db):
        conn_check = sqlite3.connect(args.db)
        try:
            tables = conn_check.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            existing_tables = {row[0] for row in tables}
        finally:
            conn_check.close()

        if "telemetry_gpu" in existing_tables:
            _print_header("Verification (existing database)")
            _print_step("Database already exists — skipping seed (use --force to re-seed)")
            conn = sqlite3.connect(args.db)
            try:
                ok = step_verify(conn)
            finally:
                conn.close()
            if ok:
                _print_header("Setup complete ✓")
                print("\n  Run `python scripts/run_local.py` to start the agent.\n")
                return 0
            else:
                _print_warn("Verification failed. Run with --force to re-seed.")
                return 1

    # Fresh setup
    _print_header("Step 1 — Create directories")
    step_create_dirs(args.db)

    _print_header("Step 2 — Create schema")
    conn = sqlite3.connect(args.db)
    try:
        step_create_schema(conn)

        _print_header(f"Step 3 — Seed {args.days} days of synthetic data")
        step_seed(conn, args.days)

        _print_header("Step 4 — Verify data integrity")
        ok = step_verify(conn)
    finally:
        conn.close()

    if ok:
        _print_header("Setup complete ✓")
        print("\n  Run `python scripts/run_local.py` to start the agent.\n")
        return 0
    else:
        _print_err("Setup finished with warnings — see above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
