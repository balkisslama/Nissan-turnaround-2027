"""
check_charts.py
===============
Purpose : Prove that the eight charts are trustworthy.

          1. The numbers behind each chart are recalculated independently
             from the raw CSV files and compared.
          2. The three "waterfall" charts must CLOSE (start + all steps = end).
          3. Every chart file exists, is big enough, is not blank, and is not
             completely filled.

Usage   : python src/check_charts.py   (after python src/make_charts.py)

Exit code: 0 if every check passes, 1 otherwise.
"""

import sys

import numpy as np
import pandas as pd
from PIL import Image

from chart_style import FIGURES_DIR
from db_utils import RAW_DIR
from make_charts import (data_bridge, data_cash_flow, data_profit_vs_net, data_q1_swing,
                         data_regional_fy2025, data_sales_margin, data_volume_changes)

results = {"passed": 0, "failed": 0}

FIGURE_FILES = [
    "fig01_sales_and_margin.png", "fig02_operating_vs_net_profit.png", "fig03_cash_flow.png",
    "fig04_regional_profit_fy2025.png", "fig05_q1_profit_swing.png",
    "fig06_profit_bridge_fy2025.png", "fig07_profit_bridge_fy2026_outlook.png",
    "fig08_volume_changes.png",
]


def check(ok: bool, message: str) -> None:
    """Print one PASS/FAIL line and update the counters."""
    print(f"[{'PASS' if ok else 'FAIL'}] {message}")
    results["passed" if ok else "failed"] += 1


def close(a, b, tolerance: float = 0.051) -> bool:
    """True if two numbers differ by less than the tolerance."""
    return bool(np.all(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)) <= tolerance))


def read(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / name)


# ----------------------------------------------------------------------
# 1. The numbers behind the charts
# ----------------------------------------------------------------------
def check_chart_data() -> None:
    print("\n--- 1. THE NUMBERS BEHIND EACH CHART (recalculated from the raw CSVs) ---")
    group = read("nissan_group_financials.csv")
    years = group[group["period_type"].isin(["FY", "FY_FORECAST"])].sort_values("fiscal_year")
    actual = group[group["period_type"] == "FY"].sort_values("fiscal_year")

    chart = data_sales_margin()
    check(len(chart) == len(years)
          and close(chart["sales_trillion"], years["net_sales_bn"] / 1000, 0.0001)
          and close(chart["operating_margin_pct"], years["operating_profit_bn"] / years["net_sales_bn"] * 100),
          f"fig01 sales and margin: {len(chart)} years agree with the raw file")

    chart = data_profit_vs_net()
    check(len(chart) == len(actual)
          and close(chart["operating_profit_bn"], actual["operating_profit_bn"], 0.0001)
          and close(chart["net_income_bn"], actual["net_income_bn"], 0.0001),
          f"fig02 operating profit vs net income: {len(chart)} years agree")

    cash_years = actual[actual["cfo_bn"].notna()]
    chart = data_cash_flow()
    check(len(chart) == len(cash_years)
          and close(chart["simple_free_cash_flow_bn"], cash_years["cfo_bn"] + cash_years["cfi_bn"]),
          f"fig03 free cash flow: {len(chart)} years agree")

    regional = read("nissan_regional_results.csv")
    fy25 = regional[(regional["period_id"] == "FY2025") & (regional["region"] != "Eliminations")]
    fy25 = fy25.sort_values("operating_profit_bn")
    chart = data_regional_fy2025()
    check(chart["region"].tolist() == fy25["region"].tolist()
          and close(chart["operating_profit_bn"], fy25["operating_profit_bn"], 0.0001),
          "fig04 regional profit: 5 regions, same values and same order as the raw file")

    pivot = regional[regional["period_id"].isin(["Q1_FY2025", "Q1_FY2026"])].pivot(
        index="region", columns="period_id", values="operating_profit_bn")
    pivot["change"] = pivot["Q1_FY2026"] - pivot["Q1_FY2025"]
    swing = data_q1_swing()
    steps = {label: amount for label, amount, _ in swing["steps"]}
    region_steps_ok = all(close(steps[region], pivot.loc[region, "change"])
                          for region in ["North America", "Japan", "Europe", "Asia", "Others"])
    check(region_steps_ok, "fig05 Q1 swing: every regional step equals the raw change")

    volumes = read("nissan_volumes.csv")
    retail = volumes[volumes["metric"] == "retail_sales"]
    q1 = retail[(retail["period_id"].isin(["Q1_FY2025", "Q1_FY2026"])) & (retail["market_level"] != "total")]
    q1 = q1.pivot(index="market", columns="period_id", values="units_thousand")
    q1["pct"] = (q1["Q1_FY2026"] / q1["Q1_FY2025"] - 1) * 100
    left, right = data_volume_changes()
    check(len(left) == len(q1) and all(close(row.change_pct, q1.loc[row.market, "pct"]) for row in left.itertuples()),
          f"fig08 left panel: {len(left)} markets agree with the raw volumes")

    def units(period, market):
        row = retail[(retail["period_id"] == period) & (retail["market"] == market)]
        return float(row["units_thousand"].iloc[0])

    expected = {name: (units("FY2026F", name) / units("FY2025", name) - 1) * 100
                for name in ["Japan", "North America", "Europe", "China"]}
    rest_actual = units("FY2025", "Asia") + units("FY2025", "Others") - units("FY2025", "China")
    expected["Rest of world (Asia ex-China + Others)"] = (
        units("FY2026F", "Others incl. Asia ex-China") / rest_actual - 1) * 100
    check(len(right) == 5 and all(close(row.change_pct, expected[row.market]) for row in right.itertuples()),
          "fig08 right panel: 5 forecast changes agree with the raw volumes")


# ----------------------------------------------------------------------
# 2. The waterfalls must close
# ----------------------------------------------------------------------
def check_waterfalls() -> None:
    print("\n--- 2. THE WATERFALLS MUST CLOSE (start + steps = end) ---")
    for label, data in [("fig05 Q1 profit swing", data_q1_swing()),
                        ("fig06 FY2025 bridge", data_bridge("FY2025_ACTUAL")),
                        ("fig07 FY2026 outlook bridge", data_bridge("FY2026_OUTLOOK"))]:
        total = sum(amount for _, amount, _ in data["steps"])
        check(close(data["start"] + total, data["end"]),
              f"{label}: {data['start']} + {total:.1f} = {data['start'] + total:.1f} equals the end {data['end']}")


# ----------------------------------------------------------------------
# 3. The image files
# ----------------------------------------------------------------------
def check_images() -> None:
    print("\n--- 3. THE IMAGE FILES ---")
    for name in FIGURE_FILES:
        path = FIGURES_DIR / name
        if not path.exists():
            check(False, f"{name}: file not found. Run python src/make_charts.py")
            continue
        size_kb = path.stat().st_size / 1024
        image = Image.open(path).convert("RGB")
        pixels = np.asarray(image)
        coloured_share = float((pixels.min(axis=2) < 240).mean())       # share of non-white pixels
        ok = size_kb > 20 and image.width >= 1000 and image.height >= 500 \
            and 0.01 < coloured_share < 0.9
        check(ok, f"{name}: {image.width}x{image.height} px, {size_kb:.0f} KB, "
                  f"{coloured_share * 100:.1f}% of the pixels are not white")


def main() -> int:
    print("=" * 72)
    print("NISSAN TURNAROUND 2027 - CHECK THE CHARTS")
    print("=" * 72)
    try:
        check_chart_data()
        check_waterfalls()
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        return 1
    check_images()

    print("\n" + "=" * 72)
    print(f"Checks passed: {results['passed']} | failed: {results['failed']}")
    if results["failed"]:
        print("RESULT: FAILED. Read the [FAIL] lines above.")
        return 1
    print("RESULT: ALL CHECKS PASSED. The charts match the data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())