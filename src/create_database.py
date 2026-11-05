"""
create_database.py
==================
Purpose : Build the empty SQLite database for the project by running
          sql/01_create_schema.sql, then verify that every expected table
          exists with its keys and constraints.

          The database file is data/processed/nissan.db. It is DELETED and
          rebuilt on every run, so the script is safe to run repeatedly.
          (Loading data into it is Step 4.)

Usage   : python src/create_database.py   (from the project root)

Exit code: 0 if the database was built and verified, 1 otherwise.
"""

import sqlite3
import sys
from pathlib import Path

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "sql" / "01_create_schema.sql"
DB_PATH = PROJECT_ROOT / "data" / "processed" / "nissan.db"

EXPECTED_TABLES = [
    "dim_company", "dim_date", "dim_geography", "dim_period", "dim_source",
    "fact_ev_sales", "fact_group_financials", "fact_regional_results",
    "fact_restructuring_targets", "fact_stock_prices", "fact_usd_jpy",
    "fact_volumes",
]


def build_database() -> sqlite3.Connection:
    """Delete any old database file and create a fresh one from the SQL file."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    connection = sqlite3.connect(DB_PATH)
    connection.execute("PRAGMA foreign_keys = ON")      # off by default in SQLite!
    connection.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    return connection


def verify(connection: sqlite3.Connection) -> bool:
    """Print a summary of the database and check it against expectations."""
    all_ok = True

    tables = [row[0] for row in connection.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]

    print(f"{'table':<30}{'columns':>8}{'foreign keys':>14}{'primary key':>14}")
    print("-" * 66)
    for table in tables:
        info = connection.execute(f"PRAGMA table_info({table})").fetchall()
        foreign_keys = connection.execute(f"PRAGMA foreign_key_list({table})").fetchall()
        primary_key = [column[1] for column in info if column[5] > 0]
        print(f"{table:<30}{len(info):>8}{len(foreign_keys):>14}"
              f"{len(primary_key):>11} col")

    print("-" * 66)
    missing = sorted(set(EXPECTED_TABLES) - set(tables))
    unexpected = sorted(set(tables) - set(EXPECTED_TABLES))
    status = "PASS" if not missing and not unexpected else "FAIL"
    print(f"[{status}] {len(tables)} tables found "
          f"(expected {len(EXPECTED_TABLES)})")
    if missing or unexpected:
        print(f"       missing: {missing} | unexpected: {unexpected}")
        all_ok = False

    foreign_keys_on = connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    print(f"[{'PASS' if foreign_keys_on else 'FAIL'}] foreign key enforcement is ON")
    all_ok &= foreign_keys_on

    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    print(f"[{'PASS' if integrity == 'ok' else 'FAIL'}] SQLite integrity check: {integrity}")
    all_ok &= integrity == "ok"

    return all_ok


def main() -> int:
    print("=" * 66)
    print("NISSAN TURNAROUND 2027 - BUILD DATABASE")
    print(f"Schema file : {SCHEMA_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Database    : {DB_PATH.relative_to(PROJECT_ROOT)}")
    print("=" * 66)

    if not SCHEMA_FILE.exists():
        print("[FAIL] schema file not found. Did you save sql/01_create_schema.sql?")
        return 1

    connection = build_database()
    ok = verify(connection)
    connection.close()

    print("=" * 66)
    if ok:
        print("RESULT: DATABASE BUILT AND VERIFIED. Ready for Step 4 (loading data).")
        return 0
    print("RESULT: FAILED. Read the [FAIL] lines above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())