"""
market_statistics.py
====================
Purpose : Statistics on the share prices (and the yen) of Nissan and its four
          Japanese rivals, from the database, for every day since 1 April 2018
          (the start of Nissan's FY2018):

            total return        last price / first price - 1
            annual volatility   standard deviation of daily returns x sqrt(252)
            maximum drawdown    the deepest fall from a previous peak
            yen sensitivity     correlation and beta of daily share returns
                                with daily changes in USD/JPY

          Saves two tables in reports/tables/ and two charts in reports/figures/.
          Statistics show association, not cause.

Usage   : python src/market_statistics.py   (after python src/run_etl.py)

Exit code: 0 if everything was produced, 1 otherwise.
"""

import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from chart_style import COLORS, apply_style, save_figure
from db_utils import PROJECT_ROOT, connect

START_DATE = "2018-04-01"
TABLES_DIR = PROJECT_ROOT / "reports" / "tables"
RIVAL_COLORS = ["#6C8EBF", "#8AAE92", "#C9A66B", "#9B8AB4"]


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------
def load_prices(connection) -> pd.DataFrame:
    """One column per company, one row per trading day (adjusted closing price)."""
    table = pd.read_sql(
        "SELECT s.date_key AS date, c.company_name AS company, c.company_id, s.close_jpy AS price "
        "FROM fact_stock_prices AS s JOIN dim_company AS c ON c.company_id = s.company_id "
        "WHERE s.date_key >= ? ORDER BY s.date_key", connection, params=(START_DATE,))
    order = table.drop_duplicates("company").sort_values("company_id")["company"].tolist()
    wide = table.pivot(index="date", columns="company", values="price")[order]
    wide.index = pd.to_datetime(wide.index)
    return wide


def load_fx(connection) -> pd.Series:
    table = pd.read_sql("SELECT date_key AS date, usd_jpy FROM fact_usd_jpy WHERE date_key >= ? "
                        "ORDER BY date_key", connection, params=(START_DATE,))
    return pd.Series(table["usd_jpy"].to_numpy(), index=pd.to_datetime(table["date"]), name="usd_jpy")


# ----------------------------------------------------------------------
# Statistics
# ----------------------------------------------------------------------
def drawdown_series(prices: pd.Series) -> pd.Series:
    """Percentage fall from the highest price reached so far (0 at a new peak)."""
    prices = prices.dropna()
    return (prices / prices.cummax() - 1) * 100


def compute_statistics(prices: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for company in prices.columns:
        series = prices[company].dropna()
        returns = (series / series.shift(1) - 1).dropna()
        drawdown = drawdown_series(series)
        rows.append({
            "company": company,
            "first_day": series.index[0].date().isoformat(),
            "last_day": series.index[-1].date().isoformat(),
            "total_return_pct": round((series.iloc[-1] / series.iloc[0] - 1) * 100, 2),
            "annual_volatility_pct": round(returns.std(ddof=1) * np.sqrt(252) * 100, 2),
            "max_drawdown_pct": round(drawdown.min(), 2),
            "max_drawdown_date": drawdown.idxmin().date().isoformat(),
            "drawdown_now_pct": round(drawdown.iloc[-1], 2),
        })
    return pd.DataFrame(rows)


def compute_yen_sensitivity(prices: pd.DataFrame, fx: pd.Series) -> pd.DataFrame:
    rows = []
    for company in prices.columns:
        joined = pd.concat([prices[company], fx], axis=1, join="inner").dropna()
        changes = (joined / joined.shift(1) - 1).dropna()
        correlation = changes[company].corr(changes["usd_jpy"])
        beta = changes[company].cov(changes["usd_jpy"]) / changes["usd_jpy"].var()
        rows.append({"company": company, "days_used": len(changes),
                     "correlation": round(correlation, 3), "beta": round(beta, 3)})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# Charts
# ----------------------------------------------------------------------
def line_colors(columns) -> dict:
    colors, rival = {}, iter(RIVAL_COLORS)
    for company in columns:
        colors[company] = COLORS["red"] if company == "Nissan" else next(rival)
    return colors


def headline(fig, title: str, subtitle: str) -> None:
    fig.subplots_adjust(top=0.84)
    fig.text(0.01, 0.975, title, fontsize=13, fontweight="bold", ha="left", va="top")
    fig.text(0.01, 0.925, subtitle, fontsize=9.5, color=COLORS["grey"], ha="left", va="top")


def chart_prices(prices: pd.DataFrame, stats: pd.DataFrame):
    colors = line_colors(prices.columns)
    fig, ax = plt.subplots(figsize=(11, 5.6))
    for company in prices.columns:
        series = prices[company].dropna()
        rebased = series / series.iloc[0] * 100
        ax.plot(rebased.index, rebased, color=colors[company],
                linewidth=2.6 if company == "Nissan" else 1.3, zorder=3 if company == "Nissan" else 2)
        ax.text(rebased.index[-1], rebased.iloc[-1], f"  {company} {rebased.iloc[-1]:.0f}",
                color=colors[company], va="center", fontsize=9, fontweight="bold")
    ax.axhline(100, color="black", linewidth=0.8)
    ax.set_ylabel("Share price, 100 = April 2018")
    ax.margins(x=0.12)
    ax.grid(axis="x", visible=False)
    nissan = stats.set_index("company").loc["Nissan", "total_return_pct"]
    rivals = stats[stats["company"] != "Nissan"]["total_return_pct"].mean()
    headline(fig, f"Share prices since April 2018: Nissan {nissan:+.0f}%, rivals' average {rivals:+.0f}%",
             "Adjusted closing prices (dividends and splits included), rebased to 100.")
    return save_figure(fig, "fig09_share_price_rebased.png")


def chart_drawdowns(prices: pd.DataFrame, stats: pd.DataFrame):
    colors = line_colors(prices.columns)
    fig, ax = plt.subplots(figsize=(11, 5.2))
    for company in prices.columns:
        drawdown = drawdown_series(prices[company])
        ax.plot(drawdown.index, drawdown, color=colors[company],
                linewidth=2.2 if company == "Nissan" else 1.1, label=company,
                zorder=3 if company == "Nissan" else 2)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("Fall from the previous peak, %")
    ax.legend(loc="lower left", ncol=5)
    ax.grid(axis="x", visible=False)
    table = stats.set_index("company")
    rivals = stats[stats["company"] != "Nissan"]["max_drawdown_pct"].mean()
    headline(fig, f"Deepest fall from a peak: Nissan {table.loc['Nissan', 'max_drawdown_pct']:.0f}%, rivals' average {rivals:.0f}%",
             f"Nissan is now {table.loc['Nissan', 'drawdown_now_pct']:.0f}% below its own peak since April 2018.")
    return save_figure(fig, "fig10_drawdowns.png")


def main() -> int:
    apply_style()
    try:
        connection = connect()
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        return 1
    prices, fx = load_prices(connection), load_fx(connection)
    connection.close()
    if prices.empty or fx.empty:
        print("[STOP] No market data in the database. Run: python src/run_etl.py")
        return 1

    stats = compute_statistics(prices)
    yen = compute_yen_sensitivity(prices, fx)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    stats.to_csv(TABLES_DIR / "market_statistics.csv", index=False)
    yen.to_csv(TABLES_DIR / "yen_sensitivity.csv", index=False)
    figures = [chart_prices(prices, stats), chart_drawdowns(prices, stats)]

    print("=" * 78)
    print("NISSAN TURNAROUND 2027 - MARKET STATISTICS (daily data since April 2018)")
    print("=" * 78)
    print(stats.to_string(index=False))
    print("\nYen sensitivity: daily share return vs daily change in USD/JPY")
    print("(correlation: -1 to +1; beta: % move of the share per +1% move in USD/JPY)")
    print(yen.to_string(index=False))
    print("\nSaved: reports/tables/market_statistics.csv, yen_sensitivity.csv; "
          + ", ".join(path.name for path in figures))
    return 0


if __name__ == "__main__":
    sys.exit(main())