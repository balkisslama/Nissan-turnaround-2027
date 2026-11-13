"""
driver_analysis.py
==================
Purpose : Turn Nissan's official profit bridge into numbers a scenario model
          can use. It answers four questions:

            1. Which causes does the FY2026 outlook rely on? (grouped drivers)
            2. How much of the outlook survives without the derived sales effect,
               and what was FY2025 profit without one-time gains and tariffs?
            3. How sensitive is profit to volume and to the US tariff burden,
               and how far above break-even volume is the outlook?
            4. Roughly how full are Nissan's plants outside China?

          Everything marked "derived" or "assumption" is an illustrative
          estimate made by us from published numbers, not a Nissan figure.
          Assumptions live in ONE place (ASSUMPTIONS below) so they are easy
          to challenge and to change.

          Saves tables in reports/tables/ and two charts in reports/figures/.

Usage   : python src/driver_analysis.py

Exit code: 0 if everything was produced, 1 otherwise.
"""

import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle

from chart_style import COLORS, apply_style, save_figure
from db_utils import PROJECT_ROOT, RAW_DIR

TABLES_DIR = PROJECT_ROOT / "reports" / "tables"

# ----------------------------------------------------------------------
# ASSUMPTIONS: every illustrative choice is here, in one place
# ----------------------------------------------------------------------
ASSUMPTIONS = {
    # multiples of the derived profit-per-extra-car (low / central / high)
    "contribution_cases": {"low": 0.5, "central": 1.0, "high": 1.5},
    # retail volumes (thousand cars) and tariff-burden changes (%) in the sensitivity grid
    "volumes": [2900, 3000, 3100, 3150, 3200, 3300, 3400],
    "tariff_changes_pct": [-50, -25, 0, 25, 50],
    # China production is not published: we assume it equals China retail sales
    # plus or minus this many thousand cars
    "china_production_gap": [-100, 0, 100],
}

CATEGORY_OF = {
    "Foreign exchange": "External pressures", "Raw materials": "External pressures",
    "US tariffs": "External pressures", "Inflation": "External pressures",
    "Monozukuri cost savings": "Cost savings (self-help)",
    "Sales performance": "Sales performance",
    "One-time items": "One-time items",
    "Other items": "Other", "Rounding difference": "Other",
}
CATEGORY_ORDER = ["External pressures", "Cost savings (self-help)", "Sales performance",
                  "One-time items", "Other"]


# ----------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------
def read_inputs() -> dict:
    bridge = pd.read_csv(RAW_DIR / "nissan_profit_bridge.csv")
    group = pd.read_csv(RAW_DIR / "nissan_group_financials.csv").set_index("period_id")
    targets = pd.read_csv(RAW_DIR / "nissan_restructuring_targets.csv").set_index("metric_id")["value"]
    volumes = pd.read_csv(RAW_DIR / "nissan_volumes.csv")
    return {"bridge": bridge, "group": group, "targets": targets, "volumes": volumes}


def units(volumes: pd.DataFrame, metric: str, period: str, market: str) -> float:
    row = volumes[(volumes["metric"] == metric) & (volumes["period_id"] == period)
                  & (volumes["market"] == market)]
    return float(row["units_thousand"].iloc[0])


# ----------------------------------------------------------------------
# 1. Grouped drivers
# ----------------------------------------------------------------------
def driver_table(bridge: pd.DataFrame) -> pd.DataFrame:
    """One row per cause: FY2025 actual and FY2026 outlook side by side."""
    changes = bridge[bridge["item_type"] == "change"].copy()
    changes["category"] = changes["item"].map(CATEGORY_OF)
    wide = changes.pivot_table(index=["item", "category"], columns="bridge_id",
                               values="amount_bn", aggfunc="sum").reset_index()
    derived = changes[changes["is_derived"] == 1].groupby("item")["bridge_id"].apply(list).to_dict()
    wide["derived_in"] = wide["item"].map(lambda item: ", ".join(derived.get(item, [])))
    wide = wide.rename(columns={"FY2025_ACTUAL": "fy2025_actual_bn", "FY2026_OUTLOOK": "fy2026_outlook_bn"})
    wide["fy2025_actual_bn"] = wide["fy2025_actual_bn"].fillna(0.0)
    wide["fy2026_outlook_bn"] = wide["fy2026_outlook_bn"].fillna(0.0)
    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    return wide.sort_values(["category", "item"], key=lambda s: s.map(order) if s.name == "category" else s) \
               .reset_index(drop=True)[["category", "item", "fy2025_actual_bn", "fy2026_outlook_bn", "derived_in"]]


def category_table(drivers: pd.DataFrame) -> pd.DataFrame:
    totals = drivers.groupby("category")[["fy2025_actual_bn", "fy2026_outlook_bn"]].sum()
    return totals.reindex(CATEGORY_ORDER).round(1).reset_index()


# ----------------------------------------------------------------------
# 2. Quality of the outlook
# ----------------------------------------------------------------------
def quality_table(inputs: dict, drivers: pd.DataFrame) -> pd.DataFrame:
    group = inputs["group"]
    amount = drivers.set_index("item")
    sales_derived = float(amount.loc["Sales performance", "fy2026_outlook_bn"])
    one_time_2025 = float(amount.loc["One-time items", "fy2025_actual_bn"])
    tariff_2025 = float(amount.loc["US tariffs", "fy2025_actual_bn"])
    op25, sales25 = group.loc["FY2025", "operating_profit_bn"], group.loc["FY2025", "net_sales_bn"]
    op26, sales26 = group.loc["FY2026F", "operating_profit_bn"], group.loc["FY2026F", "net_sales_bn"]
    rows = [
        ("FY2026 outlook, as published", op26, sales26, "Nissan's outlook of May and August 2026"),
        ("FY2026 outlook without the derived sales performance", op26 - sales_derived, sales26,
         "Sales performance of +157 bn is derived by us, not stated by Nissan"),
        ("FY2025 operating profit, as reported", op25, sales25, "Reported"),
        ("FY2025 without one-time gains", op25 - one_time_2025, sales25,
         "Removes the +148 bn of one-time items (illustrative arithmetic)"),
        ("FY2025 without one-time gains and without US tariffs", op25 - one_time_2025 - tariff_2025, sales25,
         "Also adds back the 286 bn tariff cost (illustrative arithmetic)"),
    ]
    return pd.DataFrame([{"measure": m, "operating_profit_bn": round(v, 1),
                          "operating_margin_pct": round(v / s * 100, 2), "note": n} for m, v, s, n in rows])


# ----------------------------------------------------------------------
# 3. Volume and tariff sensitivity
# ----------------------------------------------------------------------
def parameters(inputs: dict, drivers: pd.DataFrame) -> dict:
    """Numbers derived from published figures that drive the sensitivity grid."""
    amount = drivers.set_index("item")
    retail_fy2025 = units(inputs["volumes"], "retail_sales", "FY2025", "Total")
    original, revised = float(inputs["targets"]["volume_outlook_original_fy2026"]), \
        float(inputs["targets"]["volume_outlook_revised_fy2026"])
    sales_perf = float(amount.loc["Sales performance", "fy2026_outlook_bn"])
    contribution = sales_perf / (original - retail_fy2025)          # JPY million per extra car
    tariff_2025 = -float(amount.loc["US tariffs", "fy2025_actual_bn"])
    tariff_2026 = tariff_2025 - float(amount.loc["US tariffs", "fy2026_outlook_bn"])
    outlook = float(inputs["group"].loc["FY2026F", "operating_profit_bn"])
    return {"retail_fy2025": retail_fy2025, "volume_original": original, "volume_revised": revised,
            "sales_performance_bn": sales_perf, "contribution_per_car": contribution,
            "volume_cut_impact_bn": (revised - original) * contribution,
            "tariff_burden_fy2025": tariff_2025, "tariff_burden_fy2026": tariff_2026,
            "outlook_bn": outlook,
            "usd_jpy_assumption": float(inputs["group"].loc["FY2026F", "usd_jpy_avg"])}


def breakeven_table(p: dict) -> pd.DataFrame:
    rows = []
    for case, multiple in ASSUMPTIONS["contribution_cases"].items():
        c = p["contribution_per_car"] * multiple
        volume = p["volume_revised"] - p["outlook_bn"] / c
        rows.append({"case": case, "profit_per_extra_car_million_yen": round(c, 3),
                     "break_even_volume_thousand": round(volume, 0),
                     "headroom_thousand": round(p["volume_revised"] - volume, 0),
                     "headroom_pct": round((p["volume_revised"] - volume) / p["volume_revised"] * 100, 1)})
    return pd.DataFrame(rows)


def grid_table(p: dict) -> pd.DataFrame:
    """Operating profit for each volume and tariff-burden change, anchored on Nissan's current outlook."""
    rows = []
    for tariff in ASSUMPTIONS["tariff_changes_pct"]:
        for volume in ASSUMPTIONS["volumes"]:
            profit = (p["outlook_bn"] + (volume - p["volume_revised"]) * p["contribution_per_car"]
                      - tariff / 100 * p["tariff_burden_fy2026"])
            rows.append({"tariff_burden_change_pct": tariff, "retail_volume_thousand": volume,
                         "operating_profit_bn": round(profit, 1)})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 4. Plant utilisation outside China (rough estimate)
# ----------------------------------------------------------------------
def capacity_table(inputs: dict) -> pd.DataFrame:
    volumes, targets = inputs["volumes"], inputs["targets"]
    production = {"FY2025": units(volumes, "production", "FY2025", "Total"),
                  "FY2026F": units(volumes, "production", "FY2026F", "Total")}
    china_retail = {"FY2025": units(volumes, "retail_sales", "FY2025", "China"),
                    "FY2026F": units(volumes, "retail_sales", "FY2026F", "China")}
    rows = []
    for period in production:
        for gap in ASSUMPTIONS["china_production_gap"]:
            china_production = china_retail[period] + gap
            outside = production[period] - china_production
            for label, capacity in [("capacity before Re:Nissan", targets["capacity_before"]),
                                    ("capacity target", targets["capacity_target"])]:
                rows.append({"period": period, "china_production_assumed_thousand": china_production,
                             "production_outside_china_thousand": outside, "capacity_basis": label,
                             "capacity_thousand": capacity,
                             "utilisation_pct": round(outside / capacity * 100, 1)})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# Tables for the Excel scenario model (Step 8)
# ----------------------------------------------------------------------
def parameter_table(p: dict) -> pd.DataFrame:
    rows = [
        ("outlook_operating_profit_bn", p["outlook_bn"], "JPY bn", "Nissan", "FY2026 outlook (kept in August 2026)"),
        ("retail_volume_fy2025", p["retail_fy2025"], "thousand cars", "Nissan", "Actual FY2025 global retail"),
        ("retail_volume_outlook_original", p["volume_original"], "thousand cars", "Nissan", "May 2026 outlook"),
        ("retail_volume_outlook_revised", p["volume_revised"], "thousand cars", "Nissan", "Cut announced 3 Aug 2026"),
        ("sales_performance_outlook_bn", p["sales_performance_bn"], "JPY bn", "DERIVED", "Not stated by Nissan: closes the bridge"),
        ("profit_per_extra_car", round(p["contribution_per_car"], 4), "JPY million", "DERIVED",
         "Sales performance / extra cars in the original outlook (assumes all of it is volume)"),
        ("volume_cut_impact_bn", round(p["volume_cut_impact_bn"], 1), "JPY bn", "DERIVED",
         "Revised minus original volume, times profit per extra car"),
        ("tariff_burden_fy2025_bn", p["tariff_burden_fy2025"], "JPY bn", "Nissan", "Total tariff impact on FY2025 profit"),
        ("tariff_burden_fy2026_bn", p["tariff_burden_fy2026"], "JPY bn", "DERIVED", "FY2025 burden minus the 30 bn improvement"),
        ("usd_jpy_assumption", p["usd_jpy_assumption"], "JPY per USD", "Nissan", "Outlook assumption"),
    ]
    return pd.DataFrame(rows, columns=["parameter", "value", "unit", "origin", "note"])


# ----------------------------------------------------------------------
# Charts
# ----------------------------------------------------------------------
def headline(fig, title: str, subtitle: str, top: float = 0.84) -> None:
    fig.subplots_adjust(top=top)
    fig.text(0.01, 0.975, title, fontsize=13, fontweight="bold", ha="left", va="top")
    fig.text(0.01, 0.925, subtitle, fontsize=9.5, color=COLORS["grey"], ha="left", va="top")


def chart_drivers(categories: pd.DataFrame, quality: pd.DataFrame, p: dict):
    fig, ax = plt.subplots(figsize=(11, 5.4))
    positions = np.arange(len(categories))[::-1]
    height = 0.36
    ax.barh(positions + height / 2, categories["fy2025_actual_bn"], height, color=COLORS["navy"],
            label="FY2025 actual (vs FY2024)")
    ax.barh(positions - height / 2, categories["fy2026_outlook_bn"], height, color=COLORS["amber"],
            label="FY2026 outlook (vs FY2025)")
    for column, offset in [("fy2025_actual_bn", height / 2), ("fy2026_outlook_bn", -height / 2)]:
        for position, value in zip(positions, categories[column]):
            ax.text(value + (6 if value >= 0 else -6), position + offset, f"{value:+,.0f}",
                    va="center", ha="left" if value >= 0 else "right", fontsize=9)
    ax.set_yticks(positions)
    ax.set_yticklabels(categories["category"])
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Effect on operating profit, JPY billions")
    ax.margins(x=0.15)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    ax.legend(loc="lower right")
    without = quality.set_index("measure").loc["FY2026 outlook without the derived sales performance", "operating_profit_bn"]
    headline(fig, f"Without the derived {p['sales_performance_bn']:+.0f} bn from sales, the FY2026 outlook would be {without:.0f} bn, not {p['outlook_bn']:.0f} bn",
             "Operating profit change by group of causes (Nissan's official bridges). The sales figure for FY2026 is derived by us.")
    return save_figure(fig, "fig12_outlook_drivers.png")


def chart_grid(grid: pd.DataFrame, p: dict):
    wide = grid.pivot(index="tariff_burden_change_pct", columns="retail_volume_thousand",
                      values="operating_profit_bn").sort_index(ascending=False)
    fig, ax = plt.subplots(figsize=(11, 5.0))
    limit = float(np.abs(wide.to_numpy()).max())
    image = ax.imshow(wide.to_numpy(), cmap="RdYlGn", norm=TwoSlopeNorm(vcenter=0, vmin=-limit, vmax=limit), aspect="auto")
    for row in range(wide.shape[0]):
        for column in range(wide.shape[1]):
            ax.text(column, row, f"{wide.iloc[row, column]:,.0f}", ha="center", va="center", fontsize=10)
    ax.set_xticks(range(wide.shape[1]))
    ax.set_xticklabels([f"{v:,.0f}" for v in wide.columns])
    ax.set_yticks(range(wide.shape[0]))
    ax.set_yticklabels([f"{t:+d}%" for t in wide.index])
    ax.set_xlabel("Global retail volume, thousand cars")
    ax.set_ylabel(f"Change in the tariff burden\n(base: {p['tariff_burden_fy2026']:.0f} bn)")
    base_column = list(wide.columns).index(p["volume_revised"])
    base_row = list(wide.index).index(0)
    ax.add_patch(Rectangle((base_column - 0.5, base_row - 0.5), 1, 1, fill=False, edgecolor="black", linewidth=2.5))
    ax.grid(False)
    for spine in ax.spines.values():
        spine.set_visible(False)
    headline(fig, f"Outlook sensitivity: each 100k cars is about {p['contribution_per_car'] * 100:.0f} bn; each 10% of the tariff burden about {p['tariff_burden_fy2026'] * 0.1:.0f} bn",
             "Operating profit in JPY bn, around Nissan's current outlook (black box). Illustrative: the profit per car is derived by us, not a Nissan figure.")
    return save_figure(fig, "fig13_volume_tariff_sensitivity.png")


# ----------------------------------------------------------------------
def main() -> int:
    apply_style()
    try:
        inputs = read_inputs()
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        return 1

    drivers = driver_table(inputs["bridge"])
    categories = category_table(drivers)
    quality = quality_table(inputs, drivers)
    p = parameters(inputs, drivers)
    breakeven, grid = breakeven_table(p), grid_table(p)
    capacity, parameter_rows = capacity_table(inputs), parameter_table(p)

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in [("driver_items", drivers), ("driver_categories", categories),
                        ("outlook_quality", quality), ("break_even_volume", breakeven),
                        ("volume_tariff_grid", grid), ("capacity_utilisation", capacity),
                        ("scenario_parameters", parameter_rows)]:
        table.to_csv(TABLES_DIR / f"{name}.csv", index=False)
    charts = [chart_drivers(categories, quality, p), chart_grid(grid, p)]

    print("=" * 78)
    print("NISSAN TURNAROUND 2027 - PROFIT DRIVERS AND SENSITIVITIES")
    print("=" * 78)
    print("\n1. Drivers grouped (JPY bn):")
    print(categories.to_string(index=False))
    print("\n2. Quality of the outlook:")
    print(quality[["measure", "operating_profit_bn", "operating_margin_pct"]].to_string(index=False))
    print(f"\n3. Derived profit per extra car: JPY {p['contribution_per_car']:.3f} million "
          f"({p['sales_performance_bn']:.0f} bn / {p['volume_original'] - p['retail_fy2025']:.0f}k extra cars)")
    print(f"   The cut in the volume outlook ({p['volume_original']:.0f}k to {p['volume_revised']:.0f}k) is worth "
          f"{p['volume_cut_impact_bn']:+.1f} bn at that rate; Nissan kept its {p['outlook_bn']:.0f} bn outlook.")
    print(breakeven.to_string(index=False))
    print("\n4. Plant utilisation outside China (rough estimate, FY2026 outlook):")
    print(capacity[capacity["period"] == "FY2026F"][
        ["china_production_assumed_thousand", "capacity_basis", "utilisation_pct"]].to_string(index=False))
    print("\nSaved 7 tables in reports/tables/ and: " + ", ".join(path.name for path in charts))
    return 0


if __name__ == "__main__":
    sys.exit(main())