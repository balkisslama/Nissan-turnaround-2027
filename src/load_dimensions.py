"""
load_dimensions.py
==================
Purpose : Fill the five DIMENSION tables (the "address book" of the star
          schema) in data/processed/nissan.db:

            dim_source     - the documents our numbers come from
            dim_period     - reporting periods (read from the group CSV)
            dim_geography  - regions, countries and segments
            dim_company    - Nissan and its four peers
            dim_date       - one row per calendar day, 2018 to 2027

          Dimensions are loaded BEFORE the fact tables, because every fact
          row points to a dimension row (foreign keys).

Usage   : python src/create_database.py     (builds an EMPTY database)
          python src/load_dimensions.py     (fills the dimensions)

Exit code: 0 if loaded, 1 otherwise.
"""

import calendar
import csv
import sys
from datetime import date, timedelta

from db_utils import RAW_DIR, connect, count_rows

# ----------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------
DATE_START = date(2018, 1, 1)     # matches the start of our share price history
DATE_END = date(2027, 12, 31)     # covers the FY2026 forecast year and beyond

# (source_id, title, publisher, url, source_type, accessed_on)
SOURCES = [
    ("SUM-Q1FY2026", "Q1 FY2026 results summary and press release (3 Aug 2026)",
     "Nissan Motor Co.",
     "https://www.nissan-global.com/EN/IR/FINANCIAL_RESULTS/ASSETS/DATA/2026/20261st_summary_641_e.pdf",
     "primary", "2026-11-03"),
    ("SR-FY2025", "Securities Report for FY2025 (year ended 31 Mar 2026)",
     "Nissan Motor Co.",
     "https://www2.nissan-global.com/EN/IR/FINANCIAL_RESULTS/ASSETS/FR/2025/PDF/fr2025.pdf",
     "primary", "2026-11-03"),
    ("PR-FY2022", "Press release: FY2022 results (11 May 2023)",
     "Nissan Motor Co.",
     "https://global.nissannews.com/en/releases/230511-01-e",
     "primary", "2026-11-03"),
    ("PR-FY2023", "Press release: FY2023 results (9 May 2024)",
     "Nissan Motor Co.",
     "https://global.nissannews.com/en/releases/240509-01-e",
     "primary", "2026-11-03"),
    ("THEBEEP-FY2025", "Article on Nissan FY2025 results (14 May 2026)",
     "The Beep (Australia)",
     "https://thebeep.com.au/car-news/nissan-financial-results-fy2025-loss",
     "secondary", "2026-11-03"),
    ("AMS-OPPAMA", "Article on Oppama plant and capacity cuts",
     "Automotive Manufacturing Solutions",
     "https://www.automotivemanufacturingsolutions.com/news/nissan-to-halt-oppama-output-and-shift-to-kyushu/644825",
     "secondary", "2026-11-03"),
    ("MOTOR1-RENISSAN", "Article on Re:Nissan job cuts",
     "Motor1 France",
     "https://fr.motor1.com/news/759430/nissan-supprime-20000-emplois-ferme-7-usines/",
     "secondary", "2026-11-03"),
    ("YAHOO-FINANCE", "Daily share prices (7201.T, 7203.T, 7267.T, 7261.T, 7270.T)",
     "Yahoo Finance (yfinance library)",
     "https://finance.yahoo.com",
     "market_data", "2026-11-04"),
    ("FRED-DEXJPUS", "Daily USD/JPY exchange rate (series DEXJPUS)",
     "Federal Reserve Bank of St. Louis (FRED)",
     "https://fred.stlouisfed.org/series/DEXJPUS",
     "market_data", "2026-11-04"),
    ("OWID-EV", "Electric car sales by country",
     "Our World in Data (based on IEA data)",
     "https://ourworldindata.org/grapher/electric-car-sales",
     "market_data", "2026-11-04"),
]

# (geo_id, geo_name, geo_level, parent_geo_id, definition_note)
# A parent must appear BEFORE its children in this list.
GEOGRAPHIES = [
    (1, "Total", "total", None, "All markets combined"),
    (2, "Japan", "region", None, None),
    (3, "North America", "region", None, None),
    (4, "Europe", "region", None, None),
    (5, "Asia", "region", None, "Includes Oceania in the volume tables"),
    (6, "Others", "region", None, "Everything not listed above; actual results only"),
    (7, "Eliminations", "adjustment", None,
     "Removes sales between Nissan regions to avoid double counting"),
    (8, "USA", "country", 3, "Part of North America"),
    (9, "China", "country", 5, "Part of Asia; volumes cover calendar-year periods"),
    (10, "Overseas", "segment", 1, "Consolidated wholesale split: everything outside Japan"),
    (11, "Others incl. Asia ex-China", "region", None,
     "Forecast-only grouping; NOT comparable with the actual Others"),
]

# (company_id, ticker, company_name, is_focus_company)
COMPANIES = [
    (1, "7201.T", "Nissan", 1),
    (2, "7203.T", "Toyota", 0),
    (3, "7267.T", "Honda", 0),
    (4, "7261.T", "Mazda", 0),
    (5, "7270.T", "Subaru", 0),
]


# ----------------------------------------------------------------------
# Building the rows (the "Transform" part)
# ----------------------------------------------------------------------
def make_period_label(period_id: str, period_type: str, fiscal_year: int) -> str:
    """Create the readable name shown in reports, e.g. 'FY2025 (Apr 2025 - Mar 2026)'."""
    if period_type == "FY":
        return f"{period_id} (Apr {fiscal_year} - Mar {fiscal_year + 1})"
    if period_type == "FY_FORECAST":
        return f"FY{fiscal_year} forecast (Apr {fiscal_year} - Mar {fiscal_year + 1})"
    if period_type == "Q1":
        return f"Q1 FY{fiscal_year} (Apr - Jun {fiscal_year})"
    raise ValueError(f"Unknown period_type: {period_type}")


def build_period_rows() -> list:
    """Read the group financials CSV and turn each line into a dim_period row."""
    rows = []
    path = RAW_DIR / "nissan_group_financials.csv"
    with open(path, newline="", encoding="utf-8") as file:
        for order, line in enumerate(csv.DictReader(file), start=1):
            fiscal_year = int(line["fiscal_year"])
            rows.append((
                line["period_id"],
                make_period_label(line["period_id"], line["period_type"], fiscal_year),
                line["period_type"],
                fiscal_year,
                line["period_start"],
                line["period_end"],
                int(line["is_forecast"]),
                order,                      # keeps the CSV order for charts
            ))
    return rows


def build_date_rows() -> list:
    """Create one row for every day from DATE_START to DATE_END."""
    rows = []
    day = DATE_START
    while day <= DATE_END:
        month = day.month
        weekday = day.weekday()                       # Monday = 0 ... Sunday = 6
        fiscal_year = day.year if month >= 4 else day.year - 1   # fiscal year starts in April
        fiscal_quarter = ((month - 4) % 12) // 3 + 1             # Apr-Jun = 1 ... Jan-Mar = 4
        rows.append((
            day.isoformat(),                          # 'YYYY-MM-DD'
            day.year,
            (month - 1) // 3 + 1,                     # calendar quarter
            month,
            calendar.month_name[month],
            weekday + 1,                              # Monday = 1 ... Sunday = 7
            1 if weekday >= 5 else 0,
            fiscal_year,
            fiscal_quarter,
        ))
        day += timedelta(days=1)
    return rows


# ----------------------------------------------------------------------
# Loading (the "Load" part)
# ----------------------------------------------------------------------
def load(connection) -> dict:
    """Insert all dimension rows in one all-or-nothing transaction."""
    period_rows = build_period_rows()
    date_rows = build_date_rows()

    with connection:        # commits if everything works, undoes everything if not
        connection.executemany(
            "INSERT INTO dim_source VALUES (?, ?, ?, ?, ?, ?)", SOURCES)
        connection.executemany(
            "INSERT INTO dim_period VALUES (?, ?, ?, ?, ?, ?, ?, ?)", period_rows)
        connection.executemany(
            "INSERT INTO dim_geography VALUES (?, ?, ?, ?, ?)", GEOGRAPHIES)
        connection.executemany(
            "INSERT INTO dim_company VALUES (?, ?, ?, ?)", COMPANIES)
        connection.executemany(
            "INSERT INTO dim_date VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", date_rows)

    tables = ["dim_source", "dim_period", "dim_geography", "dim_company", "dim_date"]
    return {table: count_rows(connection, table) for table in tables}


def main() -> int:
    print("=" * 60)
    print("NISSAN TURNAROUND 2027 - LOAD DIMENSIONS")
    print("=" * 60)

    try:
        connection = connect()
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        return 1

    if count_rows(connection, "dim_period") > 0:
        print("[STOP] The dimension tables already contain data.")
        print("       To start again from an empty database, run first:")
        print("           python src/create_database.py")
        connection.close()
        return 1

    counts = load(connection)
    connection.close()

    for table, number in counts.items():
        print(f"[PASS] {table:<15} {number:>6} rows loaded")
    print("=" * 60)
    print("RESULT: DIMENSIONS LOADED. Next: python src/check_dimensions.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())