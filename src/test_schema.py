"""
test_schema.py
==============
Purpose : Prove that the database design PROTECTS the data. The tests build
          a throwaway in-memory copy of the schema, then try to insert both
          good rows (must be accepted) and bad rows (must be rejected).

          If a "bad row" ever gets accepted, the constraint that should have
          stopped it is missing or wrong.

          The real database file (data/processed/nissan.db) is never touched.

Usage   : python src/test_schema.py   (from the project root)

Exit code: 0 if every test passes, 1 otherwise.
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILE = PROJECT_ROOT / "sql" / "01_create_schema.sql"

results = {"passed": 0, "failed": 0}


def make_database() -> sqlite3.Connection:
    """Create an in-memory database from the schema file."""
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_FILE.read_text(encoding="utf-8"))
    return connection


def record(ok: bool, message: str) -> None:
    """Print one PASS/FAIL line and update the counters."""
    print(f"[{'PASS' if ok else 'FAIL'}] {message}")
    results["passed" if ok else "failed"] += 1


def expect_ok(db: sqlite3.Connection, message: str, sql: str) -> None:
    """The statement must be ACCEPTED by the database."""
    try:
        db.execute(sql)
        record(True, f"accepted: {message}")
    except sqlite3.Error as error:
        record(False, f"accepted: {message} -> unexpected error: {error}")


def expect_rejected(db: sqlite3.Connection, message: str, sql: str) -> None:
    """The statement must be REJECTED with an integrity error."""
    try:
        db.execute(sql)
        record(False, f"rejected: {message} -> but the database ACCEPTED it")
    except sqlite3.IntegrityError:
        record(True, f"rejected: {message}")


def main() -> int:
    print("=" * 70)
    print("NISSAN TURNAROUND 2027 - SCHEMA TESTS (in-memory, real DB untouched)")
    print("=" * 70)

    db = make_database()
    on = db.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    record(on, "foreign key enforcement is ON")

    # --- dim_period -----------------------------------------------------
    print("\n--- dimension rules ---")
    expect_ok(db, "valid actual period FY2025",
              "INSERT INTO dim_period VALUES ('FY2025','FY2025','FY',2025,"
              "'2025-04-01','2026-03-31',0,5)")
    expect_ok(db, "valid forecast period FY2026F",
              "INSERT INTO dim_period VALUES ('FY2026F','FY2026 forecast','FY_FORECAST',"
              "2026,'2026-04-01','2027-03-31',1,6)")
    expect_rejected(db, "duplicate period_id",
                    "INSERT INTO dim_period VALUES ('FY2025','dup','FY',2025,"
                    "'2025-04-01','2026-03-31',0,5)")
    expect_rejected(db, "unknown period_type 'H1'",
                    "INSERT INTO dim_period VALUES ('X1','x','H1',2025,"
                    "'2025-04-01','2025-09-30',0,9)")
    expect_rejected(db, "period ending before it starts",
                    "INSERT INTO dim_period VALUES ('X2','x','FY',2025,"
                    "'2026-03-31','2025-04-01',0,9)")
    expect_rejected(db, "forecast period flagged as actual (is_forecast = 0)",
                    "INSERT INTO dim_period VALUES ('X3','x','FY_FORECAST',2026,"
                    "'2026-04-01','2027-03-31',0,9)")

    # --- dim_geography --------------------------------------------------
    expect_ok(db, "geography 'North America' (region)",
              "INSERT INTO dim_geography VALUES (3,'North America','region',NULL,NULL)")
    expect_ok(db, "geography 'USA' as child of North America",
              "INSERT INTO dim_geography VALUES (8,'USA','country',3,NULL)")
    expect_rejected(db, "geography with a parent that does not exist",
                    "INSERT INTO dim_geography VALUES (99,'Atlantis','country',777,NULL)")
    expect_rejected(db, "duplicate geography name",
                    "INSERT INTO dim_geography VALUES (50,'USA','country',3,NULL)")
    expect_rejected(db, "invalid geo_level 'planet'",
                    "INSERT INTO dim_geography VALUES (51,'Mars','planet',NULL,NULL)")

    # --- fact_group_financials -----------------------------------------
    print("\n--- fact rules ---")
    expect_ok(db, "forecast row with NULL ordinary income and balance sheet",
              "INSERT INTO fact_group_financials (period_id, net_sales_bn, operating_profit_bn,"
              " net_income_bn, source_ids) VALUES ('FY2026F',13000.0,200.0,20.0,'SUM-Q1FY2026')")
    expect_rejected(db, "financials for a period that does not exist (broken link)",
                    "INSERT INTO fact_group_financials (period_id, net_sales_bn, operating_profit_bn,"
                    " net_income_bn, source_ids) VALUES ('FY1999',1.0,1.0,1.0,'x')")
    expect_rejected(db, "negative net sales",
                    "INSERT INTO fact_group_financials (period_id, net_sales_bn, operating_profit_bn,"
                    " net_income_bn, source_ids) VALUES ('FY2025',-5.0,1.0,1.0,'x')")
    expect_rejected(db, "equity ratio of 150 percent",
                    "INSERT INTO fact_group_financials (period_id, net_sales_bn, operating_profit_bn,"
                    " net_income_bn, equity_ratio_pct, source_ids) VALUES ('FY2025',1.0,1.0,1.0,150,'x')")
    expect_rejected(db, "financials without a source",
                    "INSERT INTO fact_group_financials (period_id, net_sales_bn, operating_profit_bn,"
                    " net_income_bn) VALUES ('FY2025',1.0,1.0,1.0)")

    # --- fact_regional_results -----------------------------------------
    expect_ok(db, "regional result (FY2025, North America)",
              "INSERT INTO fact_regional_results VALUES ('FY2025',3,6958.3,68.7,'SUM-Q1FY2026')")
    expect_rejected(db, "same period and region twice (duplicate grain)",
                    "INSERT INTO fact_regional_results VALUES ('FY2025',3,1.0,1.0,'x')")
    expect_rejected(db, "regional result for an unknown geography",
                    "INSERT INTO fact_regional_results VALUES ('FY2025',404,1.0,1.0,'x')")

    # --- fact_volumes ---------------------------------------------------
    expect_ok(db, "retail volume (FY2025, North America)",
              "INSERT INTO fact_volumes VALUES ('FY2025','retail_sales',3,1291,NULL,'SUM-Q1FY2026')")
    expect_rejected(db, "unknown volume metric 'inventory'",
                    "INSERT INTO fact_volumes VALUES ('FY2025','inventory',3,10,NULL,'x')")
    expect_rejected(db, "negative vehicle volume",
                    "INSERT INTO fact_volumes VALUES ('FY2025','production',3,-1,NULL,'x')")

    # --- stock prices & fx ---------------------------------------------
    expect_ok(db, "company Nissan",
              "INSERT INTO dim_company VALUES (1,'7201.T','Nissan',1)")
    expect_ok(db, "calendar day 2025-06-02",
              "INSERT INTO dim_date VALUES ('2025-06-02',2025,2,6,'June',1,0,2025,1)")
    expect_ok(db, "share price row",
              "INSERT INTO fact_stock_prices VALUES ('2025-06-02',1,350.5,1000000)")
    expect_rejected(db, "price for a company that does not exist",
                    "INSERT INTO fact_stock_prices VALUES ('2025-06-02',77,350.5,10)")
    expect_rejected(db, "price on a day missing from the calendar",
                    "INSERT INTO fact_stock_prices VALUES ('2025-06-03',1,350.5,10)")
    expect_rejected(db, "share price of zero",
                    "INSERT INTO fact_stock_prices VALUES ('2025-06-02',1,0,10)")
    expect_rejected(db, "same company and day twice",
                    "INSERT INTO fact_stock_prices VALUES ('2025-06-02',1,351.0,5)")
    expect_ok(db, "USD/JPY rate",
              "INSERT INTO fact_usd_jpy VALUES ('2025-06-02',143.2)")
    expect_rejected(db, "negative exchange rate",
                    "INSERT INTO fact_usd_jpy VALUES ('2025-06-02',-1)")

    # --- ev sales -------------------------------------------------------
    expect_ok(db, "EV sales for a country",
              "INSERT INTO fact_ev_sales VALUES ('China','CHN',2024,11300000)")
    expect_ok(db, "EV sales for an aggregate with no country code ('World')",
              "INSERT INTO fact_ev_sales VALUES ('World',NULL,2024,17000000)")
    expect_rejected(db, "same country and year twice",
                    "INSERT INTO fact_ev_sales VALUES ('China','CHN',2024,1)")

    # --- referential protection when DELETING ---------------------------
    print("\n--- protection when deleting ---")
    expect_rejected(db, "deleting a period that facts still use",
                    "DELETE FROM dim_period WHERE period_id = 'FY2025'")
    expect_rejected(db, "deleting a geography that facts still use",
                    "DELETE FROM dim_geography WHERE geo_id = 3")

    print("\n" + "=" * 70)
    print(f"Tests passed: {results['passed']} | failed: {results['failed']}")
    if results["failed"]:
        print("RESULT: FAILED. A rule the schema should enforce is missing.")
        return 1
    print("RESULT: ALL TESTS PASSED. The schema rejects bad data as designed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())