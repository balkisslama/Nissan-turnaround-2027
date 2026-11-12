"""
check_market_analysis.py
========================
Purpose : Prove that the market statistics, the electric-car analysis and
          their three charts are correct.

          Every statistic is recalculated a SECOND time, with plain numpy,
          straight from the raw CSV files (not from the database), and compared
          with the tables saved by market_statistics.py and ev_market_analysis.py.

Usage   : python src/market_statistics.py
          python src/ev_market_analysis.py
          python src/check_market_analysis.py

Exit code: 0 if every check passes, 1 otherwise.
"""

import sys

import numpy as np
import pandas as pd
from PIL import Image

from chart_style import FIGURES_DIR
from db_utils import PROJECT_ROOT, RAW_DIR
from ev_market_analysis import MARKET_ALIASES, START_YEAR, find_names
from market_statistics import START_DATE

TABLES_DIR = PROJECT_ROOT / "reports" / "tables"
FIGURE_FILES = ["fig09_share_price_rebased.png", "fig10_drawdowns.png", "fig11_ev_markets.png"]

results = {"passed": 0, "failed": 0}


def check(ok: bool, message: str) -> None:
    """Print one PASS/FAIL line and update the counters."""
    print(f"[{'PASS' if ok else 'FAIL'}] {message}")
    results["passed" if ok else "failed"] += 1


def same(a, b, tolerance: float) -> bool:
    return bool(np.all(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)) <= tolerance))


# ----------------------------------------------------------------------
# The raw files, cleaned independently
# ----------------------------------------------------------------------
def raw_prices() -> dict:
    """company -> (array of dates as text, array of prices), since START_DATE."""
    data = pd.read_csv(RAW_DIR / "stock_prices_daily.csv")
    data = data[(data["close_jpy"] > 0) & (data["volume"] > 0)].copy()
    data["date"] = data["date"].astype(str).str[:10]
    data = data.drop_duplicates(subset=["date", "ticker"], keep="last")
    data = data[data["date"] >= START_DATE].sort_values("date")
    return {name: (part["date"].to_numpy(), part["close_jpy"].to_numpy(dtype=float))
            for name, part in data.groupby("company", sort=False)}


def raw_fx() -> tuple:
    data = pd.read_csv(RAW_DIR / "usd_jpy_daily.csv")
    data = data[data["usd_jpy"] > 0].copy()
    data["date"] = data["date"].astype(str).str[:10]
    data = data.drop_duplicates(subset="date", keep="last")
    data = data[data["date"] >= START_DATE].sort_values("date")
    return data["date"].to_numpy(), data["usd_jpy"].to_numpy(dtype=float)


# ----------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------
def check_statistics() -> None:
    print("\n--- 1. SHARE PRICE STATISTICS (recalculated with numpy from the raw CSV) ---")
    stats = pd.read_csv(TABLES_DIR / "market_statistics.csv").set_index("company")
    prices = raw_prices()
    check(set(stats.index) == set(prices), f"{len(stats)} companies in the table: {', '.join(stats.index)}")

    expected = {}
    for company, (dates, p) in prices.items():
        returns = p[1:] / p[:-1] - 1
        drawdown = (p / np.maximum.accumulate(p) - 1) * 100
        expected[company] = {
            "first_day": dates[0], "last_day": dates[-1],
            "total_return_pct": (p[-1] / p[0] - 1) * 100,
            "annual_volatility_pct": returns.std(ddof=1) * np.sqrt(252) * 100,
            "max_drawdown_pct": drawdown.min(), "max_drawdown_date": dates[int(drawdown.argmin())],
            "drawdown_now_pct": drawdown[-1],
        }
    frame = pd.DataFrame(expected).T
    check(all(stats.loc[c, "first_day"] == frame.loc[c, "first_day"]
              and stats.loc[c, "last_day"] == frame.loc[c, "last_day"] for c in stats.index),
          "first and last trading day agree")
    check(same(stats["total_return_pct"], frame.loc[stats.index, "total_return_pct"], 0.011),
          "total return agrees")
    check(same(stats["annual_volatility_pct"], frame.loc[stats.index, "annual_volatility_pct"], 0.011),
          "annual volatility agrees")
    check(same(stats["max_drawdown_pct"], frame.loc[stats.index, "max_drawdown_pct"], 0.011)
          and same(stats["drawdown_now_pct"], frame.loc[stats.index, "drawdown_now_pct"], 0.011),
          "maximum drawdown and drawdown today agree")
    check(all(stats.loc[c, "max_drawdown_date"] == frame.loc[c, "max_drawdown_date"] for c in stats.index),
          "the date of each maximum drawdown agrees")
    check((stats["max_drawdown_pct"] <= 0).all() and stats["annual_volatility_pct"].between(5, 100).all(),
          "sanity: drawdowns are negative and volatilities are between 5% and 100%")


def check_yen_sensitivity() -> None:
    print("\n--- 2. YEN SENSITIVITY ---")
    yen = pd.read_csv(TABLES_DIR / "yen_sensitivity.csv").set_index("company")
    prices = raw_prices()
    fx_dates, fx_values = raw_fx()
    fx_lookup = dict(zip(fx_dates, fx_values))
    correlations, betas = {}, {}
    for company, (dates, p) in prices.items():
        common = [i for i, d in enumerate(dates) if d in fx_lookup]
        stock = p[common]
        rate = np.array([fx_lookup[dates[i]] for i in common])
        r_stock, r_rate = stock[1:] / stock[:-1] - 1, rate[1:] / rate[:-1] - 1
        correlations[company] = np.corrcoef(r_stock, r_rate)[0, 1]
        betas[company] = np.cov(r_stock, r_rate, ddof=1)[0, 1] / np.var(r_rate, ddof=1)
    check(same(yen["correlation"], pd.Series(correlations)[yen.index], 0.0011), "correlation with USD/JPY agrees")
    check(same(yen["beta"], pd.Series(betas)[yen.index], 0.0011), "beta to USD/JPY agrees")


def check_ev() -> None:
    print("\n--- 3. ELECTRIC CAR MARKETS ---")
    summary = pd.read_csv(TABLES_DIR / "ev_summary.csv").set_index("market")
    raw = pd.read_csv(RAW_DIR / "ev_sales_by_country.csv")
    raw = raw[raw["electric_car_sales"] >= 0].drop_duplicates(subset=["country", "year"], keep="last")
    found = find_names(raw["country"].unique())
    check(len(summary) > 0 and set(summary.index) == set(found),
          f"{len(summary)} markets in the table, the same as found in the raw file: {', '.join(summary.index)}")

    values_ok, growth_ok = True, True
    for market in summary.index:
        part = raw[(raw["country"] == found[market]) & (raw["year"] >= START_YEAR) & (raw["year"] <= 2026)]
        part = part.sort_values("year")
        first, last = part.iloc[0], part.iloc[-1]
        row = summary.loc[market]
        values_ok &= (int(row["first_year"]) == first["year"] and int(row["latest_year"]) == last["year"]
                      and same(row["latest_sales_million"], last["electric_car_sales"] / 1e6, 0.0006)
                      and same(row["first_sales_million"], first["electric_car_sales"] / 1e6, 0.0006))
        multiple = last["electric_car_sales"] / first["electric_car_sales"]
        cagr = (multiple ** (1 / (last["year"] - first["year"])) - 1) * 100
        growth_ok &= same(row["growth_multiple"], multiple, 0.0051) and same(row["cagr_pct"], cagr, 0.051)
    check(values_ok, "first and latest year and sales agree with the raw file")
    check(growth_ok, "growth multiple and compound annual growth agree")


def check_images() -> None:
    print("\n--- 4. THE IMAGE FILES ---")
    for name in FIGURE_FILES:
        path = FIGURES_DIR / name
        if not path.exists():
            check(False, f"{name}: file not found")
            continue
        size_kb = path.stat().st_size / 1024
        image = Image.open(path).convert("RGB")
        share = float((np.asarray(image).min(axis=2) < 240).mean())
        check(size_kb > 20 and image.width >= 1000 and image.height >= 500 and 0.01 < share < 0.9,
              f"{name}: {image.width}x{image.height} px, {size_kb:.0f} KB, {share * 100:.1f}% of the pixels are not white")


def main() -> int:
    print("=" * 72)
    print("NISSAN TURNAROUND 2027 - CHECK THE MARKET ANALYSIS")
    print("=" * 72)
    try:
        check_statistics()
        check_yen_sensitivity()
        check_ev()
    except FileNotFoundError as error:
        print(f"[STOP] {error}. Run market_statistics.py and ev_market_analysis.py first.")
        return 1
    check_images()

    print("\n" + "=" * 72)
    print(f"Checks passed: {results['passed']} | failed: {results['failed']}")
    if results["failed"]:
        print("RESULT: FAILED. Read the [FAIL] lines above.")
        return 1
    print("RESULT: ALL CHECKS PASSED. The market analysis matches the raw data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())