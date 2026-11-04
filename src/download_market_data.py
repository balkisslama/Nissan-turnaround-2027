"""
download_market_data.py
=======================
Purpose : Download three external datasets used to put Nissan's results in
          context, and save them as CSV files in data/raw/:

            1. stock_prices_daily.csv   - daily share prices of Nissan and four
                                          Japanese peers (Yahoo Finance)
            2. usd_jpy_daily.csv        - daily USD/JPY exchange rate (FRED)
            3. ev_sales_by_country.csv  - electric car sales by country
                                          (Our World in Data / IEA)

          Each download is independent: if one source is unreachable, the
          others still run and the script tells you what to do manually.

Usage   : python src/download_market_data.py   (from the project root)

Exit code: 0 if all three downloads succeeded, 1 otherwise.
"""

import sys
import warnings
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# Start in 2018 so the history includes November 2018 (arrest of Carlos Ghosn),
# the event usually seen as the start of Nissan's governance and strategy crisis.
START_DATE = "2018-01-01"

# Ticker symbols on the Tokyo Stock Exchange (".T" suffix on Yahoo Finance).
TICKERS = {
    "7201.T": "Nissan",
    "7203.T": "Toyota",
    "7267.T": "Honda",
    "7261.T": "Mazda",
    "7270.T": "Subaru",
}

FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXJPUS"

# Two address variants are tried in order; the first one that parses wins.
OWID_URLS = [
    "https://ourworldindata.org/grapher/electric-car-sales.csv",
    "https://ourworldindata.org/grapher/electric-car-sales.csv"
    "?v=1&csvType=full&useColumnShortNames=true",
]

# Some websites reject requests that do not look like a browser.
HEADERS = {"User-Agent": "Mozilla/5.0 (educational portfolio project)"}
TIMEOUT_SECONDS = 30


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def download_text(url: str) -> str:
    """Download a URL and return its text. Raises an error on HTTP failure."""
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.text


def parse_fred_csv(text: str) -> pd.DataFrame:
    """Turn the raw FRED CSV text into a clean date / usd_jpy table.

    FRED marks missing days (holidays) with a dot '.', which we convert to
    a missing value and drop.
    """
    raw = pd.read_csv(StringIO(text))
    date_column, value_column = raw.columns[0], raw.columns[1]
    clean = pd.DataFrame({
        "date": pd.to_datetime(raw[date_column]),
        "usd_jpy": pd.to_numeric(raw[value_column], errors="coerce"),
    })
    clean = clean.dropna(subset=["usd_jpy"])
    clean = clean[clean["date"] >= START_DATE]
    return clean.reset_index(drop=True)


def parse_owid_csv(text: str) -> pd.DataFrame:
    """Turn the raw Our World in Data CSV text into a clean table.

    The file must contain Entity, Code and Year columns (in any letter case);
    the first remaining column is the measured value (new electric cars sold).
    If the format is not recognised, the error shows what was received so the
    problem can be diagnosed instead of guessed.
    """
    raw = pd.read_csv(StringIO(text.lstrip("\ufeff")))
    lookup = {str(column).strip().lower(): column for column in raw.columns}
    required = ["entity", "code", "year"]

    missing = [name for name in required if name not in lookup]
    if missing:
        preview = text[:150].replace("\n", " | ")
        raise ValueError(f"unexpected OWID format, missing {missing}. "
                         f"First characters received: {preview!r}")

    value_columns = [c for c in raw.columns if str(c).strip().lower() not in required]
    if not value_columns:
        raise ValueError("OWID file has no value column")

    clean = raw[[lookup["entity"], lookup["code"], lookup["year"], value_columns[0]]].copy()
    clean.columns = ["country", "country_code", "year", "electric_car_sales"]
    return clean


# ----------------------------------------------------------------------
# The three downloads
# ----------------------------------------------------------------------
def get_stock_prices() -> pd.DataFrame:
    """Daily closing prices (adjusted for splits and dividends) per company."""
    import yfinance as yf  # imported here so a missing library is reported clearly

    frames = []
    # yfinance prints harmless deprecation warnings from its own internals;
    # they are hidden here so the output stays readable.
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=".*inplace keyword.*")
        for ticker, company in TICKERS.items():
            history = yf.Ticker(ticker).history(start=START_DATE, auto_adjust=True)
            if history.empty:
                raise ValueError(f"Yahoo Finance returned no data for {ticker}")
            frame = pd.DataFrame({
                "date": pd.to_datetime(history.index).tz_localize(None).normalize(),
                "ticker": ticker,
                "company": company,
                "close_jpy": history["Close"].round(2).to_numpy(),
                "volume": history["Volume"].to_numpy(),
            })
            frames.append(frame)
    return pd.concat(frames, ignore_index=True)


def get_usd_jpy() -> pd.DataFrame:
    """Daily USD/JPY exchange rate from FRED (series DEXJPUS)."""
    return parse_fred_csv(download_text(FRED_URL))


def get_ev_sales() -> pd.DataFrame:
    """Number of new electric cars sold per country and year."""
    errors = []
    for url in OWID_URLS:
        try:
            return parse_owid_csv(download_text(url))
        except Exception as error:  # noqa: BLE001 - try the next address
            errors.append(f"{url} -> {type(error).__name__}: {str(error)[:300]}")
    raise RuntimeError("every OWID address failed:\n       " + "\n       ".join(errors))


# ----------------------------------------------------------------------
# Runner
# ----------------------------------------------------------------------
DOWNLOADS = [
    ("Stock prices (Yahoo Finance)", get_stock_prices, "stock_prices_daily.csv",
     "Yahoo sometimes rate-limits requests. Wait a few minutes and rerun. If it keeps failing, send me the exact error."),
    ("USD/JPY rate (FRED)", get_usd_jpy, "usd_jpy_daily.csv",
     "Open https://fred.stlouisfed.org/series/DEXJPUS, click Download (CSV), save it as data/raw/usd_jpy_daily.csv."),
    ("EV sales (Our World in Data)", get_ev_sales, "ev_sales_by_country.csv",
     "Open https://ourworldindata.org/grapher/electric-car-sales, Download tab, save the CSV as data/raw/ev_sales_by_country.csv."),
]


def main() -> int:
    """Run each download independently and print a summary."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 60)
    print("NISSAN TURNAROUND 2027 - MARKET DATA DOWNLOAD")
    print("=" * 60)

    failures = 0
    for label, function, filename, manual_help in DOWNLOADS:
        print(f"\n>> {label}")
        try:
            data = function()
            if data.empty:
                raise ValueError("the download returned zero rows")
            data.to_csv(RAW_DIR / filename, index=False)
            print(f"[PASS] saved {len(data):,} rows -> data/raw/{filename}")
            if "date" in data.columns:
                print(f"       date range: {data['date'].min().date()} "
                      f"to {data['date'].max().date()}")
        except Exception as error:  # noqa: BLE001 - we want to catch everything here
            failures += 1
            print(f"[FAIL] {type(error).__name__}: {error}")
            print(f"       What to do: {manual_help}")

    print("\n" + "=" * 60)
    if failures:
        print(f"RESULT: {failures} of {len(DOWNLOADS)} downloads FAILED. See messages above.")
        return 1
    print("RESULT: ALL DOWNLOADS SUCCEEDED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())