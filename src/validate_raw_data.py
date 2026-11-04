"""
validate_raw_data.py
====================
Purpose : Quality-check the hand-built Nissan raw data files in data/raw/
          BEFORE they are loaded into the database (Step 4).

          Checks performed
          ----------------
          1. Structure   - files exist, expected columns, expected row counts
          2. Integrity   - no duplicate keys, no missing source references
          3. Reconciling - regional figures add up to the group totals,
                           volumes add up to totals (within rounding)
          4. Plausibility- operating margins match what Nissan reported

          Think of it as a "unit test" for data: if a number was mistyped,
          one of these checks should catch it.

Usage   : python src/validate_raw_data.py   (from the project root)

Exit code: 0 if every check passes, 1 otherwise.
"""

import sys
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"

# file name -> (expected columns, expected number of rows)
EXPECTED_FILES = {
    "nissan_group_financials.csv": (
        ["period_id", "period_type", "fiscal_year", "period_start", "period_end",
         "is_forecast", "net_sales_bn", "operating_profit_bn", "ordinary_income_bn",
         "net_income_bn", "total_assets_bn", "net_assets_bn", "equity_ratio_pct",
         "cfo_bn", "cfi_bn", "cff_bn", "cash_end_bn", "capex_bn", "depreciation_bn",
         "rnd_bn", "usd_jpy_avg", "eur_jpy_avg", "source_ids"],
        8,
    ),
    "nissan_regional_results.csv": (
        ["period_id", "region", "net_sales_bn", "operating_profit_bn", "source_ids"],
        18,
    ),
    "nissan_volumes.csv": (
        ["period_id", "metric", "market", "market_level", "units_thousand",
         "note", "source_ids"],
        58,
    ),
    "nissan_restructuring_targets.csv": (
        ["metric_id", "description", "value", "unit", "as_of", "source_ids"],
        17,
    ),
}

# Tolerances: published figures are rounded, so sums can be slightly off.
TOLERANCE_BN = 0.5      # yen billions
TOLERANCE_UNITS = 2     # thousand units

# Counters for the final summary
results = {"passed": 0, "failed": 0}


def report(ok: bool, message: str) -> None:
    """Print one PASS/FAIL line and update the counters."""
    print(f"[{'PASS' if ok else 'FAIL'}] {message}")
    results["passed" if ok else "failed"] += 1


# ----------------------------------------------------------------------
# 1. Structure
# ----------------------------------------------------------------------
def load_files() -> dict:
    """Load every expected CSV; check columns and row counts."""
    print("\n--- 1. STRUCTURE ---")
    frames = {}
    for name, (columns, expected_rows) in EXPECTED_FILES.items():
        path = RAW_DIR / name
        if not path.exists():
            report(False, f"{name}: file not found in data/raw/")
            continue
        df = pd.read_csv(path)
        frames[name] = df
        report(list(df.columns) == columns, f"{name}: columns match the data dictionary")
        report(len(df) == expected_rows,
               f"{name}: {len(df)} rows (expected {expected_rows})")
    return frames


# ----------------------------------------------------------------------
# 2. Integrity
# ----------------------------------------------------------------------
def check_integrity(frames: dict) -> None:
    """No duplicate keys; every row cites at least one source."""
    print("\n--- 2. INTEGRITY ---")
    keys = {
        "nissan_group_financials.csv": ["period_id"],
        "nissan_regional_results.csv": ["period_id", "region"],
        "nissan_volumes.csv": ["period_id", "metric", "market"],
        "nissan_restructuring_targets.csv": ["metric_id"],
    }
    for name, key in keys.items():
        df = frames[name]
        duplicates = int(df.duplicated(subset=key).sum())
        report(duplicates == 0, f"{name}: no duplicate rows on key {key}")
        missing_source = int(df["source_ids"].isna().sum())
        report(missing_source == 0, f"{name}: every row has a source_ids value")


# ----------------------------------------------------------------------
# 3. Reconciliation
# ----------------------------------------------------------------------
def check_regional_totals(frames: dict) -> None:
    """Regions (incl. eliminations) must add up to the group totals."""
    print("\n--- 3. RECONCILIATION ---")
    group = frames["nissan_group_financials.csv"].set_index("period_id")
    regional = frames["nissan_regional_results.csv"]

    for period in regional["period_id"].unique():
        subset = regional[regional["period_id"] == period]
        for column, label in [("net_sales_bn", "net sales"),
                              ("operating_profit_bn", "operating profit")]:
            regional_sum = subset[column].sum()
            group_value = group.loc[period, column]
            gap = abs(regional_sum - group_value)
            report(gap <= TOLERANCE_BN,
                   f"{period}: regional {label} sum = {regional_sum:.1f} "
                   f"vs group {group_value:.1f} (gap {gap:.1f})")


def check_volume_totals(frames: dict) -> None:
    """Regional volumes must add up to the stated totals (within rounding)."""
    volumes = frames["nissan_volumes.csv"]
    for metric in ["retail_sales", "production", "wholesale"]:
        for period in ["Q1_FY2025", "Q1_FY2026", "FY2025"]:
            subset = volumes[(volumes["metric"] == metric)
                             & (volumes["period_id"] == period)]
            total = subset.loc[subset["market_level"] == "total", "units_thousand"].iloc[0]
            parts = subset.loc[subset["market_level"].isin(["region", "segment"]),
                               "units_thousand"].sum()
            gap = abs(parts - total)
            report(gap <= TOLERANCE_UNITS,
                   f"{period} {metric}: parts sum = {parts} vs total {total} (gap {gap})")


# ----------------------------------------------------------------------
# 4. Plausibility
# ----------------------------------------------------------------------
def check_margins(frames: dict) -> None:
    """Computed operating margins must match Nissan's published margins."""
    print("\n--- 4. PLAUSIBILITY ---")
    group = frames["nissan_group_financials.csv"].set_index("period_id")
    group["op_margin_pct"] = group["operating_profit_bn"] / group["net_sales_bn"] * 100

    published = {"FY2021": 2.9, "FY2022": 3.6, "FY2023": 4.5,
                 "FY2025": 0.5, "Q1_FY2026": 2.6}
    for period, expected in published.items():
        actual = round(group.loc[period, "op_margin_pct"], 1)
        report(abs(actual - expected) <= 0.05,
               f"{period}: operating margin {actual}% (published {expected}%)")

    # Net sales fell 4.9% in FY2025 according to Nissan.
    change = (group.loc["FY2025", "net_sales_bn"] / group.loc["FY2024", "net_sales_bn"] - 1) * 100
    report(abs(change - (-4.9)) <= 0.1,
           f"FY2025 net sales change {change:.1f}% (published -4.9%)")


def show_first_look(frames: dict) -> None:
    """Print the operating margin by period: our first real insight."""
    group = frames["nissan_group_financials.csv"].copy()
    group["op_margin_pct"] = (group["operating_profit_bn"] / group["net_sales_bn"] * 100).round(1)
    print("\n--- FIRST LOOK: OPERATING MARGIN BY PERIOD ---")
    print(group[["period_id", "net_sales_bn", "operating_profit_bn", "op_margin_pct"]]
          .to_string(index=False))


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main() -> int:
    print("=" * 60)
    print("NISSAN RAW DATA VALIDATION")
    print(f"Reading from: {RAW_DIR}")
    print("=" * 60)

    frames = load_files()
    if len(frames) != len(EXPECTED_FILES):
        print("\nRESULT: FAILED -> some files are missing. Fix them and rerun.")
        return 1

    check_integrity(frames)
    check_regional_totals(frames)
    check_volume_totals(frames)
    check_margins(frames)
    show_first_look(frames)

    print("\n" + "=" * 60)
    print(f"Checks passed: {results['passed']} | failed: {results['failed']}")
    if results["failed"]:
        print("RESULT: FAILED. Read the [FAIL] lines above, fix the CSV, rerun.")
        return 1
    print("RESULT: ALL CHECKS PASSED. Raw Nissan data is consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())