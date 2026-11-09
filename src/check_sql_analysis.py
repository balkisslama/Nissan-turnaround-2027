"""
check_sql_analysis.py
=====================
Purpose : Prove that the 17 SQL analysis queries give the RIGHT answers.

          For every query, the same answer is calculated a SECOND time,
          independently, with pandas straight from the raw CSV files (not from
          the database). The two answers must agree to within rounding.
          If the SQL had a mistake (a wrong join, a wrong formula), the two
          methods would disagree.

Usage   : python src/check_sql_analysis.py   (after python src/run_etl.py)

Exit code: 0 if every check passes, 1 otherwise.
"""

import sys

import pandas as pd

from db_utils import RAW_DIR, connect
from run_sql_analysis import load_queries, run_query

results = {"passed": 0, "failed": 0}


def check(ok: bool, message: str) -> None:
    """Print one PASS/FAIL line and update the counters."""
    print(f"[{'PASS' if ok else 'FAIL'}] {message}")
    results["passed" if ok else "failed"] += 1


def same(actual, expected, tolerance: float) -> bool:
    """Two numbers agree if they differ by less than the tolerance; two blanks agree."""
    if pd.isna(actual) and pd.isna(expected):
        return True
    if pd.isna(actual) or pd.isna(expected):
        return False
    return abs(float(actual) - float(expected)) <= tolerance


def compare(label: str, sql_table: pd.DataFrame, expected: pd.DataFrame, key: str,
            columns: list, tolerance: float = 0.051) -> None:
    """Compare the SQL answer with the independently calculated answer."""
    sql_table = sql_table.set_index(key)
    expected = expected.set_index(key)
    if set(sql_table.index) != set(expected.index):
        check(False, f"{label}: SQL has {len(sql_table)} rows, expected {len(expected)}")
        return
    wrong = [f"{row}/{column}" for row in expected.index for column in columns
             if not same(sql_table.loc[row, column], expected.loc[row, column], tolerance)]
    check(not wrong, f"{label}: {len(expected)} rows x {len(columns)} columns agree"
          + (f" - differences: {wrong[:3]}" if wrong else ""))


# ----------------------------------------------------------------------
# The raw files, read directly (no database involved)
# ----------------------------------------------------------------------
def read(name: str) -> pd.DataFrame:
    return pd.read_csv(RAW_DIR / name)


def check_profitability(answers: dict) -> None:
    print("\n--- 5A. PROFITABILITY (q01 to q05) ---")
    group = read("nissan_group_financials.csv")

    fy = group[group["period_type"].isin(["FY", "FY_FORECAST"])].sort_values("fiscal_year").copy()
    fy["operating_margin_pct"] = fy["operating_profit_bn"] / fy["net_sales_bn"] * 100
    fy["sales_growth_pct"] = (fy["net_sales_bn"] / fy["net_sales_bn"].shift(1) - 1) * 100
    fy["profit_growth_pct"] = (fy["operating_profit_bn"] / fy["operating_profit_bn"].shift(1) - 1) * 100
    compare("q01 profit trend", answers["q01"], fy, "period_id",
            ["operating_margin_pct", "sales_growth_pct", "profit_growth_pct"])
    published = answers["q01"].set_index("period_id").loc["FY2025", "profit_growth_pct"]
    check(abs(published - (-16.9)) <= 0.05,
          f"q01 FY2025 profit growth {published}% equals the -16.9% Nissan itself published")

    actual_years = group[group["period_type"] == "FY"].sort_values("fiscal_year").copy()
    actual_years["gap_bn"] = actual_years["net_income_bn"] - actual_years["operating_profit_bn"]
    compare("q02 operating vs net profit", answers["q02"], actual_years, "period_id", ["gap_bn"])

    cash = actual_years[actual_years["cfo_bn"].notna()].copy()
    cash["simple_free_cash_flow_bn"] = cash["cfo_bn"] + cash["cfi_bn"]
    cash["cash_change_bn"] = cash["cash_end_bn"].diff()
    compare("q03 cash flow", answers["q03"], cash, "period_id",
            ["simple_free_cash_flow_bn", "cash_change_bn"])

    balance = actual_years[actual_years["total_assets_bn"].notna()].copy()
    balance["change_in_points"] = balance["equity_ratio_pct"].diff()
    compare("q04 balance sheet", answers["q04"], balance, "period_id",
            ["equity_ratio_pct", "change_in_points"])

    invest = group[group["rnd_bn"].notna()].copy()
    invest["rnd_pct_of_sales"] = invest["rnd_bn"] / invest["net_sales_bn"] * 100
    invest["capex_pct_of_sales"] = invest["capex_bn"] / invest["net_sales_bn"] * 100
    invest["capex_to_depreciation"] = invest["capex_bn"] / invest["depreciation_bn"]
    compare("q05 investment intensity (percentages)", answers["q05"], invest, "period_id",
            ["rnd_pct_of_sales", "capex_pct_of_sales"])
    compare("q05 investment intensity (ratio)", answers["q05"], invest, "period_id",
            ["capex_to_depreciation"], tolerance=0.0051)


def check_regions(answers: dict) -> None:
    print("\n--- 5B. REGIONS (q06 to q08) ---")
    regional = read("nissan_regional_results.csv")
    real = regional[regional["region"] != "Eliminations"].copy()

    segment = real.copy()
    segment["key"] = segment["period_id"] + "|" + segment["region"]
    segment["segment_margin_pct"] = segment["operating_profit_bn"] / segment["net_sales_bn"] * 100
    sql_segment = answers["q06"].copy()
    sql_segment["key"] = sql_segment["period_id"] + "|" + sql_segment["region"]
    compare("q06 region profit", sql_segment, segment, "key", ["operating_profit_bn", "segment_margin_pct"])

    pivot = regional[regional["period_id"].isin(["Q1_FY2025", "Q1_FY2026"])].pivot(
        index="region", columns="period_id", values="operating_profit_bn")
    pivot["change_bn"] = pivot["Q1_FY2026"] - pivot["Q1_FY2025"]
    pivot["share_of_group_change_pct"] = pivot["change_bn"] / pivot["change_bn"].sum() * 100
    pivot = pivot.reset_index()
    compare("q07 Q1 profit swing", answers["q07"], pivot, "region",
            ["change_bn", "share_of_group_change_pct"])

    losses = real[real["operating_profit_bn"] < 0]
    expected = losses.groupby("period_id").agg(
        loss_making_regions=("region", "count"),
        combined_loss_bn=("operating_profit_bn", "sum")).reset_index()
    compare("q08 loss-making regions", answers["q08"], expected, "period_id",
            ["loss_making_regions", "combined_loss_bn"])
    names_ok = all(
        set(row["which_regions"].split(", ")) == set(losses[losses["period_id"] == row["period_id"]]["region"])
        for _, row in answers["q08"].iterrows())
    check(names_ok, "q08 the names of the loss-making regions agree")


def check_volumes(answers: dict) -> None:
    print("\n--- 5C. VOLUMES (q09 to q12) ---")
    volumes = read("nissan_volumes.csv")
    retail = volumes[volumes["metric"] == "retail_sales"]

    q1 = retail[retail["period_id"].isin(["Q1_FY2025", "Q1_FY2026"])].pivot(
        index="market", columns="period_id", values="units_thousand").reset_index()
    q1["change_thousand"] = q1["Q1_FY2026"] - q1["Q1_FY2025"]
    q1["change_pct"] = (q1["Q1_FY2026"] / q1["Q1_FY2025"] - 1) * 100
    compare("q09 Q1 retail change", answers["q09"], q1, "market", ["change_thousand", "change_pct"])

    fy25 = retail[retail["period_id"] == "FY2025"]
    total = float(fy25[fy25["market_level"] == "total"]["units_thousand"].iloc[0])
    mix = fy25[fy25["market_level"].isin(["region", "country"])].copy()
    mix["share_of_global_pct"] = mix["units_thousand"] / total * 100
    compare("q10 retail mix", answers["q10"], mix, "market", ["units_thousand", "share_of_global_pct"])

    def units(period, market):
        row = retail[(retail["period_id"] == period) & (retail["market"] == market)]
        return float(row["units_thousand"].iloc[0])

    rows = []
    for market in ["Japan", "North America", "Europe", "China", "Total"]:
        rows.append((market, units("FY2025", market), units("FY2026F", market)))
    actual_rest = units("FY2025", "Asia") + units("FY2025", "Others") - units("FY2025", "China")
    rows.append(("Rest of world (Asia ex-China + Others)", actual_rest,
                 units("FY2026F", "Others incl. Asia ex-China")))
    forecast = pd.DataFrame(rows, columns=["market", "fy2025_actual", "fy2026_forecast"])
    forecast["change_thousand"] = forecast["fy2026_forecast"] - forecast["fy2025_actual"]
    forecast["change_pct"] = (forecast["fy2026_forecast"] / forecast["fy2025_actual"] - 1) * 100
    compare("q11 forecast vs actual", answers["q11"], forecast, "market",
            ["fy2025_actual", "fy2026_forecast", "change_thousand", "change_pct"])

    group = read("nissan_group_financials.csv")
    wholesale = volumes[(volumes["metric"] == "wholesale") & (volumes["market_level"] == "total")]
    merged = group.merge(wholesale[["period_id", "units_thousand"]], on="period_id")
    merged["revenue_per_vehicle_million_yen"] = merged["net_sales_bn"] / merged["units_thousand"]
    compare("q12 revenue per vehicle", answers["q12"], merged, "period_id",
            ["revenue_per_vehicle_million_yen"], tolerance=0.0051)


def check_restructuring(answers: dict) -> None:
    print("\n--- 5D. RESTRUCTURING (q13 to q15) ---")
    t = read("nissan_restructuring_targets.csv").set_index("metric_id")["value"]

    def pct(after, before):
        return (after / before - 1) * 100

    plan = pd.DataFrame({
        "step": [1, 2, 3, 4],
        "before_value": [t["plants_before"], t["capacity_before"], t["models_before"],
                         t["volume_outlook_original_fy2026"]],
        "after_value": [t["plants_target"], t["capacity_target"], t["models_target"],
                        t["volume_outlook_revised_fy2026"]],
    })
    plan["change"] = plan["after_value"] - plan["before_value"]
    plan["change_pct"] = pct(plan["after_value"], plan["before_value"])
    compare("q13 restructuring plan", answers["q13"], plan, "step",
            ["before_value", "after_value", "change", "change_pct"])

    savings = t["fixed_cost_savings_fy2025"] + t["variable_cost_savings_fy2025"]
    jobs = t["employees_fy2024"] - t["employees_fy2025"]
    progress = pd.DataFrame({
        "item": ["Cost savings vs FY2024 (JPY bn)", "Workforce reduction (employees)"],
        "target": [t["cost_savings_target"], t["workforce_reduction_target"]],
        "achieved": [savings, jobs],
        "progress_pct": [savings / t["cost_savings_target"] * 100,
                         jobs / t["workforce_reduction_target"] * 100],
    })
    compare("q14 progress so far", answers["q14"], progress, "item",
            ["target", "achieved", "progress_pct"])

    group = read("nissan_group_financials.csv").set_index("period_id")
    op24, op25 = group.loc["FY2024", "operating_profit_bn"], group.loc["FY2025", "operating_profit_bn"]
    bridge = pd.DataFrame({"step": [1, 2, 3, 4],
                           "amount_bn": [op24, savings, op25 - op24 - savings, op25]})
    compare("q15 profit bridge", answers["q15"], bridge, "step", ["amount_bn"])
    check(abs(answers["q15"]["amount_bn"].iloc[:3].sum() - op25) <= 0.051,
          "q15 the bridge adds up: profit FY2024 + savings + other effects = profit FY2025")


def check_market(answers: dict) -> None:
    print("\n--- 5E. MARKET CONTEXT (q16 to q17) ---")
    group = read("nissan_group_financials.csv")
    nissan_rate = group[group["period_type"] == "FY"].set_index("fiscal_year")["usd_jpy_avg"]

    fx = read("usd_jpy_daily.csv")
    fx = fx[fx["usd_jpy"] > 0].copy()
    fx["date"] = pd.to_datetime(fx["date"].astype(str).str[:10])
    fx = fx.drop_duplicates(subset="date", keep="last")
    fx["fy"] = fx["date"].dt.year - (fx["date"].dt.month < 4).astype(int)
    fx = fx[fx["fy"] >= 2018]
    expected = fx.groupby("fy").agg(market_avg_usd_jpy=("usd_jpy", "mean"),
                                    days_in_data=("usd_jpy", "count")).reset_index()
    expected["fiscal_year"] = "FY" + expected["fy"].astype(str)
    expected["nissan_assumed_usd_jpy"] = expected["fy"].map(nissan_rate)
    expected["difference"] = expected["market_avg_usd_jpy"] - expected["nissan_assumed_usd_jpy"]
    compare("q16 yen vs Nissan assumption", answers["q16"], expected, "fiscal_year",
            ["market_avg_usd_jpy", "nissan_assumed_usd_jpy", "difference", "days_in_data"])

    stock = read("stock_prices_daily.csv")
    stock = stock[(stock["close_jpy"] > 0) & (stock["volume"] > 0)].copy()
    stock["date"] = pd.to_datetime(stock["date"].astype(str).str[:10])
    stock = stock.drop_duplicates(subset=["date", "ticker"], keep="last").sort_values("date")
    stock["fy"] = stock["date"].dt.year - (stock["date"].dt.month < 4).astype(int)
    stock = stock[stock["fy"] >= 2018]
    per_company = stock.groupby(["ticker", "fy"]).agg(
        first_close=("close_jpy", "first"), last_close=("close_jpy", "last"),
        trading_days=("close_jpy", "count")).reset_index()
    per_company["return_pct"] = (per_company["last_close"] / per_company["first_close"] - 1) * 100
    nissan = per_company[per_company["ticker"] == "7201.T"].set_index("fy")
    rivals = per_company[per_company["ticker"] != "7201.T"].groupby("fy")["return_pct"].mean()
    expected = pd.DataFrame({
        "fiscal_year": "FY" + nissan.index.astype(str),
        "nissan_return_pct": nissan["return_pct"].to_numpy(),
        "rivals_avg_return_pct": rivals.reindex(nissan.index).to_numpy(),
        "trading_days": per_company.groupby("fy")["trading_days"].max().reindex(nissan.index).to_numpy(),
    })
    expected["nissan_minus_rivals_pts"] = expected["nissan_return_pct"] - expected["rivals_avg_return_pct"]
    compare("q17 share price by fiscal year", answers["q17"], expected, "fiscal_year",
            ["nissan_return_pct", "rivals_avg_return_pct", "nissan_minus_rivals_pts", "trading_days"])


def main() -> int:
    print("=" * 72)
    print("NISSAN TURNAROUND 2027 - CHECK THE SQL ANALYSIS")
    print("=" * 72)

    try:
        connection = connect()
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        return 1

    queries = load_queries()
    check(len(queries) == 17, f"{len(queries)} queries found in the sql folder (expected 17)")
    try:
        answers = {q["name"][:3]: run_query(connection, q) for q in queries}
        check_profitability(answers)
        check_regions(answers)
        check_volumes(answers)
        check_restructuring(answers)
        check_market(answers)
    except (KeyError, FileNotFoundError) as error:
        print(f"[STOP] Something is missing: {error}. Did you run python src/run_etl.py?")
        connection.close()
        return 1
    connection.close()

    print("\n" + "=" * 72)
    print(f"Checks passed: {results['passed']} | failed: {results['failed']}")
    if results["failed"]:
        print("RESULT: FAILED. Read the [FAIL] lines above.")
        return 1
    print("RESULT: ALL CHECKS PASSED. The SQL answers agree with an independent calculation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())