"""
check_dimensions.py
===================
Purpose : Ask the database questions (in SQL) to prove that the five
          dimension tables were loaded correctly:

            1. Do the tables hold the expected number of rows?
            2. Is the calendar complete, with Nissan's fiscal year correct?
            3. Is the geography family tree (USA -> North America...) right?
            4. Does every source code used in our CSV files exist in dim_source?

Usage   : python src/check_dimensions.py   (after load_dimensions.py)

Exit code: 0 if every check passes, 1 otherwise.
"""

import csv
import sys

from db_utils import RAW_DIR, connect

results = {"passed": 0, "failed": 0} 

def check(ok: bool, message: str) -> None: 
    """Print one PASS/FAIL line and update the counters."""
    print(f"[{'PASS' if ok else 'FAIL'}] {message}")
    results["passed" if ok else "failed"] += 1


def ask(connection, sql: str, parameters: tuple = ()) -> list:
    """Run a SQL question and return the answer rows."""
    return connection.execute(sql, parameters).fetchall()


# ----------------------------------------------------------------------
# 1. Row counts
# ----------------------------------------------------------------------
def check_row_counts(connection) -> None:
    print("\n--- 1. ROW COUNTS ---")
    expected = {
        "dim_source": 10,
        "dim_period": 8,
        "dim_geography": 11,
        "dim_company": 5,
        "dim_date": 3652,      # 2018-01-01 to 2027-12-31 including 2 leap days
    }
    for table, wanted in expected.items():
        found = ask(connection, f"SELECT COUNT(*) FROM {table}")[0][0]
        check(found == wanted, f"{table}: {found} rows (expected {wanted})")


# ----------------------------------------------------------------------
# 2. The calendar
# ----------------------------------------------------------------------
def check_calendar(connection) -> None:
    print("\n--- 2. CALENDAR ---")

    first, last, total = ask(
        connection, "SELECT MIN(date_key), MAX(date_key), COUNT(*) FROM dim_date")[0]
    check(first == "2018-01-01" and last == "2027-12-31",
          f"calendar runs from {first} to {last}")

    # If no day is missing, (last - first + 1) must equal the number of rows.
    span = ask(connection,
               "SELECT CAST(julianday(MAX(date_key)) - julianday(MIN(date_key)) AS INTEGER) + 1 "
               "FROM dim_date")[0][0]
    check(span == total, f"no missing days ({total} rows cover a span of {span} days)")

    # Spot checks: a few days whose fiscal year and quarter we can work out by hand.
    spot_checks = [
        ("2025-04-01", 2025, 1, "first day of FY2025"),
        ("2025-05-10", 2025, 1, "a day in May 2025"),
        ("2025-12-31", 2025, 3, "last day of calendar 2025"),
        ("2026-02-15", 2025, 4, "February 2026 still belongs to FY2025"),
        ("2025-03-31", 2024, 4, "last day of FY2024"),
    ]
    for day, fiscal_year, fiscal_quarter, meaning in spot_checks:
        answer = ask(connection,
                     "SELECT nissan_fiscal_year, nissan_fiscal_quarter "
                     "FROM dim_date WHERE date_key = ?", (day,))[0]
        check(answer == (fiscal_year, fiscal_quarter),
              f"{day} -> FY{answer[0]} Q{answer[1]} ({meaning})")

    # 2 June 2025 was a Monday; 7 June 2025 was a Saturday.
    monday = ask(connection, "SELECT day_of_week, is_weekend FROM dim_date "
                             "WHERE date_key = '2025-06-02'")[0]
    saturday = ask(connection, "SELECT day_of_week, is_weekend FROM dim_date "
                               "WHERE date_key = '2025-06-07'")[0]
    check(monday == (1, 0), "2025-06-02 is a Monday and not a weekend day")
    check(saturday == (6, 1), "2025-06-07 is a Saturday and a weekend day")


# ----------------------------------------------------------------------
# 3. Periods and geography
# ----------------------------------------------------------------------
def check_periods_and_geography(connection) -> None:
    print("\n--- 3. PERIODS AND GEOGRAPHY ---")

    forecasts = ask(connection,
                    "SELECT period_id FROM dim_period WHERE is_forecast = 1")
    check(forecasts == [("FY2026F",)], f"the only forecast period is {forecasts}")

    label = ask(connection, "SELECT period_label FROM dim_period "
                            "WHERE period_id = 'FY2025'")[0][0]
    check(label == "FY2025 (Apr 2025 - Mar 2026)", f"label of FY2025 reads: {label}")

    # Match every place with its parent by joining the table to itself.
    family = ask(connection,
                 "SELECT child.geo_name, parent.geo_name "
                 "FROM dim_geography AS child "
                 "JOIN dim_geography AS parent ON child.parent_geo_id = parent.geo_id "
                 "ORDER BY child.geo_id")
    expected = [("USA", "North America"), ("China", "Asia"), ("Overseas", "Total")]
    check(family == expected, f"family tree is {family}")


# ----------------------------------------------------------------------
# 4. Source codes
# ----------------------------------------------------------------------
def check_source_codes(connection) -> None:
    print("\n--- 4. SOURCE CODES ---")
    known = {row[0] for row in ask(connection, "SELECT source_id FROM dim_source")}

    files = ["nissan_group_financials.csv", "nissan_regional_results.csv",
             "nissan_volumes.csv", "nissan_restructuring_targets.csv"]
    for name in files:
        used = set()
        with open(RAW_DIR / name, newline="", encoding="utf-8") as file:
            for line in csv.DictReader(file):
                used.update(code.strip() for code in line["source_ids"].split(";"))
        unknown = sorted(used - known)
        check(not unknown,
              f"{name}: {len(used)} source codes used, all known"
              if not unknown else f"{name}: unknown codes {unknown}")


def main() -> int:
    print("=" * 66)
    print("NISSAN TURNAROUND 2027 - CHECK DIMENSIONS")
    print("=" * 66)

    try:
        connection = connect()
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        return 1
    check_row_counts(connection)
    check_calendar(connection)
    check_periods_and_geography(connection)
    check_source_codes(connection)
    connection.close()

    print("\n" + "=" * 66)
    print(f"Checks passed: {results['passed']} | failed: {results['failed']}")
    if results["failed"]:
        print("RESULT: FAILED. Read the [FAIL] lines above.")
        return 1
    print("RESULT: ALL CHECKS PASSED. Dimensions are loaded correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())