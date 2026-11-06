"""
run_etl.py
==========
Purpose : Rebuild the ENTIRE database from the raw files with one command,
          then prove it is correct. In order, it:

            1. builds a new, empty database            (create_database.py)
            2. loads the dimension tables              (load_dimensions.py)
            3. loads Nissan's result tables            (load_nissan_facts.py)
            4. loads the market data tables            (load_market_data.py)
            5. checks the dimensions                   (check_dimensions.py)
            6. checks Nissan's result tables           (check_nissan_facts.py)
            7. checks the market data tables           (check_market_data.py)

          It stops at the first problem and shows that step's full output.
          Because the database is deleted and rebuilt every time, running it
          again always gives the same clean result.

Usage   : python src/run_etl.py   (from the project root)

Exit code: 0 if every step passed, 1 otherwise.
"""

import contextlib
import io
import sys
import time

import check_dimensions
import check_market_data
import check_nissan_facts
import create_database
import load_dimensions
import load_market_data
import load_nissan_facts
from db_utils import connect, count_rows

STEPS = [
    ("Build the empty database", create_database),
    ("Load the dimension tables", load_dimensions),
    ("Load Nissan's result tables", load_nissan_facts),
    ("Load the market data tables", load_market_data),
    ("Check the dimension tables", check_dimensions),
    ("Check Nissan's result tables", check_nissan_facts),
    ("Check the market data tables", check_market_data),
]

ALL_TABLES = [
    "dim_source", "dim_period", "dim_geography", "dim_company", "dim_date",
    "fact_group_financials", "fact_regional_results", "fact_volumes",
    "fact_restructuring_targets", "fact_stock_prices", "fact_usd_jpy", "fact_ev_sales",
]


def run_step(module) -> tuple:
    """Run one script's main() while capturing what it prints."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = module.main()
    return code, buffer.getvalue()


def checks_line(output: str) -> str:
    """Pull the 'Checks passed: N | failed: M' line out of a check script's output."""
    for line in output.splitlines():
        if line.startswith("Checks passed"):
            return line
    return ""


def main() -> int:
    started = time.perf_counter()
    print("=" * 66)
    print("NISSAN TURNAROUND 2027 - FULL ETL PIPELINE")
    print("=" * 66)

    total_checks = 0
    for number, (label, module) in enumerate(STEPS, start=1):
        code, output = run_step(module)
        if code != 0:
            print(f"[FAIL] {number}. {label}\n")
            print(output)
            print("=" * 66)
            print(f"PIPELINE STOPPED at step {number}. Fix the problem above, then rerun.")
            return 1
        summary = checks_line(output)
        if summary:
            total_checks += int(summary.split(":")[1].split("|")[0])
        print(f"[PASS] {number}. {label:<32}{summary}".rstrip())

    connection = connect()
    print("\nWhat is now inside the database:")
    for table in ALL_TABLES:
        print(f"  {table:<30}{count_rows(connection, table):>9,} rows")
    connection.close()

    seconds = time.perf_counter() - started
    print("\n" + "=" * 66)
    print(f"RESULT: PIPELINE COMPLETE. {total_checks} checks passed in {seconds:.1f} seconds.")
    print("The database was rebuilt from the raw files and verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())