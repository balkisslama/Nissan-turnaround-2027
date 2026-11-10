"""
make_charts.py
==============
Purpose : Draw the project's first eight charts and save them as PNG files in
          reports/figures/. The numbers come from the SQL answers saved in
          reports/tables/ (verified in Step 5), from the official profit
          bridge (data/raw/nissan_profit_bridge.csv) and from the group
          financials file. Each chart has two parts:

            data_...()  : prepares the numbers (no drawing)
            chart_...() : draws them

          Splitting the two lets the checker test the numbers separately.

Usage   : python src/make_charts.py   (after python src/run_sql_analysis.py)

Exit code: 0 if all charts were drawn, 1 otherwise.
"""

import sys
import textwrap

import matplotlib.pyplot as plt
import pandas as pd

from chart_style import COLORS, apply_style, save_figure
from db_utils import PROJECT_ROOT, RAW_DIR

TABLES_DIR = PROJECT_ROOT / "reports" / "tables"


# ----------------------------------------------------------------------
# Reading the numbers
# ----------------------------------------------------------------------
def read_table(name: str) -> pd.DataFrame:
    """Read one SQL answer saved by run_sql_analysis.py."""
    path = TABLES_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} not found in reports/tables. "
            "Create it first with: python src/run_sql_analysis.py")
    return pd.read_csv(path)


def wrap(label: str, width: int = 11) -> str:
    """Break a long label over several lines so it fits under its bar."""
    return textwrap.fill(str(label), width=width, break_long_words=False)


# ----------------------------------------------------------------------
# DATA: one function per chart (no drawing here)
# ----------------------------------------------------------------------
def data_sales_margin() -> pd.DataFrame:
    table = read_table("q01_profit_trend")
    table["sales_trillion"] = table["net_sales_bn"] / 1000
    return table


def data_profit_vs_net() -> pd.DataFrame:
    return read_table("q02_operating_vs_net_profit")


def data_cash_flow() -> pd.DataFrame:
    return read_table("q03_cash_flow")


def data_regional_fy2025() -> pd.DataFrame:
    table = read_table("q06_region_profit")
    table = table[table["period_id"] == "FY2025"]
    return table.sort_values("operating_profit_bn").reset_index(drop=True)


def data_q1_swing() -> dict:
    """Start, steps and end of the Q1 FY2025 -> Q1 FY2026 profit walk."""
    swing = read_table("q07_q1_profit_swing_by_region")
    regions = swing[swing["region"] != "Eliminations"].sort_values("change_bn", ascending=False)
    group = pd.read_csv(RAW_DIR / "nissan_group_financials.csv").set_index("period_id")
    start = float(group.loc["Q1_FY2025", "operating_profit_bn"])
    end = float(group.loc["Q1_FY2026", "operating_profit_bn"])
    steps = [(row.region, float(row.change_bn), False) for row in regions.itertuples()]
    # The published regional figures are rounded, so the last step absorbs the
    # eliminations line and the rounding, which makes the walk close exactly.
    steps.append(("Eliminations & rounding", round(end - start - sum(s[1] for s in steps), 1), False))
    return {"start_label": "Q1 FY2025", "start": start, "steps": steps,
            "end_label": "Q1 FY2026", "end": end}


def data_bridge(bridge_id: str) -> dict:
    """Start, steps and end of one of Nissan's official profit bridges."""
    bridge = pd.read_csv(RAW_DIR / "nissan_profit_bridge.csv")
    part = bridge[bridge["bridge_id"] == bridge_id].sort_values("step")
    start = part[part["item_type"] == "start"].iloc[0]
    end = part[part["item_type"] == "end"].iloc[0]
    steps = [(row.item, float(row.amount_bn), bool(row.is_derived))
             for row in part[part["item_type"] == "change"].itertuples()]
    return {"start_label": start["item"], "start": float(start["amount_bn"]), "steps": steps,
            "end_label": end["item"], "end": float(end["amount_bn"])}


def data_volume_changes() -> tuple:
    """Left panel: Q1 retail change by market. Right panel: FY2026 forecast vs FY2025."""
    q1 = read_table("q09_q1_retail_change_by_market")
    q1 = q1[q1["level"] != "total"].sort_values("change_pct").reset_index(drop=True)
    forecast = read_table("q11_forecast_vs_actual_volume")
    forecast = forecast[forecast["market"] != "Total"].sort_values("change_pct").reset_index(drop=True)
    return q1, forecast


# ----------------------------------------------------------------------
# DRAWING helpers
# ----------------------------------------------------------------------
def format_amount(amount: float) -> str:
    """Show small fractions with one decimal (+0.3) and everything else without (-5, +286)."""
    if abs(amount) < 10 and amount != int(amount):
        return f"{amount:+,.1f}"
    return f"{amount:+,.0f}"


def draw_waterfall(ax, data: dict) -> None:
    """Draw a waterfall: a start bar, floating bars for each change, an end bar."""
    labels = [data["start_label"]] + [s[0] for s in data["steps"]] + [data["end_label"]]
    levels = [data["start"]]
    for _, amount, _ in data["steps"]:
        levels.append(levels[-1] + amount)
    low, high = min(levels + [0, data["end"]]), max(levels + [0, data["end"]])
    span = high - low
    pad = span * 0.02

    ax.bar(0, data["start"], color=COLORS["navy"], width=0.62)
    ax.text(0, data["start"] + (pad if data["start"] >= 0 else -pad),
            f"{data['start']:,.1f}", ha="center",
            va="bottom" if data["start"] >= 0 else "top", fontweight="bold")

    for position, (_, amount, derived) in enumerate(data["steps"], start=1):
        before, after = levels[position - 1], levels[position]
        ax.bar(position, abs(amount), bottom=min(before, after), width=0.62,
               color=COLORS["green"] if amount >= 0 else COLORS["red"],
               hatch="///" if derived else None, edgecolor="white", linewidth=0)
        ax.plot([position - 1 + 0.31, position - 0.31], [before, before],
                color=COLORS["grey"], linewidth=0.8)
        ax.text(position, max(before, after) + pad if amount >= 0 else min(before, after) - pad,
                format_amount(amount), ha="center",
                va="bottom" if amount >= 0 else "top", fontsize=9,
                bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.6})

    last = len(data["steps"]) + 1
    ax.plot([last - 1 + 0.31, last - 0.31], [levels[-1], levels[-1]],
            color=COLORS["grey"], linewidth=0.8)
    ax.bar(last, data["end"], color=COLORS["navy"], width=0.62)
    ax.text(last, data["end"] + (pad if data["end"] >= 0 else -pad),
            f"{data['end']:,.1f}", ha="center",
            va="bottom" if data["end"] >= 0 else "top", fontweight="bold")

    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels([wrap(label) for label in labels], fontsize=8.5)
    ax.set_ylabel("JPY billions")
    ax.set_ylim(low - span * 0.12, high + span * 0.12)     # room for the value labels
    ax.grid(axis="x", visible=False)


def add_headline(fig, title: str, subtitle: str, top: float = 0.84) -> None:
    """Put a title and a smaller grey sub-title at the top-left of a figure."""
    fig.subplots_adjust(top=top)           # reserve a band at the top for the headline
    fig.text(0.01, 0.975, title, fontsize=13, fontweight="bold", ha="left", va="top")
    fig.text(0.01, 0.925, subtitle, fontsize=9.5, color=COLORS["grey"], ha="left", va="top")


# ----------------------------------------------------------------------
# DRAWING: one function per chart
# ----------------------------------------------------------------------
def chart_sales_margin():
    data = data_sales_margin()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    forecast = data["is_forecast"] == 1
    bars = ax.bar(data["period_id"], data["sales_trillion"],
                  color=[COLORS["light"] if f else COLORS["navy"] for f in forecast],
                  hatch=None, width=0.6)
    for bar, is_forecast in zip(bars, forecast):
        if is_forecast:
            bar.set_hatch("///")
            bar.set_edgecolor("white")
    for x, value in zip(data["period_id"], data["sales_trillion"]):
        ax.text(x, value + 0.15, f"{value:.1f}", ha="center", fontsize=9)
    ax.set_ylabel("Net sales, JPY trillions")
    ax.set_ylim(0, data["sales_trillion"].max() * 1.25)

    ax2 = ax.twinx()
    ax2.plot(data["period_id"], data["operating_margin_pct"], color=COLORS["red"],
             marker="o", linewidth=2.2)
    for x, value in zip(data["period_id"], data["operating_margin_pct"]):
        ax2.text(x, value + 0.25, f"{value:.1f}%", ha="center", color=COLORS["red"],
                 fontsize=9, fontweight="bold",
                 bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.2})
    ax2.set_ylabel("Operating margin, %", color=COLORS["red"])
    ax2.set_ylim(0, data["operating_margin_pct"].max() * 1.6)
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)

    add_headline(fig, "Sales held up, but the profit margin collapsed",
                 "Bars: net sales (hatched = FY2026 forecast). Line: operating margin. FY = April to March.")
    return save_figure(fig, "fig01_sales_and_margin.png")


def chart_profit_vs_net():
    data = data_profit_vs_net()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    positions = range(len(data))
    width = 0.38
    ax.bar([p - width / 2 for p in positions], data["operating_profit_bn"], width,
           color=COLORS["navy"], label="Operating profit")
    ax.bar([p + width / 2 for p in positions], data["net_income_bn"], width,
           color=COLORS["red"], label="Net income (final profit)")
    for p, (op, net) in enumerate(zip(data["operating_profit_bn"], data["net_income_bn"])):
        ax.text(p - width / 2, op + (15 if op >= 0 else -15), f"{op:,.0f}", ha="center",
                va="bottom" if op >= 0 else "top", fontsize=9)
        ax.text(p + width / 2, net + (15 if net >= 0 else -15), f"{net:,.0f}", ha="center",
                va="bottom" if net >= 0 else "top", fontsize=9)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(list(positions))
    ax.set_xticklabels(data["period_id"])
    ax.set_ylabel("JPY billions")
    ax.legend(loc="lower left")
    ax.margins(y=0.15)
    add_headline(fig, "In FY2024 and FY2025 the final result fell far below operating profit",
                 "Large costs outside normal operations (such as restructuring) sit between the two bars.")
    return save_figure(fig, "fig02_operating_vs_net_profit.png")


def chart_cash_flow():
    data = data_cash_flow()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    values = data["simple_free_cash_flow_bn"]
    ax.bar(data["period_id"], values, width=0.6,
           color=[COLORS["green"] if v >= 0 else COLORS["red"] for v in values])
    for x, value in zip(data["period_id"], values):
        ax.text(x, value + (15 if value >= 0 else -15), f"{value:,.0f}", ha="center",
                va="bottom" if value >= 0 else "top", fontweight="bold")
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("JPY billions")
    ax.margins(y=0.15)
    add_headline(fig, "After investing, Nissan's cash flow turned negative in FY2024 and FY2025",
                 "Simple free cash flow = cash from operations + cash from investing (consolidated, includes the car-loan arm).")
    return save_figure(fig, "fig03_cash_flow.png")


def chart_regional_fy2025():
    data = data_regional_fy2025()
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.barh(data["region"], data["operating_profit_bn"], height=0.6,
            color=[COLORS["green"] if v >= 0 else COLORS["red"] for v in data["operating_profit_bn"]])
    for position, row in enumerate(data.itertuples()):
        offset = 2 if row.operating_profit_bn >= 0 else -2
        ax.text(row.operating_profit_bn + offset, position,
                f"{row.operating_profit_bn:,.1f}  (margin {row.segment_margin_pct:.1f}%)",
                va="center", ha="left" if row.operating_profit_bn >= 0 else "right", fontsize=9)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Operating profit FY2025, JPY billions")
    ax.margins(x=0.28)
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", visible=True)
    add_headline(fig, "North America earns the profit; Europe loses it",
                 "FY2025 operating profit by region (segment margin = profit / the region's sales).")
    return save_figure(fig, "fig04_regional_profit_fy2025.png")


def chart_q1_swing():
    data = data_q1_swing()
    fig, ax = plt.subplots(figsize=(10, 5.5))
    draw_waterfall(ax, data)
    north_america = next(amount for label, amount, _ in data["steps"] if label == "North America")
    total_change = data["end"] - data["start"]
    add_headline(fig, f"North America delivered {north_america / total_change * 100:.0f}% of the Q1 profit improvement",
                 "Operating profit, Q1 FY2025 to Q1 FY2026, by region. Nissan notes one-time US tariff-related gains in Q1 FY2026.")
    return save_figure(fig, "fig05_q1_profit_swing.png")


def chart_bridge_fy2025():
    data = data_bridge("FY2025_ACTUAL")
    amounts = {label: amount for label, amount, _ in data["steps"]}
    fig, ax = plt.subplots(figsize=(11, 5.8))
    draw_waterfall(ax, data)
    tariff, savings = amounts["US tariffs"], amounts["Monozukuri cost savings"]
    before_tariffs = data["end"] - tariff
    add_headline(fig, f"FY2025: US tariffs ({tariff:+,.0f} bn) outweighed cost savings ({savings:+,.0f} bn)",
                 f"Nissan's own breakdown of the change in operating profit. All else equal, profit before tariffs would have been about JPY {before_tariffs:,.0f} bn.")
    return save_figure(fig, "fig06_profit_bridge_fy2025.png")


def chart_bridge_fy2026():
    data = data_bridge("FY2026_OUTLOOK")
    amounts = {label: amount for label, amount, _ in data["steps"]}
    fig, ax = plt.subplots(figsize=(11, 5.8))
    draw_waterfall(ax, data)
    add_headline(fig, f"The FY2026 outlook needs {amounts['Monozukuri cost savings']:+,.0f} bn of cost savings and {amounts['Sales performance']:+,.0f} bn from sales",
                 "Hatched bar = derived by us (Nissan did not state it). The outlook assumed 3.3 million units; the volume outlook was later cut to 3.15 million.")
    return save_figure(fig, "fig07_profit_bridge_fy2026_outlook.png")


def chart_volume_changes():
    q1, forecast = data_volume_changes()
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 5.2), sharex=True)
    for ax, table, label_column, title in [
            (left, q1, "market", "Q1 FY2026 retail sales vs a year earlier"),
            (right, forecast, "market", "FY2026 forecast vs FY2025 actual")]:
        colors = [COLORS["green"] if v >= 0 else COLORS["red"] for v in table["change_pct"]]
        if ax is left:
            colors = [COLORS["light"] if level == "country" else color
                      for level, color in zip(table["level"], colors)]
        ax.barh([wrap(m, 22) for m in table[label_column]], table["change_pct"], color=colors, height=0.6)
        for position, value in enumerate(table["change_pct"]):
            ax.text(value + (0.4 if value >= 0 else -0.4), position, f"{value:+.1f}%",
                    va="center", ha="left" if value >= 0 else "right", fontsize=9)
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set_title(title, fontsize=11)
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", visible=True)
        ax.set_xlabel("Change, %")
        ax.margins(x=0.2)
    add_headline(fig, "Europe is shrinking in Q1, yet the FY2026 outlook assumes it grows",
                 "Change in retail sales volume. Left: grey bars are single countries (USA, China) that are part of a region.",
                 top=0.80)
    return save_figure(fig, "fig08_volume_changes.png")


CHARTS = [chart_sales_margin, chart_profit_vs_net, chart_cash_flow, chart_regional_fy2025,
          chart_q1_swing, chart_bridge_fy2025, chart_bridge_fy2026, chart_volume_changes]


def main() -> int:
    apply_style()
    print("=" * 66)
    print("NISSAN TURNAROUND 2027 - DRAW THE CHARTS")
    print("=" * 66)
    failures = 0
    for draw in CHARTS:
        try:
            path = draw()
            print(f"[PASS] {path.name:<42}{path.stat().st_size / 1024:>6.0f} KB")
        except (FileNotFoundError, KeyError, ValueError, StopIteration) as error:
            failures += 1
            print(f"[FAIL] {draw.__name__}: {type(error).__name__}: {error}")
    print("=" * 66)
    if failures:
        print(f"RESULT: {failures} chart(s) failed. Read the [FAIL] lines above.")
        return 1
    print(f"RESULT: ALL {len(CHARTS)} CHARTS DRAWN. They are in reports/figures/")
    return 0


if __name__ == "__main__":
    sys.exit(main())