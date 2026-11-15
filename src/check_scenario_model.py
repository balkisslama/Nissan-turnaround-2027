"""
check_scenario_model.py
=======================
Purpose : Prove that the Excel scenario model is built correctly and calculates
          correctly.

          PART 1 - structure (works on the file as built)
            * the five sheets exist; the Model sheet holds live formulas,
              not typed numbers; the Downside, Base and Upside columns use the
              same formula pattern; published inputs equal the verified
              pipeline tables; colours follow the convention; the dropdown exists

          PART 2 - values (needs the file to have been calculated by Excel)
            * Excel's results are compared with an independent Python
              calculation, the Base case must equal Nissan's outlook, the
              'Selected' column must follow the dropdown, Summary must equal
              Model, and the Sensitivity grid must equal the Python grid of
              Step 7. If the file has not been calculated yet, open it in Excel,
              press Ctrl+S, and run this script again.

Usage   : python src/build_scenario_model.py
          (open excel/nissan_scenario_model.xlsx in Excel, press Ctrl+S)
          python src/check_scenario_model.py

Exit code: 0 if nothing failed, 1 otherwise.
"""

import re
import sys

import pandas as pd
from openpyxl import load_workbook

from db_utils import PROJECT_ROOT, RAW_DIR

PATH = PROJECT_ROOT / "excel" / "nissan_scenario_model.xlsx"
TABLES_DIR = PROJECT_ROOT / "reports" / "tables"
SHEETS = ["Guide", "Inputs", "Model", "Summary", "Sensitivity"]
MODEL_ROWS = [6, 7, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 25, 26, 27]
BLUE = "0000FF"          # compared on the last 6 hex digits: Excel and openpyxl differ in the alpha prefix
YELLOW = "FFFF00"

results = {"passed": 0, "failed": 0, "waiting": 0}


def check(ok: bool, message: str) -> None:
    """Print one PASS/FAIL line and update the counters."""
    print(f"[{'PASS' if ok else 'FAIL'}] {message}")
    results["passed" if ok else "failed"] += 1


def wait(message: str) -> None:
    print(f"[WAIT] {message}")
    results["waiting"] += 1


def close(a, b, tolerance=0.0011) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) <= tolerance


def is_blue(cell) -> bool:
    return cell.font is not None and cell.font.color is not None and str(cell.font.color.rgb)[-6:] == BLUE


# ----------------------------------------------------------------------
# PART 1 - structure
# ----------------------------------------------------------------------
def check_structure(wb) -> None:
    print("\n--- PART 1: STRUCTURE (the workbook as built) ---")
    check(wb.sheetnames == SHEETS, f"sheets: {', '.join(wb.sheetnames)}")

    model, summary, inputs, sensitivity = wb["Model"], wb["Summary"], wb["Inputs"], wb["Sensitivity"]

    formulas = [c for row in model["C6:F27"] for c in row if isinstance(c.value, str) and c.value.startswith("=")]
    constants = [f"{sheet.title}!{c.coordinate}" for sheet in (model, summary) for row in sheet.iter_rows()
                 for c in row if isinstance(c.value, (int, float)) and not isinstance(c.value, bool)]
    check(len(formulas) >= 20 * 4 and not constants,
          f"Model and Summary hold {len(formulas)} formulas in the model area and no typed numbers"
          + (f" (typed numbers found: {constants[:4]})" if constants else ""))

    axis = {f"{chr(66 + i)}4" for i in range(7)} | {f"A{r}" for r in range(5, 10)}
    stray = [c.coordinate for row in sensitivity.iter_rows() for c in row
             if isinstance(c.value, (int, float)) and c.coordinate not in axis]
    check(not stray, "Sensitivity: the only typed numbers are the volume and tariff axis values")

    def shifted(formula, column):
        if not isinstance(formula, str):          # a typed number instead of a formula: leave it, it will not match
            return formula
        return re.sub(r"(?<![$A-Za-z])C(?=\d)", column, formula)

    inconsistent = [r for r in MODEL_ROWS
                    if not all(model[f"{c}{r}"].value == shifted(model[f"C{r}"].value, c) for c in "DE")]
    check(not inconsistent, "Downside, Base and Upside use the same formula pattern in every Model row"
          + (f" (rows differ: {inconsistent})" if inconsistent else ""))

    pipeline = pd.read_csv(TABLES_DIR / "scenario_parameters.csv").set_index("parameter")["value"]
    drivers = pd.read_csv(TABLES_DIR / "driver_items.csv").set_index("item")["fy2026_outlook_bn"]
    group = pd.read_csv(RAW_DIR / "nissan_group_financials.csv").set_index("period_id")
    expected = {
        "C6": group.loc["FY2025", "operating_profit_bn"], "C7": group.loc["FY2025", "net_sales_bn"],
        "C8": group.loc["FY2026F", "net_sales_bn"], "C9": pipeline["retail_volume_fy2025"],
        "C10": pipeline["retail_volume_outlook_original"], "C11": pipeline["retail_volume_outlook_revised"],
        "C12": pipeline["outlook_operating_profit_bn"], "C13": pipeline["usd_jpy_assumption"],
        "C14": pipeline["tariff_burden_fy2025_bn"], "C17": drivers["Foreign exchange"], "C18": drivers["Raw materials"],
        "C19": drivers["US tariffs"], "C20": drivers["Sales performance"], "C21": drivers["Inflation"],
        "C22": drivers["Monozukuri cost savings"], "C23": drivers["One-time items"], "C24": drivers["Other items"],
    }
    wrong = [ref for ref, value in expected.items() if not close(inputs[ref].value, value, 0.0001)]
    check(not wrong, f"{len(expected)} published and derived inputs equal the verified pipeline tables"
          + (f" (differ: {wrong})" if wrong else ""))

    blue_ok = all(is_blue(inputs[ref]) for ref in expected)
    lever_cells = [inputs[f"{c}{r}"] for r in range(35, 42) for c in "CDE"]
    yellow_ok = all(str(c.fill.fgColor.rgb)[-6:] == YELLOW for c in lever_cells)
    model_not_blue = not any(is_blue(c) for row in model["C6:F27"] for c in row if c.value is not None)
    check(blue_ok and yellow_ok and model_not_blue,
          "colour convention: inputs blue, levers yellow, Model formulas not blue")

    validation = inputs.data_validations.dataValidation
    check(any("C3" in str(v.sqref) and "Downside" in (v.formula1 or "") for v in validation),
          "the scenario dropdown (Downside, Base, Upside) exists on Inputs!C3")


# ----------------------------------------------------------------------
# PART 2 - values
# ----------------------------------------------------------------------
def mirror(values, column: str) -> dict:
    """The same model, calculated in plain Python from the Inputs values (not from Excel's formulas)."""
    inputs = values["Inputs"]

    def lever(row):
        return inputs[f"{column}{row}"].value        # rows: 35 volume, 36 tariff, 37 savings, 38 raw materials,
                                                     #       39 inflation, 40 offsets, 41 USD/JPY

    def number(ref):
        return inputs[ref].value

    tariff_2026 = number("C14") - number("C19")                    # FY2025 burden minus the improvement
    per_car = number("C20") / (number("C10") - number("C9"))       # profit per extra car
    gap = (number("C10") - number("C11")) * per_car                # gap created by the volume cut
    volume = lever(35)
    parts = {
        10: number("C17") + number("C31") * (lever(41) - number("C13")),
        11: number("C18") * lever(38),
        12: number("C14") - tariff_2026 * (1 + lever(36)),
        13: number("C20"),
        14: (volume - number("C10")) * per_car,
        15: lever(40) * gap,
        16: number("C21") * lever(39),
        17: number("C22") * lever(37),
        18: number("C23"),
        19: number("C24"),
    }
    total = sum(parts.values())
    profit = number("C6") + total
    sales = number("C8") * volume / number("C11")
    breakeven = volume - profit / per_car
    return {6: volume, 7: sales, 9: number("C6"), **parts, 20: total, 21: profit, 22: profit / sales,
            23: profit - number("C12"), 25: breakeven, 26: volume - breakeven, 27: (volume - breakeven) / volume}


def check_values(wb_values) -> None:
    print("\n--- PART 2: VALUES (Excel's results against an independent Python calculation) ---")
    model, summary, inputs, sensitivity = (wb_values[n] for n in ("Model", "Summary", "Inputs", "Sensitivity"))
    if model["D21"].value is None:
        wait("The workbook has no calculated values yet. Open excel/nissan_scenario_model.xlsx in Excel, "
             "press Ctrl+S to save, then run this script again.")
        return

    errors = [f"{ws.title}!{c.coordinate}" for ws in wb_values.worksheets for row in ws.iter_rows()
              for c in row if isinstance(c.value, str) and c.value.startswith("#")]
    check(not errors, "no Excel error values (#DIV/0!, #REF!, #NAME?...) anywhere" + (f": {errors[:3]}" if errors else ""))

    differences = []
    for column in "CDE":
        expected = mirror(wb_values, column)
        for row, value in expected.items():
            if not close(model[f"{column}{row}"].value, value, 0.0011 if row not in (7, 25, 26) else 0.011):
                differences.append(f"{column}{row}")
    check(not differences, "all 3 scenarios x 20 lines agree with the independent Python calculation"
          + (f" (differ: {differences[:4]})" if differences else ""))

    outlook = inputs["C12"].value
    check(close(model["D21"].value, outlook, 0.051) and model["D29"].value == "OK",
          f"the Base case equals Nissan's outlook: {model['D21'].value:,.1f} vs {outlook:,.1f}")
    check(close(inputs["C30"].value, 0, 0.051), "the bridge on Inputs closes (check cell = 0)")

    selected = model["F4"].value
    column = {"Downside": "C", "Base": "D", "Upside": "E"}.get(selected)
    check(column is not None and all(close(model[f"F{r}"].value, model[f"{column}{r}"].value, 0.0001) for r in MODEL_ROWS),
          f"the 'Selected' column follows the dropdown ({selected})")

    pairs = {5: 6, 6: 7, 7: 21, 8: 22, 9: 23, 10: 25, 11: 26}
    check(all(close(summary[f"{c}{s}"].value, model[f"{c}{m}"].value, 0.0001) for c in "CDEF" for s, m in pairs.items()),
          "Summary equals Model")
    bridge_ok = all(close(summary[f"{c}22"].value, model[f"{c}21"].value - model["D21"].value, 0.0011) for c in "CDE")
    check(bridge_ok, "Summary: the causes add up to the profit difference versus Base")

    grid = pd.read_csv(TABLES_DIR / "volume_tariff_grid.csv")
    matches = 0
    for row in range(5, 10):
        for offset in range(7):
            volume = sensitivity.cell(row=4, column=2 + offset).value
            tariff = round(sensitivity.cell(row=row, column=1).value * 100)
            python = grid[(grid["retail_volume_thousand"] == volume) & (grid["tariff_burden_change_pct"] == tariff)]
            matches += int(len(python) == 1 and close(sensitivity.cell(row=row, column=2 + offset).value,
                                                       python["operating_profit_bn"].iloc[0], 0.051))
    check(matches == 35, f"{matches} of 35 Sensitivity cells equal the Python grid of Step 7")


def main() -> int:
    print("=" * 72)
    print("NISSAN TURNAROUND 2027 - CHECK THE EXCEL SCENARIO MODEL")
    print("=" * 72)
    if not PATH.exists():
        print("[STOP] excel/nissan_scenario_model.xlsx not found. Run: python src/build_scenario_model.py")
        return 1
    try:
        check_structure(load_workbook(PATH))
        check_values(load_workbook(PATH, data_only=True))
    except FileNotFoundError as error:
        print(f"[STOP] {error}. Run python src/driver_analysis.py first.")
        return 1

    print("\n" + "=" * 72)
    print(f"Checks passed: {results['passed']} | failed: {results['failed']} | waiting: {results['waiting']}")
    if results["failed"]:
        print("RESULT: FAILED. Read the [FAIL] lines above.")
        return 1
    if results["waiting"]:
        print("RESULT: STRUCTURE OK. Value checks are waiting: open the file in Excel, press Ctrl+S, rerun.")
        return 0
    print("RESULT: ALL CHECKS PASSED. The Excel model is built and calculates correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())