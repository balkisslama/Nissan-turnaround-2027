"""
check_driver_analysis.py
========================
Purpose : Prove that the driver and sensitivity numbers are right.

          Every figure is recalculated a SECOND time with plain Python (the csv
          module and simple arithmetic, no pandas), straight from the raw CSV
          files, and compared with the tables saved by driver_analysis.py.
          Also checks that the groups of causes add up to the profit change,
          that the sensitivity grid behaves sensibly, and that the charts exist.

Usage   : python src/driver_analysis.py
          python src/check_driver_analysis.py

Exit code: 0 if every check passes, 1 otherwise.
"""

import csv
import sys

import numpy as np
import pandas as pd
from PIL import Image

from chart_style import FIGURES_DIR
from db_utils import PROJECT_ROOT, RAW_DIR
from driver_analysis import ASSUMPTIONS, CATEGORY_OF

TABLES_DIR = PROJECT_ROOT / "reports" / "tables"
FIGURE_FILES = ["fig12_outlook_drivers.png", "fig13_volume_tariff_sensitivity.png"]
results = {"passed": 0, "failed": 0}


def check(ok: bool, message: str) -> None:
    """Print one PASS/FAIL line and update the counters."""
    print(f"[{'PASS' if ok else 'FAIL'}] {message}")
    results["passed" if ok else "failed"] += 1


def same(a, b, tolerance: float = 0.051) -> bool:
    return bool(np.all(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)) <= tolerance))


def rows_of(name: str) -> list:
    with open(RAW_DIR / name, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def saved(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES_DIR / f"{name}.csv")


# ----------------------------------------------------------------------
# Independent inputs (plain Python)
# ----------------------------------------------------------------------
def raw_numbers() -> dict:
    bridge = rows_of("nissan_profit_bridge.csv")
    group = {r["period_id"]: r for r in rows_of("nissan_group_financials.csv")}
    targets = {r["metric_id"]: float(r["value"]) for r in rows_of("nissan_restructuring_targets.csv")}
    volumes = {(r["period_id"], r["metric"], r["market"]): float(r["units_thousand"])
               for r in rows_of("nissan_volumes.csv")}

    def amount(bridge_id, item):
        return sum(float(r["amount_bn"]) for r in bridge
                   if r["bridge_id"] == bridge_id and r["item"] == item and r["item_type"] == "change")

    out = {"bridge": bridge, "group": group, "targets": targets, "volumes": volumes, "amount": amount}
    out["retail25"] = volumes[("FY2025", "retail_sales", "Total")]
    out["original"], out["revised"] = targets["volume_outlook_original_fy2026"], targets["volume_outlook_revised_fy2026"]
    out["sales_perf"] = amount("FY2026_OUTLOOK", "Sales performance")
    out["c"] = out["sales_perf"] / (out["original"] - out["retail25"])
    out["tariff25"] = -amount("FY2025_ACTUAL", "US tariffs")
    out["tariff26"] = out["tariff25"] - amount("FY2026_OUTLOOK", "US tariffs")
    out["outlook"] = float(group["FY2026F"]["operating_profit_bn"])
    return out


# ----------------------------------------------------------------------
# Checks
# ----------------------------------------------------------------------
def check_drivers(r: dict) -> None:
    print("\n--- 1. GROUPED DRIVERS ---")
    totals = {}
    for row in r["bridge"]:
        if row["item_type"] == "change":
            key = (CATEGORY_OF[row["item"]], row["bridge_id"])
            totals[key] = totals.get(key, 0.0) + float(row["amount_bn"])
    categories = saved("driver_categories")
    ok = all(same(row.fy2025_actual_bn, totals.get((row.category, "FY2025_ACTUAL"), 0.0))
             and same(row.fy2026_outlook_bn, totals.get((row.category, "FY2026_OUTLOOK"), 0.0))
             for row in categories.itertuples())
    check(ok and len(categories) == 5, "the 5 groups of causes agree with the raw bridge file")
    change25 = float(r["group"]["FY2025"]["operating_profit_bn"]) - float(r["group"]["FY2024"]["operating_profit_bn"])
    change26 = r["outlook"] - float(r["group"]["FY2025"]["operating_profit_bn"])
    check(same(categories["fy2025_actual_bn"].sum(), change25) and same(categories["fy2026_outlook_bn"].sum(), change26),
          f"the groups add up to the profit changes ({change25:+.1f} in FY2025, {change26:+.1f} in the FY2026 outlook)")


def check_quality(r: dict) -> None:
    print("\n--- 2. QUALITY OF THE OUTLOOK ---")
    quality = saved("outlook_quality").set_index("measure")
    op25, s25 = float(r["group"]["FY2025"]["operating_profit_bn"]), float(r["group"]["FY2025"]["net_sales_bn"])
    s26 = float(r["group"]["FY2026F"]["net_sales_bn"])
    expected = {
        "FY2026 outlook, as published": (r["outlook"], s26),
        "FY2026 outlook without the derived sales performance": (r["outlook"] - r["sales_perf"], s26),
        "FY2025 operating profit, as reported": (op25, s25),
        "FY2025 without one-time gains": (op25 - r["amount"]("FY2025_ACTUAL", "One-time items"), s25),
        "FY2025 without one-time gains and without US tariffs":
            (op25 - r["amount"]("FY2025_ACTUAL", "One-time items") - r["amount"]("FY2025_ACTUAL", "US tariffs"), s25),
    }
    ok = all(same(quality.loc[name, "operating_profit_bn"], value) and same(quality.loc[name, "operating_margin_pct"], value / sales * 100, 0.011)
             for name, (value, sales) in expected.items())
    check(ok and len(quality) == 5, "the 5 profit measures and their margins agree")


def check_parameters(r: dict) -> None:
    print("\n--- 3. DERIVED PARAMETERS AND BREAK-EVEN ---")
    parameters = saved("scenario_parameters").set_index("parameter")
    check(same(parameters.loc["profit_per_extra_car", "value"], r["c"], 0.00051)
          and same(parameters.loc["volume_cut_impact_bn", "value"], (r["revised"] - r["original"]) * r["c"])
          and same(parameters.loc["tariff_burden_fy2026_bn", "value"], r["tariff26"]),
          f"profit per extra car {r['c']:.3f}, volume cut impact {(r['revised'] - r['original']) * r['c']:.1f} bn, tariff burden {r['tariff26']:.0f} bn agree")
    derived = set(parameters[parameters["origin"] == "DERIVED"].index)
    check(derived == {"sales_performance_outlook_bn", "profit_per_extra_car", "volume_cut_impact_bn", "tariff_burden_fy2026_bn"},
          "exactly the four derived parameters are flagged DERIVED")

    breakeven = saved("break_even_volume").set_index("case")
    ok = True
    for case, multiple in ASSUMPTIONS["contribution_cases"].items():
        volume = r["revised"] - r["outlook"] / (r["c"] * multiple)
        ok &= same(breakeven.loc[case, "break_even_volume_thousand"], volume, 0.51)
        ok &= same(breakeven.loc[case, "headroom_thousand"], r["revised"] - volume, 0.51)
    check(ok, "break-even volume and headroom agree in the low, central and high cases")


def check_grid(r: dict) -> None:
    print("\n--- 4. SENSITIVITY GRID ---")
    grid = saved("volume_tariff_grid")
    expected = [r["outlook"] + (row.retail_volume_thousand - r["revised"]) * r["c"]
                - row.tariff_burden_change_pct / 100 * r["tariff26"] for row in grid.itertuples()]
    check(len(grid) == len(ASSUMPTIONS["volumes"]) * len(ASSUMPTIONS["tariff_changes_pct"])
          and same(grid["operating_profit_bn"], expected), f"all {len(grid)} cells agree")
    centre = grid[(grid["retail_volume_thousand"] == r["revised"]) & (grid["tariff_burden_change_pct"] == 0)]
    check(len(centre) == 1 and same(centre["operating_profit_bn"].iloc[0], r["outlook"]),
          f"the base cell ({r['revised']:.0f}k cars, tariff 0%) equals Nissan's outlook of {r['outlook']:.0f}")
    by_volume = all(part.sort_values("retail_volume_thousand")["operating_profit_bn"].is_monotonic_increasing
                    for _, part in grid.groupby("tariff_burden_change_pct"))
    by_tariff = all(part.sort_values("tariff_burden_change_pct")["operating_profit_bn"].is_monotonic_decreasing
                    for _, part in grid.groupby("retail_volume_thousand"))
    check(by_volume and by_tariff, "sanity: profit rises with volume and falls as the tariff burden rises")


def check_capacity(r: dict) -> None:
    print("\n--- 5. PLANT UTILISATION OUTSIDE CHINA ---")
    capacity = saved("capacity_utilisation")
    ok = True
    for row in capacity.itertuples():
        production = r["volumes"][(row.period, "production", "Total")]
        china_retail = r["volumes"][(row.period, "retail_sales", "China")]
        gap = row.china_production_assumed_thousand - china_retail
        ok &= gap in ASSUMPTIONS["china_production_gap"]
        outside = production - row.china_production_assumed_thousand
        ok &= same(row.production_outside_china_thousand, outside, 0.01)
        ok &= same(row.utilisation_pct, outside / row.capacity_thousand * 100, 0.051)
    check(ok and len(capacity) == 12, "the 12 utilisation estimates (2 years x 3 assumptions x 2 capacity bases) agree")


def check_images() -> None:
    print("\n--- 6. THE IMAGE FILES ---")
    for name in FIGURE_FILES:
        path = FIGURES_DIR / name
        if not path.exists():
            check(False, f"{name}: file not found")
            continue
        size_kb = path.stat().st_size / 1024
        image = Image.open(path).convert("RGB")
        share = float((np.asarray(image).min(axis=2) < 240).mean())
        check(size_kb > 20 and image.width >= 1000 and image.height >= 500 and 0.01 < share < 0.95,
              f"{name}: {image.width}x{image.height} px, {size_kb:.0f} KB, {share * 100:.1f}% of the pixels are not white")


def main() -> int:
    print("=" * 72)
    print("NISSAN TURNAROUND 2027 - CHECK THE DRIVER ANALYSIS")
    print("=" * 72)
    try:
        r = raw_numbers()
        check_drivers(r)
        check_quality(r)
        check_parameters(r)
        check_grid(r)
        check_capacity(r)
    except FileNotFoundError as error:
        print(f"[STOP] {error}. Run python src/driver_analysis.py first.")
        return 1
    check_images()

    print("\n" + "=" * 72)
    print(f"Checks passed: {results['passed']} | failed: {results['failed']}")
    if results["failed"]:
        print("RESULT: FAILED. Read the [FAIL] lines above.")
        return 1
    print("RESULT: ALL CHECKS PASSED. The driver analysis matches the raw data.")
    return 0


if __name__ == "__main__":
    sys.exit(main())