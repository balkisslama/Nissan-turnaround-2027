"""
validate_bridge_data.py
=======================
Purpose : Quality-check data/raw/nissan_profit_bridge.csv, Nissan's own
          breakdown ("bridge") of why operating profit changed.

          A bridge is only trustworthy if it CLOSES: the starting profit plus
          all the changes must equal the ending profit. This script checks that,
          and also ties the bridge to the group financials file we already
          verified in Step 2 (different file, same numbers).

Usage   : python src/validate_bridge_data.py   (from the project root)

Exit code: 0 if every check passes, 1 otherwise.
"""

import sys

import pandas as pd

from db_utils import RAW_DIR

EXPECTED_COLUMNS = ["bridge_id", "step", "item", "item_type", "amount_bn",
                    "is_derived", "note", "source_ids"]
KNOWN_SOURCES = {"SCRIPT-Q4FY2025"}
TOLERANCE = 0.051     # published figures are rounded

results = {"passed": 0, "failed": 0}


def check(ok: bool, message: str) -> None:
    """Print one PASS/FAIL line and update the counters."""
    print(f"[{'PASS' if ok else 'FAIL'}] {message}")
    results["passed" if ok else "failed"] += 1


def main() -> int:
    print("=" * 66)
    print("NISSAN TURNAROUND 2027 - VALIDATE THE PROFIT BRIDGE DATA")
    print("=" * 66)

    path = RAW_DIR / "nissan_profit_bridge.csv"
    if not path.exists():
        print("[STOP] data/raw/nissan_profit_bridge.csv not found. Did you save it?")
        return 1
    bridge = pd.read_csv(path)
    group = pd.read_csv(RAW_DIR / "nissan_group_financials.csv").set_index("period_id")

    print("\n--- STRUCTURE ---")
    check(list(bridge.columns) == EXPECTED_COLUMNS, "columns match the data dictionary")
    check(len(bridge) == 21, f"{len(bridge)} rows (expected 21)")
    check(set(bridge["bridge_id"]) == {"FY2025_ACTUAL", "FY2026_OUTLOOK"},
          "two bridges: FY2025_ACTUAL and FY2026_OUTLOOK")
    check(not bridge.duplicated(subset=["bridge_id", "step"]).any(),
          "no duplicate steps inside a bridge")
    check(set(bridge["source_ids"]) <= KNOWN_SOURCES, "every row cites a known source")
    check(set(bridge["is_derived"]) <= {0, 1}, "is_derived is always 0 or 1")

    print("\n--- EACH BRIDGE MUST CLOSE ---")
    expected_ties = {
        "FY2025_ACTUAL": (group.loc["FY2024", "operating_profit_bn"],
                          group.loc["FY2025", "operating_profit_bn"]),
        "FY2026_OUTLOOK": (group.loc["FY2025", "operating_profit_bn"],
                           group.loc["FY2026F", "operating_profit_bn"]),
    }
    for bridge_id, part in bridge.groupby("bridge_id"):
        part = part.sort_values("step")
        starts = part[part["item_type"] == "start"]
        ends = part[part["item_type"] == "end"]
        changes = part[part["item_type"] == "change"]
        check(len(starts) == 1 and len(ends) == 1 and part["step"].tolist() == list(range(len(part))),
              f"{bridge_id}: one start, one end, steps numbered 0 to {len(part) - 1}")
        start, end = float(starts["amount_bn"].iloc[0]), float(ends["amount_bn"].iloc[0])
        total = float(changes["amount_bn"].sum())
        check(abs(start + total - end) <= TOLERANCE,
              f"{bridge_id}: {start} + {total:.1f} = {start + total:.1f} equals the end {end}")
        wanted_start, wanted_end = expected_ties[bridge_id]
        check(abs(start - wanted_start) <= TOLERANCE and abs(end - wanted_end) <= TOLERANCE,
              f"{bridge_id}: start {start} and end {end} match nissan_group_financials.csv")

    print("\n--- DERIVED VALUES ARE FLAGGED ---")
    derived = bridge[bridge["is_derived"] == 1]
    check(sorted(derived["item"]) == ["Rounding difference", "Sales performance"],
          "only 'Rounding difference' and 'Sales performance' are derived: "
          + ", ".join(f"{row.bridge_id}/{row.item}" for row in derived.itertuples()))
    check(all(isinstance(note, str) and len(note) > 20 for note in derived["note"]),
          "every derived value carries an explanatory note")

    print("\n" + "=" * 66)
    print(f"Checks passed: {results['passed']} | failed: {results['failed']}")
    if results["failed"]:
        print("RESULT: FAILED. Read the [FAIL] lines above.")
        return 1
    print("RESULT: ALL CHECKS PASSED. The profit bridge data is consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())