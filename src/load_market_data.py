"""
load_market_data.py
===================
Purpose : Fill the three MARKET fact tables from the files that
          download_market_data.py saved in data/raw/:

            stock_prices_daily.csv   -> fact_stock_prices
            usd_jpy_daily.csv        -> fact_usd_jpy
            ev_sales_by_country.csv  -> fact_ev_sales

          CLEANING RULES (every decision is counted and printed):
            1. Share prices with volume 0 are dropped. They are days when the
               Tokyo exchange was closed (holidays): Yahoo repeats the previous
               price with nothing traded, so they are not real prices.
            2. Rows with a missing or non-positive price / rate / sales figure
               are dropped.
            3. If the same key appears twice (same company and day, same day,
               same country and year), the LAST one is kept.
            4. Dates are cut to 'YYYY-MM-DD' (any time of day is removed).
            5. Company tickers are translated into the ids in dim_company.

          The raw files themselves are never modified.

Usage   : python src/load_market_data.py   (after load_dimensions.py)

Exit code: 0 if loaded, 1 otherwise.
"""

import csv
import sqlite3
import sys

from db_utils import RAW_DIR, connect, count_rows

MARKET_TABLES = ["fact_stock_prices", "fact_usd_jpy", "fact_ev_sales"]


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------
def read_csv(file_name: str) -> list:
    """Read a CSV from data/raw/ as a list of dictionaries."""
    path = RAW_DIR / file_name
    if not path.exists():
        raise FileNotFoundError(
            f"{file_name} not found in data/raw. "
            "Download it first with: python src/download_market_data.py")
    with open(path, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def to_number(text: str):
    """Turn '12.5' into 12.5, and a blank cell into None."""
    text = (text or "").strip()
    return float(text) if text != "" else None


def to_whole_number(text: str):
    """Turn '1200' or '1200.0' into 1200, and a blank cell into None."""
    number = to_number(text)
    return int(number) if number is not None else None


def clean_date(text: str) -> str:
    """Keep only 'YYYY-MM-DD' (removes a time such as ' 00:00:00' if present)."""
    return text.strip()[:10]


# ----------------------------------------------------------------------
# Cleaning each file (the "Transform" part)
# ----------------------------------------------------------------------
def build_stock_rows(ticker_ids: dict):
    """Return (clean rows, report) for the share price file."""
    kept = {}
    report = {"read": 0, "no_price": 0, "holiday_zero_volume": 0, "duplicates": 0}
    for line in read_csv("stock_prices_daily.csv"):
        report["read"] += 1
        ticker = line["ticker"].strip()
        if ticker not in ticker_ids:
            raise ValueError(f"Ticker '{ticker}' does not exist in dim_company")
        close = to_number(line["close_jpy"])
        volume = to_whole_number(line["volume"])
        if close is None or close <= 0:
            report["no_price"] += 1
            continue
        if volume is None or volume == 0:
            report["holiday_zero_volume"] += 1
            continue
        key = (clean_date(line["date"]), ticker_ids[ticker])
        if key in kept:
            report["duplicates"] += 1
        kept[key] = {"date_key": key[0], "company_id": key[1],
                     "close_jpy": close, "volume": volume}
    return list(kept.values()), report


def build_fx_rows():
    """Return (clean rows, report) for the USD/JPY file."""
    kept = {}
    report = {"read": 0, "no_rate": 0, "duplicates": 0}
    for line in read_csv("usd_jpy_daily.csv"):
        report["read"] += 1
        rate = to_number(line["usd_jpy"])
        if rate is None or rate <= 0:
            report["no_rate"] += 1
            continue
        day = clean_date(line["date"])
        if day in kept:
            report["duplicates"] += 1
        kept[day] = {"date_key": day, "usd_jpy": rate}
    return list(kept.values()), report


def build_ev_rows():
    """Return (clean rows, report) for the electric car sales file."""
    kept = {}
    report = {"read": 0, "no_value": 0, "duplicates": 0}
    for line in read_csv("ev_sales_by_country.csv"):
        report["read"] += 1
        value = to_number(line["electric_car_sales"])
        if value is None or value < 0:
            report["no_value"] += 1
            continue
        country = line["country"].strip()
        year = int(float(line["year"]))
        if (country, year) in kept:
            report["duplicates"] += 1
        kept[(country, year)] = {
            "country": country,
            "country_code": (line["country_code"] or "").strip() or None,
            "year": year,
            "electric_car_sales": value,
        }
    return list(kept.values()), report


# ----------------------------------------------------------------------
# Loading (the "Load" part)
# ----------------------------------------------------------------------
def load(connection):
    """Clean the three files and insert them in one all-or-nothing transaction."""
    ticker_ids = {ticker: company_id for company_id, ticker in connection.execute(
        "SELECT company_id, ticker FROM dim_company")}

    stock_rows, stock_report = build_stock_rows(ticker_ids)
    fx_rows, fx_report = build_fx_rows()
    ev_rows, ev_report = build_ev_rows()

    with connection:
        connection.executemany(
            "INSERT INTO fact_stock_prices (date_key, company_id, close_jpy, volume) "
            "VALUES (:date_key, :company_id, :close_jpy, :volume)", stock_rows)
        connection.executemany(
            "INSERT INTO fact_usd_jpy (date_key, usd_jpy) "
            "VALUES (:date_key, :usd_jpy)", fx_rows)
        connection.executemany(
            "INSERT INTO fact_ev_sales (country, country_code, year, electric_car_sales) "
            "VALUES (:country, :country_code, :year, :electric_car_sales)", ev_rows)

    counts = {table: count_rows(connection, table) for table in MARKET_TABLES}
    reports = {"stock": stock_report, "fx": fx_report, "ev": ev_report}
    return counts, reports


def main() -> int:
    print("=" * 66)
    print("NISSAN TURNAROUND 2027 - LOAD MARKET DATA TABLES")
    print("=" * 66)

    try:
        connection = connect()
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        return 1

    if count_rows(connection, "dim_date") == 0:
        print("[STOP] The dimension tables are empty. Load them first:")
        print("           python src/load_dimensions.py")
        connection.close()
        return 1

    if any(count_rows(connection, table) > 0 for table in MARKET_TABLES):
        print("[STOP] The market data tables already contain data.")
        print("       To start again from scratch, run: python src/run_etl.py")
        connection.close()
        return 1

    try:
        counts, reports = load(connection)
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        connection.close()
        return 1
    except (ValueError, KeyError, sqlite3.Error) as error:
        print(f"[FAIL] {type(error).__name__}: {error}")
        print("       Nothing was loaded (the transaction was undone).")
        connection.close()
        return 1
    connection.close()

    stock, fx, ev = reports["stock"], reports["fx"], reports["ev"]
    print("Cleaning report:")
    print(f"  share prices : {stock['read']:,} lines read | "
          f"{stock['holiday_zero_volume']:,} holiday rows dropped (volume 0) | "
          f"{stock['no_price']} without a price | {stock['duplicates']} duplicates")
    print(f"  USD/JPY      : {fx['read']:,} lines read | "
          f"{fx['no_rate']} without a rate | {fx['duplicates']} duplicates")
    print(f"  EV sales     : {ev['read']:,} lines read | "
          f"{ev['no_value']} without a value | {ev['duplicates']} duplicates")
    print()
    for table, number in counts.items():
        print(f"[PASS] {table:<20} {number:>7,} rows loaded")
    print("=" * 66)
    print("RESULT: MARKET DATA LOADED. Next: python src/check_market_data.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())