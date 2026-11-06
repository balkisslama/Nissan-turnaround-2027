"""
load_nissan_facts.py
====================
Purpose : Fill the four FACT tables that hold Nissan's own numbers, using
          the raw CSV files in data/raw/:

            nissan_group_financials.csv      -> fact_group_financials
            nissan_regional_results.csv      -> fact_regional_results
            nissan_volumes.csv               -> fact_volumes
            nissan_restructuring_targets.csv -> fact_restructuring_targets

          Transformations done on the way in:
            * blank cells become NULL ("not published"), never 0
            * text numbers become real numbers
            * place names (Japan, Europe...) become the numeric ids
              stored in dim_geography

Usage   : python src/load_nissan_facts.py   (after load_dimensions.py)

Exit code: 0 if loaded, 1 otherwise.
"""

import csv
import sqlite3
import sys

from db_utils import RAW_DIR, connect, count_rows

FACT_TABLES = ["fact_group_financials", "fact_regional_results",
               "fact_volumes", "fact_restructuring_targets"]

# The columns of the group financials CSV that contain numbers.
GROUP_NUMBER_COLUMNS = [
    "net_sales_bn", "operating_profit_bn", "ordinary_income_bn", "net_income_bn",
    "total_assets_bn", "net_assets_bn", "equity_ratio_pct",
    "cfo_bn", "cfi_bn", "cff_bn", "cash_end_bn",
    "capex_bn", "depreciation_bn", "rnd_bn", "usd_jpy_avg", "eur_jpy_avg",
]


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------
def read_csv(file_name: str) -> list:
    """Read a CSV from data/raw/ and return its lines as a list of dictionaries."""
    with open(RAW_DIR / file_name, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def to_number(text: str):
    """Turn '12.5' into 12.5, and a blank cell into None (which means NULL)."""
    text = text.strip()
    return float(text) if text != "" else None


def geography_ids(connection) -> dict:
    """Build a lookup 'place name -> id number' from the dim_geography table."""
    lookup = {}
    for geo_id, geo_name in connection.execute("SELECT geo_id, geo_name FROM dim_geography"):
        lookup[geo_name] = geo_id
    return lookup


def find_geo_id(lookup: dict, name: str, where: str) -> int:
    """Return the id of a place, or stop with a clear message if it is unknown."""
    if name not in lookup:
        raise ValueError(f"Place '{name}' ({where}) does not exist in dim_geography")
    return lookup[name]


# ----------------------------------------------------------------------
# Building the rows (the "Transform" part)
# ----------------------------------------------------------------------
def build_group_rows() -> list:
    rows = []
    for line in read_csv("nissan_group_financials.csv"):
        row = {"period_id": line["period_id"], "source_ids": line["source_ids"]}
        for column in GROUP_NUMBER_COLUMNS:
            row[column] = to_number(line[column])
        rows.append(row)
    return rows


def build_regional_rows(lookup: dict) -> list:
    rows = []
    for line in read_csv("nissan_regional_results.csv"):
        rows.append({
            "period_id": line["period_id"],
            "geo_id": find_geo_id(lookup, line["region"], "regional results"),
            "net_sales_bn": to_number(line["net_sales_bn"]),
            "operating_profit_bn": to_number(line["operating_profit_bn"]),
            "source_ids": line["source_ids"],
        })
    return rows


def build_volume_rows(lookup: dict) -> list:
    rows = []
    for line in read_csv("nissan_volumes.csv"):
        rows.append({
            "period_id": line["period_id"],
            "metric": line["metric"],
            "geo_id": find_geo_id(lookup, line["market"], "volumes"),
            "units_thousand": int(line["units_thousand"]),
            "note": line["note"] or None,        # an empty note becomes NULL
            "source_ids": line["source_ids"],
        })
    return rows


def build_target_rows() -> list:
    rows = []
    for line in read_csv("nissan_restructuring_targets.csv"):
        rows.append({
            "metric_id": line["metric_id"],
            "description": line["description"],
            "value": to_number(line["value"]),
            "unit": line["unit"],
            "as_of": line["as_of"],
            "source_ids": line["source_ids"],
        })
    return rows


# ----------------------------------------------------------------------
# Loading (the "Load" part)
# ----------------------------------------------------------------------
def load(connection) -> dict:
    """Insert all fact rows in one all-or-nothing transaction."""
    lookup = geography_ids(connection)
    group_rows = build_group_rows()
    regional_rows = build_regional_rows(lookup)
    volume_rows = build_volume_rows(lookup)
    target_rows = build_target_rows()

    with connection:
        connection.executemany(
            """INSERT INTO fact_group_financials (
                   period_id, net_sales_bn, operating_profit_bn, ordinary_income_bn,
                   net_income_bn, total_assets_bn, net_assets_bn, equity_ratio_pct,
                   cfo_bn, cfi_bn, cff_bn, cash_end_bn, capex_bn, depreciation_bn,
                   rnd_bn, usd_jpy_avg, eur_jpy_avg, source_ids)
               VALUES (
                   :period_id, :net_sales_bn, :operating_profit_bn, :ordinary_income_bn,
                   :net_income_bn, :total_assets_bn, :net_assets_bn, :equity_ratio_pct,
                   :cfo_bn, :cfi_bn, :cff_bn, :cash_end_bn, :capex_bn, :depreciation_bn,
                   :rnd_bn, :usd_jpy_avg, :eur_jpy_avg, :source_ids)""",
            group_rows)
        connection.executemany(
            """INSERT INTO fact_regional_results
                   (period_id, geo_id, net_sales_bn, operating_profit_bn, source_ids)
               VALUES (:period_id, :geo_id, :net_sales_bn, :operating_profit_bn, :source_ids)""",
            regional_rows)
        connection.executemany(
            """INSERT INTO fact_volumes
                   (period_id, metric, geo_id, units_thousand, note, source_ids)
               VALUES (:period_id, :metric, :geo_id, :units_thousand, :note, :source_ids)""",
            volume_rows)
        connection.executemany(
            """INSERT INTO fact_restructuring_targets
                   (metric_id, description, value, unit, as_of, source_ids)
               VALUES (:metric_id, :description, :value, :unit, :as_of, :source_ids)""",
            target_rows)

    return {table: count_rows(connection, table) for table in FACT_TABLES}


def main() -> int:
    print("=" * 60)
    print("NISSAN TURNAROUND 2027 - LOAD NISSAN FACT TABLES")
    print("=" * 60)

    try:
        connection = connect()
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        return 1

    if count_rows(connection, "dim_period") == 0:
        print("[STOP] The dimension tables are empty. Load them first:")
        print("           python src/load_dimensions.py")
        connection.close()
        return 1

    if any(count_rows(connection, table) > 0 for table in FACT_TABLES):
        print("[STOP] The Nissan fact tables already contain data.")
        print("       To start again, run in this order:")
        print("           python src/create_database.py")
        print("           python src/load_dimensions.py")
        print("           python src/load_nissan_facts.py")
        connection.close()
        return 1

    try:
        counts = load(connection)
    except (ValueError, KeyError, sqlite3.Error) as error:
        print(f"[FAIL] {type(error).__name__}: {error}")
        print("       Nothing was loaded (the transaction was undone).")
        connection.close()
        return 1
    connection.close()

    for table, number in counts.items():
        print(f"[PASS] {table:<30} {number:>4} rows loaded")
    print("=" * 60)
    print("RESULT: NISSAN FACTS LOADED. Next: python src/check_nissan_facts.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())