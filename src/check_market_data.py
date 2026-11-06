"""
check_market_data.py
====================
Purpose : Prove that the three market tables are correct.

          1. Independent re-count  - the raw files are cleaned a SECOND time,
                                     with a different tool (pandas), and the
                                     result must match the database exactly
          2. Rules                 - no holiday rows left, no broken links,
                                     every company present, sensible rates
          3. Information           - things worth knowing (not pass/fail)
          4. First look            - first real questions about share prices,
                                     the yen and electric cars

Usage   : python src/check_market_data.py   (after load_market_data.py)

Exit code: 0 if every check passes, 1 otherwise.
"""

import sys

import pandas as pd

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
# The raw files, cleaned independently with pandas
# ----------------------------------------------------------------------
def expected_stock() -> pd.DataFrame:
    raw = pd.read_csv(RAW_DIR / "stock_prices_daily.csv")
    raw["date"] = raw["date"].astype(str).str[:10]
    raw = raw[(raw["close_jpy"] > 0) & (raw["volume"] > 0)]
    return raw.drop_duplicates(subset=["date", "ticker"], keep="last")


def expected_fx() -> pd.DataFrame:
    raw = pd.read_csv(RAW_DIR / "usd_jpy_daily.csv")
    raw["date"] = raw["date"].astype(str).str[:10]
    raw = raw[raw["usd_jpy"] > 0]
    return raw.drop_duplicates(subset=["date"], keep="last")


def expected_ev() -> pd.DataFrame:
    raw = pd.read_csv(RAW_DIR / "ev_sales_by_country.csv")
    raw = raw[raw["electric_car_sales"] >= 0].copy()
    raw["country_code"] = raw["country_code"].fillna("")
    return raw.drop_duplicates(subset=["country", "year"], keep="last")


def compare(expected: pd.DataFrame, stored: pd.DataFrame, keys: list, label: str) -> None:
    """Match expected and stored rows on their keys and compare every value."""
    merged = expected.merge(stored, on=keys, how="outer", indicator=True,
                            suffixes=("_csv", "_db"))
    only_csv = int((merged["_merge"] == "left_only").sum())
    only_db = int((merged["_merge"] == "right_only").sum())
    both = merged[merged["_merge"] == "both"]

    value_columns = [c[:-4] for c in merged.columns if c.endswith("_csv")]
    wrong = 0
    for column in value_columns:
        left, right = both[f"{column}_csv"], both[f"{column}_db"]
        if pd.api.types.is_numeric_dtype(left):
            wrong += int(((left - right).abs() > 1e-9).sum())
        else:
            wrong += int((left.astype(str) != right.astype(str)).sum())

    check(only_csv == 0 and only_db == 0 and wrong == 0,
          f"{label}: {len(both):,} rows matched | missing in database: {only_csv} | "
          f"extra in database: {only_db} | different values: {wrong}")


# ----------------------------------------------------------------------
# 1. Independent re-count
# ----------------------------------------------------------------------
def check_against_raw(connection) -> None:
    print("\n--- 1. DATABASE VERSUS RAW FILES (cleaned a second time, independently) ---")

    stored = pd.read_sql(
        "SELECT s.date_key AS date, c.ticker AS ticker, s.close_jpy, s.volume "
        "FROM fact_stock_prices AS s JOIN dim_company AS c ON c.company_id = s.company_id",
        connection)
    compare(expected_stock()[["date", "ticker", "close_jpy", "volume"]], stored,
            ["date", "ticker"], "fact_stock_prices")

    stored = pd.read_sql("SELECT date_key AS date, usd_jpy FROM fact_usd_jpy", connection)
    compare(expected_fx()[["date", "usd_jpy"]], stored, ["date"], "fact_usd_jpy")

    stored = pd.read_sql(
        "SELECT country, COALESCE(country_code, '') AS country_code, year, "
        "electric_car_sales FROM fact_ev_sales", connection)
    compare(expected_ev()[["country", "country_code", "year", "electric_car_sales"]],
            stored, ["country", "year"], "fact_ev_sales")


# ----------------------------------------------------------------------
# 2. Rules
# ----------------------------------------------------------------------
def check_rules(connection) -> None:
    print("\n--- 2. RULES (asked in SQL) ---")

    zero = ask(connection, "SELECT COUNT(*) FROM fact_stock_prices WHERE volume = 0")[0][0]
    check(zero == 0, f"no holiday (zero-volume) rows left in the share prices ({zero} found)")

    per_company = ask(connection,
                      "SELECT c.company_name, COUNT(s.date_key) "
                      "FROM dim_company AS c "
                      "LEFT JOIN fact_stock_prices AS s ON s.company_id = c.company_id "
                      "GROUP BY c.company_id ORDER BY c.company_id")
    check(len(per_company) == 5 and all(n > 0 for _, n in per_company),
          "all 5 companies have share prices: "
          + ", ".join(f"{name} {n:,}" for name, n in per_company))

    low, high = ask(connection, "SELECT MIN(usd_jpy), MAX(usd_jpy) FROM fact_usd_jpy")[0]
    check(50 < low and high < 300,
          f"USD/JPY stays between 50 and 300 (lowest {low:.2f}, highest {high:.2f})")

    broken = ask(connection, "PRAGMA foreign_key_check")
    check(broken == [], f"no broken links between tables ({len(broken)} found)")

    ev_rows = ask(connection, "SELECT COUNT(*) FROM fact_ev_sales")[0][0]
    check(ev_rows > 0, f"electric car sales table is not empty ({ev_rows:,} rows)")


# ----------------------------------------------------------------------
# 3. Information (not pass/fail)
# ----------------------------------------------------------------------
def show_information(connection) -> None:
    print("\n--- 3. INFORMATION (worth knowing, not pass/fail) ---")

    weekend = ask(connection,
                  "SELECT COUNT(*) FROM fact_stock_prices AS s "
                  "JOIN dim_date AS d ON d.date_key = s.date_key WHERE d.is_weekend = 1")[0][0]
    print(f"[INFO] share price rows dated on a weekend: {weekend}")

    both = ask(connection,
               "SELECT COUNT(DISTINCT s.date_key) FROM fact_stock_prices AS s "
               "JOIN fact_usd_jpy AS f ON f.date_key = s.date_key")[0][0]
    print(f"[INFO] days that have both a share price and a USD/JPY rate: {both:,}")

    for name, first, last in ask(connection,
                                 "SELECT c.company_name, MIN(s.date_key), MAX(s.date_key) "
                                 "FROM fact_stock_prices AS s "
                                 "JOIN dim_company AS c ON c.company_id = s.company_id "
                                 "GROUP BY c.company_id ORDER BY c.company_id"):
        print(f"[INFO] {name:<8} share prices from {first} to {last}")


# ----------------------------------------------------------------------
# 4. First look
# ----------------------------------------------------------------------
def show_first_look(connection) -> None:
    print("\n--- 4. FIRST LOOK (first real questions about the market) ---")

    print("\nQuestion 3: how strong was the dollar against the yen, per Nissan fiscal year?")
    print("(a higher number = a weaker yen; the latest fiscal year is only partly over)")
    print(f"{'fiscal year':<13}{'average yen per USD':>21}{'days':>7}")
    for fiscal_year, average, days in ask(
            connection,
            "SELECT d.nissan_fiscal_year, ROUND(AVG(f.usd_jpy), 1), COUNT(*) "
            "FROM fact_usd_jpy AS f JOIN dim_date AS d ON d.date_key = f.date_key "
            "GROUP BY d.nissan_fiscal_year ORDER BY d.nissan_fiscal_year"):
        print(f"FY{fiscal_year:<11}{average:>21.1f}{days:>7}")

    print("\nQuestion 4: how did each share price change from its first to its last day?")
    print(f"{'company':<10}{'first close':>13}{'last close':>12}{'change':>10}")
    for name, first_close, last_close in ask(
            connection,
            "SELECT c.company_name, "
            "(SELECT s.close_jpy FROM fact_stock_prices AS s "
            "  WHERE s.company_id = c.company_id ORDER BY s.date_key ASC LIMIT 1), "
            "(SELECT s.close_jpy FROM fact_stock_prices AS s "
            "  WHERE s.company_id = c.company_id ORDER BY s.date_key DESC LIMIT 1) "
            "FROM dim_company AS c ORDER BY c.company_id"):
        change = (last_close / first_close - 1) * 100
        print(f"{name:<10}{first_close:>13,.1f}{last_close:>12,.1f}{change:>9.0f}%")

    latest = ask(connection, "SELECT MAX(year) FROM fact_ev_sales")[0][0]
    print(f"\nQuestion 5: electric car sales in {latest} (the latest year in the data)")
    print(f"{'country':<18}{'electric cars sold':>20}")
    for country, sales in ask(
            connection,
            "SELECT country, electric_car_sales FROM fact_ev_sales "
            "WHERE year = ? AND country IN "
            "('China', 'United States', 'Germany', 'Japan', 'France') "
            "ORDER BY electric_car_sales DESC", (latest,)):
        print(f"{country:<18}{sales:>20,.0f}")


def main() -> int:
    print("=" * 66)
    print("NISSAN TURNAROUND 2027 - CHECK MARKET DATA TABLES")
    print("=" * 66)

    try:
        connection = connect()
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        return 1

    try:
        check_against_raw(connection)
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        connection.close()
        return 1
    check_rules(connection)
    show_information(connection)
    show_first_look(connection)
    connection.close()

    print("\n" + "=" * 66)
    print(f"Checks passed: {results['passed']} | failed: {results['failed']}")
    if results["failed"]:
        print("RESULT: FAILED. Read the [FAIL] lines above.")
        return 1
    print("RESULT: ALL CHECKS PASSED. Market data matches the raw files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())