"""
ev_market_analysis.py
=====================
Purpose : Size the electric-car markets that matter to Nissan (China, Europe,
          the United States, Japan) from the Our World in Data / IEA numbers
          in the database, and draw one chart.

          "Electric car" here means battery-electric plus plug-in hybrid cars.
          Ordinary hybrids, including Nissan's e-POWER, are NOT counted, and
          the data has no total car sales, so we measure growth, not market share.

          Market names are matched in lower case against a list of aliases;
          markets not found in your data are reported and skipped.

Usage   : python src/ev_market_analysis.py            (analysis + chart)
          python src/ev_market_analysis.py --list     (print every name in the data)

Exit code: 0 if produced, 1 otherwise.
"""

import sys

import matplotlib.pyplot as plt
import pandas as pd

from chart_style import COLORS, apply_style, save_figure
from db_utils import PROJECT_ROOT, connect

TABLES_DIR = PROJECT_ROOT / "reports" / "tables"
START_YEAR = 2018

MARKET_ALIASES = {
    "China": ["china"],
    "Europe": ["europe"],
    "United States": ["united states", "usa", "us", "united states of america"],
    "Japan": ["japan"],
    "Germany": ["germany"],
    "France": ["france"],
    "United Kingdom": ["united kingdom", "uk"],
}
MAIN_MARKETS = ["China", "Europe", "United States", "Japan"]
EXTRA_MARKETS = ["Germany", "France", "United Kingdom"]     # charted only if "Europe" is missing
WORLD_ALIASES = ["world"]
LINE_COLORS = {"China": "#C0392B", "Europe": "#1F3A5F", "United States": "#2E8B57", "Japan": "#D98E04",
               "Germany": "#6C8EBF", "France": "#8AAE92", "United Kingdom": "#9B8AB4"}


def load_ev(connection) -> pd.DataFrame:
    return pd.read_sql("SELECT country, year, electric_car_sales FROM fact_ev_sales "
                       "WHERE year <= 2026", connection)


def find_names(entities) -> dict:
    """Map each market we want to the exact name used in the data (if present)."""
    lower = {name.lower(): name for name in entities}
    found = {}
    for market, aliases in MARKET_ALIASES.items():
        for alias in aliases:
            if alias in lower:
                found[market] = lower[alias]
                break
    return found


def yearly_table(ev: pd.DataFrame, found: dict) -> pd.DataFrame:
    """Long table: market, year, electric cars sold (millions) since START_YEAR."""
    rows = []
    for market, name in found.items():
        part = ev[(ev["country"] == name) & (ev["year"] >= START_YEAR)]
        for row in part.itertuples():
            rows.append({"market": market, "year": int(row.year),
                         "sales_million": round(row.electric_car_sales / 1e6, 4)})
    return pd.DataFrame(rows).sort_values(["market", "year"]).reset_index(drop=True)


def summary_table(ev: pd.DataFrame, yearly: pd.DataFrame) -> pd.DataFrame:
    """First year, latest year, growth multiple, compound annual growth, share of world."""
    lower = {name.lower(): name for name in ev["country"].unique()}
    world_name = next((lower[a] for a in WORLD_ALIASES if a in lower), None)
    rows = []
    for market, part in yearly.groupby("market"):
        part = part.sort_values("year")
        first, last = part.iloc[0], part.iloc[-1]
        years = int(last["year"] - first["year"])
        multiple = last["sales_million"] / first["sales_million"] if first["sales_million"] > 0 else None
        cagr = ((multiple ** (1 / years) - 1) * 100) if multiple and years > 0 else None
        share = None
        if world_name is not None:
            world = ev[(ev["country"] == world_name) & (ev["year"] == last["year"])]
            if len(world) and world["electric_car_sales"].iloc[0] > 0:
                share = last["sales_million"] * 1e6 / world["electric_car_sales"].iloc[0] * 100
        rows.append({"market": market, "first_year": int(first["year"]),
                     "first_sales_million": round(first["sales_million"], 3),
                     "latest_year": int(last["year"]), "latest_sales_million": round(last["sales_million"], 3),
                     "growth_multiple": None if multiple is None else round(multiple, 2),
                     "cagr_pct": None if cagr is None else round(cagr, 1),
                     "share_of_world_pct": None if share is None else round(share, 1)})
    order = {m: i for i, m in enumerate(MARKET_ALIASES)}
    return pd.DataFrame(rows).sort_values("market", key=lambda s: s.map(order)).reset_index(drop=True)


def chart_ev(yearly: pd.DataFrame, summary: pd.DataFrame, found: dict):
    shown = [m for m in MAIN_MARKETS if m in found]
    if "Europe" not in found:
        shown += [m for m in EXTRA_MARKETS if m in found]
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 5.2), gridspec_kw={"width_ratios": [1.5, 1]})
    for market in shown:
        part = yearly[yearly["market"] == market]
        left.plot(part["year"], part["sales_million"], marker="o", markersize=3.5, linewidth=2.2,
                  color=LINE_COLORS[market])
        left.text(part["year"].iloc[-1], part["sales_million"].iloc[-1], f"  {market}",
                  color=LINE_COLORS[market], va="center", fontsize=9, fontweight="bold")
    left.set_ylabel("Electric cars sold, millions")
    left.margins(x=0.32)
    left.grid(axis="x", visible=False)
    left.set_title("New electric cars sold per year", fontsize=11)

    table = summary[summary["market"].isin(shown)].sort_values("growth_multiple")
    right.barh(table["market"], table["growth_multiple"], color=[LINE_COLORS[m] for m in table["market"]], height=0.6)
    for position, row in enumerate(table.itertuples()):
        right.text(row.growth_multiple, position, f"  x{row.growth_multiple:.1f}", va="center", fontsize=9)
    right.set_xlabel("Sales now / sales in the first year shown")
    right.margins(x=0.2)
    right.grid(axis="y", visible=False)
    right.set_title("Growth multiple", fontsize=11)

    latest = summary[summary["market"].isin(shown)].sort_values("latest_sales_million", ascending=False).iloc[0]
    fig.subplots_adjust(top=0.80, wspace=0.45)
    fig.text(0.01, 0.975, f"{latest['market']} led electric-car sales in {latest['latest_year']}: "
             f"{latest['latest_sales_million']:.1f} million", fontsize=13, fontweight="bold", ha="left", va="top")
    fig.text(0.01, 0.925, "Battery-electric plus plug-in hybrid cars (ordinary hybrids such as Nissan's e-POWER are not counted).",
             fontsize=9.5, color=COLORS["grey"], ha="left", va="top")
    return save_figure(fig, "fig11_ev_markets.png")


def main() -> int:
    connection = connect()
    ev = load_ev(connection)
    connection.close()
    if "--list" in sys.argv:
        print(f"{ev['country'].nunique()} names in the data:")
        print(", ".join(sorted(ev["country"].unique())))
        return 0

    apply_style()
    found = find_names(ev["country"].unique())
    print("=" * 78)
    print("NISSAN TURNAROUND 2027 - ELECTRIC CAR MARKETS")
    print("=" * 78)
    for market in MARKET_ALIASES:
        print(f"[{'FOUND' if market in found else 'MISSING'}] {market}"
              + (f" (data name: {found[market]})" if market in found else ""))
    if not found:
        print("[STOP] None of the markets was found. Run with --list to see the names in your data.")
        return 1

    yearly = yearly_table(ev, found)
    summary = summary_table(ev, yearly)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    yearly.to_csv(TABLES_DIR / "ev_markets.csv", index=False)
    summary.to_csv(TABLES_DIR / "ev_summary.csv", index=False)
    path = chart_ev(yearly, summary, found)
    print()
    print(summary.to_string(index=False, na_rep=""))
    print(f"\nSaved: reports/tables/ev_markets.csv, ev_summary.csv; {path.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())