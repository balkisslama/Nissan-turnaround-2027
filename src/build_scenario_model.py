"""
build_scenario_model.py
=======================
Purpose : Build the Excel scenario model excel/nissan_scenario_model.xlsx.

          The numbers come from the verified pipeline (reports/tables/ and the raw
          CSV files), so nothing is typed by hand. The workbook uses LIVE
          FORMULAS: change a yellow cell and everything recalculates.

          Sheets
            Guide        how to use the model, colour legend, caveats
            Inputs       published / derived numbers (blue) and the scenario levers (yellow)
            Model        FY2026 operating profit for Downside, Base and Upside
            Summary      the three scenarios side by side, and a chart
            Sensitivity  profit for different volumes and tariff burdens

          Colour code: blue = typed input, black = formula, green = link to another
          sheet, yellow fill = a lever you are meant to change.

Usage   : python src/driver_analysis.py        (creates the input tables)
          python src/build_scenario_model.py

Exit code: 0 if the workbook was written, 1 otherwise.
"""

import re
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.properties import PageSetupProperties

from db_utils import PROJECT_ROOT, RAW_DIR

TABLES_DIR = PROJECT_ROOT / "reports" / "tables"
OUTPUT = PROJECT_ROOT / "excel" / "nissan_scenario_model.xlsx"

FONT = "Arial"
BLUE, BLACK, GREEN = "0000FF", "000000", "008000"
HEADER_FILL = PatternFill("solid", fgColor="1F3A5F")
SECTION_FILL = PatternFill("solid", fgColor="D9E1EC")
YELLOW_FILL = PatternFill("solid", fgColor="FFFF00")
THIN = Side(style="thin", color="B0B7C3")

BN = '#,##0.0;(#,##0.0);"-"'          # billions of yen, negatives in brackets, zero as a dash
THOUSAND = '#,##0;(#,##0);"-"'
PCT = '0.0%;(0.0%);"-"'
PCT0 = '0%;(0%);"-"'
RATE = '0.000;(0.000);"-"'

# Scenario levers: label, unit, Downside, Base, Upside, number format, note.
# A Base value of None means "link to Nissan's own outlook" (a formula).
LEVERS = [
    ("Retail volume", "thousand cars", 3050, None, 3200, THOUSAND,
     "Base = Nissan's current outlook (cut to 3,150 on 3 Aug 2026)"),
    ("Change in the US tariff burden", "%", 0.10, 0.0, -0.10, PCT0,
     "+10% means a heavier burden; the base burden is derived on Inputs"),
    ("Delivery of Monozukuri cost savings", "% of the +340 bn", 0.90, 1.0, 1.05, PCT0,
     "Share of the outlook's savings that Nissan actually delivers"),
    ("Raw materials burden", "% of the -85 bn", 1.10, 1.0, 0.95, PCT0,
     "Aluminium and oil risks in Nissan's outlook"),
    ("Inflation burden", "% of the -60 bn", 1.10, 1.0, 0.95, PCT0, "Cost inflation versus the outlook"),
    ("Delivery of offsets to the volume cut", "% of the gap", 0.75, 1.0, 1.0, PCT0,
     "Nissan cut volume but kept its profit outlook: this is how much of that gap it closes"),
    ("USD/JPY average", "JPY per USD", 145, None, 155, '0.0',
     "Only matters if you enter an FX sensitivity on Inputs"),
]


# ----------------------------------------------------------------------
# Small styling helpers
# ----------------------------------------------------------------------
def style(cell, color=BLACK, bold=False, fill=None, fmt=None, align=None, italic=False, size=10):
    cell.font = Font(name=FONT, size=size, bold=bold, italic=italic, color=color)
    if fill is not None:
        cell.fill = fill
    if fmt is not None:
        cell.number_format = fmt
    if align is not None:
        cell.alignment = align
    return cell


def put(ws, ref, value, **kwargs):
    ws[ref] = value
    return style(ws[ref], **kwargs)


def header_row(ws, row, labels, first_column=1):
    for offset, label in enumerate(labels):
        cell = ws.cell(row=row, column=first_column + offset, value=label)
        style(cell, color="FFFFFF", bold=True, fill=HEADER_FILL,
              align=Alignment(horizontal="center" if offset else "left", vertical="center", wrap_text=True))


def section(ws, row, text, width=7):
    for column in range(1, width + 1):
        ws.cell(row=row, column=column).fill = SECTION_FILL
    style(ws.cell(row=row, column=1, value=text), bold=True, fill=SECTION_FILL)


def fit_to_page(ws) -> None:
    """Print each sheet one page wide, in landscape."""
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)


def indent_notes(ws, column: str) -> None:
    """Give the text notes in one column a small left margin (skips header cells)."""
    for cell in ws[column]:
        is_header = cell.fill is not None and cell.fill.fgColor is not None and cell.fill.fgColor.rgb == "001F3A5F"
        if isinstance(cell.value, str) and cell.row > 3 and not cell.value.startswith("=") and not is_header:
            cell.alignment = Alignment(indent=2, vertical="center")


def widths(ws, mapping):
    for column, size in mapping.items():
        ws.column_dimensions[column].width = size


# ----------------------------------------------------------------------
# Reading the verified numbers
# ----------------------------------------------------------------------
def read_numbers() -> dict:
    parameters = pd.read_csv(TABLES_DIR / "scenario_parameters.csv").set_index("parameter")["value"]
    drivers = pd.read_csv(TABLES_DIR / "driver_items.csv").set_index("item")
    group = pd.read_csv(RAW_DIR / "nissan_group_financials.csv").set_index("period_id")
    return {
        "op_fy2025": float(group.loc["FY2025", "operating_profit_bn"]),
        "sales_fy2025": float(group.loc["FY2025", "net_sales_bn"]),
        "sales_outlook": float(group.loc["FY2026F", "net_sales_bn"]),
        "retail_fy2025": float(parameters["retail_volume_fy2025"]),
        "volume_original": float(parameters["retail_volume_outlook_original"]),
        "volume_revised": float(parameters["retail_volume_outlook_revised"]),
        "outlook": float(parameters["outlook_operating_profit_bn"]),
        "usd_jpy": float(parameters["usd_jpy_assumption"]),
        "tariff_fy2025": float(parameters["tariff_burden_fy2025_bn"]),
        "drivers": {item: float(row["fy2026_outlook_bn"]) for item, row in drivers.iterrows()
                    if item != "Rounding difference"},
    }


# ----------------------------------------------------------------------
# Sheets
# ----------------------------------------------------------------------
def build_guide(wb) -> None:
    ws = wb.active
    ws.title = "Guide"
    ws.sheet_view.showGridLines = False
    widths(ws, {"A": 26, "B": 100})
    put(ws, "A1", "Nissan Turnaround 2027: FY2026 operating profit scenario model", bold=True, size=14)
    put(ws, "A2", "Illustrative sensitivities built on Nissan's official profit bridge. NOT a forecast.", italic=True, color="666666")
    rows = [
        ("Purpose", "Shows how FY2026 operating profit (Nissan's outlook: JPY 200 bn) changes if volume, US tariffs, cost savings, "
                    "raw materials, inflation or the delivery of offsets turn out differently."),
        ("How to use", "1) Go to Inputs. 2) Change the YELLOW cells (the scenario levers) or pick a scenario in the yellow dropdown. "
                       "3) Read the results on Model and Summary. 4) Sensitivity shows profit for many volumes and tariff burdens at once."),
        ("Colour code", "Blue text = typed input or published number. Black = formula. Green = link to another sheet. "
                        "Yellow fill = a lever you are meant to change."),
        ("Money and units", "Money is in JPY billions (bn); volumes in thousand cars; percentages are stored as fractions (10% = 0.10)."),
        ("Where the numbers come from", "Published figures come from Nissan's FY2025 results and its Q4 FY2025 presentation script (13 May 2026). "
                                        "They were loaded from the project's verified tables, not typed into the workbook by hand."),
        ("DERIVED values", "Three inputs are derived by us, not published: the +157 bn sales performance of the outlook, the profit per extra car "
                           "(about JPY 1.05 million) and the FY2026 tariff burden (256 bn). They are marked DERIVED on Inputs."),
        ("Base scenario", "The Base column reproduces Nissan's outlook (200 bn). The Downside and Upside levers are our illustrative choices, "
                          "deliberately wider on the downside because the outlook already assumes good delivery. Challenge them."),
        ("Known gap", "Nissan's yen sensitivity is not in the documents we used, so the FX sensitivity on Inputs is 0. Enter your own estimate to activate it."),
        ("Simplifications", "Revenue is scaled with volume at constant price and mix; the profit per extra car is linear; "
                            "quarterly seasonality and price/mix effects are not modelled."),
        ("Check", "After opening the file in Excel and saving it, run: python src/check_scenario_model.py"),
    ]
    for index, (label, text) in enumerate(rows, start=4):
        put(ws, f"A{index}", label, bold=True, align=Alignment(vertical="top"))
        put(ws, f"B{index}", text, align=Alignment(wrap_text=True, vertical="top"))
        ws.row_dimensions[index].height = 46
    put(ws, "A15", "Colour legend", bold=True)
    put(ws, "A16", "Typed input", color=BLUE)
    put(ws, "A17", "Formula", color=BLACK)
    put(ws, "A18", "Link to another sheet", color=GREEN)
    put(ws, "A19", "Lever to change", color=BLUE, fill=YELLOW_FILL)


def build_inputs(wb, n: dict) -> None:
    ws = wb.create_sheet("Inputs")
    widths(ws, {"A": 46, "B": 20, "C": 14, "D": 14, "E": 14, "F": 74})
    put(ws, "A1", "Inputs", bold=True, size=14)
    put(ws, "A3", "Selected scenario (dropdown)", bold=True)
    put(ws, "C3", "Base", color=BLUE, fill=YELLOW_FILL, bold=True, align=Alignment(horizontal="center"))
    validation = DataValidation(type="list", formula1='"Downside,Base,Upside"', allow_blank=False)
    ws.add_data_validation(validation)
    validation.add("C3")
    put(ws, "F3", "Pick Downside, Base or Upside: the 'Selected' column on Model and Summary follows it.", italic=True, color="666666")

    section(ws, 4, "A. Published and derived numbers (JPY bn unless stated)", 6)
    header_row(ws, 5, ["Item", "Unit", "Value", "", "", "Origin and note"])
    rows = [
        (6, "FY2025 operating profit", "JPY bn", n["op_fy2025"], BN, "Nissan: reported"),
        (7, "FY2025 net sales", "JPY bn", n["sales_fy2025"], BN, "Nissan: reported"),
        (8, "FY2026 outlook net sales", "JPY bn", n["sales_outlook"], BN, "Nissan: outlook"),
        (9, "FY2025 retail volume", "thousand cars", n["retail_fy2025"], THOUSAND, "Nissan: reported, global retail"),
        (10, "FY2026 volume outlook, original (May 2026)", "thousand cars", n["volume_original"], THOUSAND, "Nissan: the outlook behind the bridge"),
        (11, "FY2026 volume outlook, revised (3 Aug 2026)", "thousand cars", n["volume_revised"], THOUSAND, "Nissan: cut announced with Q1 FY2026 results"),
        (12, "FY2026 operating profit outlook", "JPY bn", n["outlook"], BN, "Nissan: kept in August 2026"),
        (13, "USD/JPY assumed in the outlook", "JPY per USD", n["usd_jpy"], '0.0', "Nissan: outlook assumption"),
        (14, "FY2025 US tariff burden", "JPY bn", n["tariff_fy2025"], BN, "Nissan: total tariff impact on FY2025 profit"),
    ]
    for row, label, unit, value, fmt, note in rows:
        put(ws, f"A{row}", label)
        put(ws, f"B{row}", unit, color="666666")
        put(ws, f"C{row}", value, color=BLUE, fmt=fmt)
        put(ws, f"F{row}", note, color="666666")

    section(ws, 16, "Bridge from FY2025 to the FY2026 outlook (change in operating profit, JPY bn)", 6)
    bridge = [
        (17, "Foreign exchange", "Foreign exchange", "Nissan"),
        (18, "Raw materials", "Raw materials", "Nissan"),
        (19, "US tariffs", "US tariffs", "Nissan: the burden improves by this much"),
        (20, "Sales performance", "Sales performance", "DERIVED: not stated by Nissan; closes the bridge"),
        (21, "Inflation", "Inflation", "Nissan"),
        (22, "Monozukuri cost savings", "Monozukuri cost savings", "Nissan: fixed and variable manufacturing savings"),
        (23, "One-time items", "One-time items", "Nissan: FY2025 one-time gains do not repeat"),
        (24, "Other items", "Other items", "Nissan"),
    ]
    for row, label, key, note in bridge:
        put(ws, f"A{row}", label)
        put(ws, f"B{row}", "JPY bn", color="666666")
        put(ws, f"C{row}", n["drivers"][key], color=BLUE, fmt=BN)
        put(ws, f"F{row}", note, color="DC2626" if note.startswith("DERIVED") else "666666",
            bold=note.startswith("DERIVED"))

    section(ws, 26, "Derived parameters (formulas)", 6)
    derived = [
        (27, "FY2026 US tariff burden", "JPY bn", "=C14-C19", BN, "DERIVED: FY2025 burden minus the improvement above"),
        (28, "Profit per extra car", "JPY million", "=C20/(C10-C9)", RATE,
         "DERIVED: sales performance / extra cars in the original outlook (assumes it is all volume, linear)"),
        (29, "Gap created by the volume cut", "JPY bn", "=(C10-C11)*C28", BN,
         "DERIVED: cars cut from the outlook x profit per extra car"),
        (30, "Bridge check: FY2025 profit + changes - outlook", "JPY bn", "=C6+SUM(C17:C24)-C12", BN,
         "Must be 0: the bridge closes"),
    ]
    for row, label, unit, formula, fmt, note in derived:
        put(ws, f"A{row}", label)
        put(ws, f"B{row}", unit, color="666666")
        put(ws, f"C{row}", formula, fmt=fmt)
        put(ws, f"F{row}", note, color="666666")
    put(ws, "A31", "FX sensitivity (profit per JPY 1 move in USD/JPY)", bold=True)
    put(ws, "B31", "JPY bn per JPY 1", color="666666")
    put(ws, "C31", 0, color=BLUE, fill=YELLOW_FILL, fmt='0.0;(0.0);"-"')
    put(ws, "F31", "Left at 0: Nissan's sensitivity is not in the documents used. Enter your own estimate to activate the yen lever.",
        color="666666")

    section(ws, 33, "B. Scenario levers (change the yellow cells)", 6)
    header_row(ws, 34, ["Lever", "Unit", "Downside", "Base", "Upside", "Note"])
    for index, (label, unit, down, base, up, fmt, note) in enumerate(LEVERS, start=35):
        put(ws, f"A{index}", label)
        put(ws, f"B{index}", unit, color="666666")
        put(ws, f"C{index}", down, color=BLUE, fill=YELLOW_FILL, fmt=fmt)
        if base is None:
            link = "=C11" if label == "Retail volume" else "=C13"
            put(ws, f"D{index}", link, fmt=fmt, fill=YELLOW_FILL)
        else:
            put(ws, f"D{index}", base, color=BLUE, fill=YELLOW_FILL, fmt=fmt)
        put(ws, f"E{index}", up, color=BLUE, fill=YELLOW_FILL, fmt=fmt)
        put(ws, f"F{index}", note, color="666666")
    indent_notes(ws, "F")
    ws.freeze_panes = "A4"


LEVER_ROW = {name: 35 + i for i, name in enumerate(
    ["volume", "tariff", "savings", "raw", "inflation", "offsets", "usd_jpy"])}


def build_model(wb) -> None:
    ws = wb.create_sheet("Model")
    widths(ws, {"A": 52, "B": 16, "C": 14, "D": 14, "E": 14, "F": 18, "G": 70})
    put(ws, "A1", "Model: FY2026 operating profit by scenario", bold=True, size=14)
    put(ws, "A2", "All cells are formulas that follow the same pattern in the Downside, Base and Upside columns.",
        italic=True, color="666666")
    header_row(ws, 4, ["Item", "Unit", "Downside", "Base", "Upside", "Selected", "How it is calculated"])
    put(ws, "F4", "=Inputs!$C$3", color="FFFFFF", bold=True, fill=HEADER_FILL, align=Alignment(horizontal="center"))
    ws["F4"].font = Font(name=FONT, size=10, bold=True, color="FFFFFF")

    L = LEVER_ROW
    lines = [
        # row, label, unit, formula (for column C; D and E follow), format, note, link colour?
        (6, "Retail volume", "thousand cars", f"=Inputs!C{L['volume']}", THOUSAND, "Scenario lever", GREEN),
        (7, "Net sales", "JPY bn", "=Inputs!$C$8*C6/Inputs!$C$11", BN, "Outlook net sales scaled with volume (constant price and mix)", GREEN),
        (9, "Operating profit FY2025", "JPY bn", "=Inputs!$C$6", BN, "Reported", GREEN),
        (10, "Foreign exchange", "JPY bn", f"=Inputs!$C$17+Inputs!$C$31*(Inputs!C{L['usd_jpy']}-Inputs!$C$13)", BN,
         "Outlook effect + FX sensitivity x (scenario USD/JPY - outlook USD/JPY)", GREEN),
        (11, "Raw materials", "JPY bn", f"=Inputs!$C$18*Inputs!C{L['raw']}", BN, "Outlook effect x raw materials lever", GREEN),
        (12, "US tariffs", "JPY bn", f"=Inputs!$C$14-Inputs!$C$27*(1+Inputs!C{L['tariff']})", BN,
         "FY2025 burden minus the scenario FY2026 burden", GREEN),
        (13, "Sales performance in the original plan", "JPY bn", "=Inputs!$C$20", BN, "DERIVED +157 bn (volume and mix of the May 2026 outlook)", GREEN),
        (14, "Volume change versus the original plan", "JPY bn", "=(C6-Inputs!$C$10)*Inputs!$C$28", BN,
         "(scenario volume - original outlook volume) x profit per extra car", GREEN),
        (15, "Offsets found to the volume cut", "JPY bn", f"=Inputs!C{L['offsets']}*Inputs!$C$29", BN,
         "Delivery lever x the gap created by the volume cut", GREEN),
        (16, "Inflation", "JPY bn", f"=Inputs!$C$21*Inputs!C{L['inflation']}", BN, "Outlook effect x inflation lever", GREEN),
        (17, "Monozukuri cost savings", "JPY bn", f"=Inputs!$C$22*Inputs!C{L['savings']}", BN, "Outlook savings x delivery lever", GREEN),
        (18, "One-time items", "JPY bn", "=Inputs!$C$23", BN, "FY2025 one-time gains do not repeat", GREEN),
        (19, "Other items", "JPY bn", "=Inputs!$C$24", BN, "As in the outlook", GREEN),
        (20, "Total change versus FY2025", "JPY bn", "=SUM(C10:C19)", BN, "Sum of the causes above", BLACK),
        (21, "Operating profit FY2026", "JPY bn", "=C9+C20", BN, "FY2025 profit + total change", BLACK),
        (22, "Operating margin", "% of sales", "=IF(C7=0,0,C21/C7)", PCT, "Profit / net sales", BLACK),
        (23, "Change versus Nissan's outlook", "JPY bn", "=C21-Inputs!$C$12", BN, "Scenario profit - outlook profit", GREEN),
        (25, "Break-even volume", "thousand cars", "=IF(Inputs!$C$28=0,0,C6-C21/Inputs!$C$28)", THOUSAND,
         "Volume at which profit would be zero, at the derived profit per extra car", GREEN),
        (26, "Headroom to break-even", "thousand cars", "=C6-C25", THOUSAND, "Scenario volume - break-even volume", BLACK),
        (27, "Headroom as a share of volume", "%", "=IF(C6=0,0,C26/C6)", PCT, "Headroom / scenario volume", BLACK),
    ]
    for row, label, unit, formula, fmt, note, colour in lines:
        bold = row in (20, 21)
        put(ws, f"A{row}", label, bold=bold)
        put(ws, f"B{row}", unit, color="666666")
        for column in "CDE":
            # Move every RELATIVE reference to column C (not $C$...) to this scenario's column.
            shifted = re.sub(r"(?<![$A-Za-z])C(?=\d)", column, formula)
            put(ws, f"{column}{row}", shifted, color=colour, bold=bold, fmt=fmt)
        put(ws, f"F{row}", f"=INDEX(C{row}:E{row},MATCH($F$4,$C$4:$E$4,0))", bold=bold, fmt=fmt)
        put(ws, f"G{row}", note, color="666666")
    for column in "ABCDEFG":
        ws[f"{column}21"].border = Border(top=THIN, bottom=THIN)
    section(ws, 8, "Operating profit build (JPY bn)", 7)
    section(ws, 24, "Break-even", 7)
    indent_notes(ws, "G")
    put(ws, "F3", "Selected scenario", italic=True, color="666666", align=Alignment(horizontal="center"))
    put(ws, "A29", "Check: Base equals Nissan's outlook", bold=True)
    put(ws, "D29", '=IF(ABS(D21-Inputs!$C$12)<0.05,"OK","CHECK")', bold=True, align=Alignment(horizontal="center"))
    ws.freeze_panes = "C5"


def build_summary(wb) -> None:
    ws = wb.create_sheet("Summary")
    widths(ws, {"A": 46, "B": 16, "C": 14, "D": 14, "E": 14, "F": 18})
    put(ws, "A1", "Summary: the three scenarios side by side", bold=True, size=14)
    header_row(ws, 4, ["Metric", "Unit", "Downside", "Base", "Upside", "Selected"])
    put(ws, "F4", "=Inputs!$C$3", color="FFFFFF", bold=True, fill=HEADER_FILL, align=Alignment(horizontal="center"))
    ws["F4"].font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
    put(ws, "F3", "Selected scenario", italic=True, color="666666", align=Alignment(horizontal="center"))
    metrics = [
        (5, "Retail volume", "thousand cars", 6, THOUSAND),
        (6, "Net sales", "JPY bn", 7, BN),
        (7, "Operating profit FY2026", "JPY bn", 21, BN),
        (8, "Operating margin", "% of sales", 22, PCT),
        (9, "Change versus Nissan's outlook", "JPY bn", 23, BN),
        (10, "Break-even volume", "thousand cars", 25, THOUSAND),
        (11, "Headroom to break-even", "thousand cars", 26, THOUSAND),
    ]
    for row, label, unit, model_row, fmt in metrics:
        bold = row == 7
        put(ws, f"A{row}", label, bold=bold)
        put(ws, f"B{row}", unit, color="666666")
        for column in "CDEF":
            put(ws, f"{column}{row}", f"=Model!{column}{model_row}", color=GREEN, bold=bold, fmt=fmt)

    section(ws, 13, "What moves profit versus the Base case (JPY bn)", 6)
    header_row(ws, 14, ["Cause", "Unit", "Downside", "Base", "Upside", "Selected"])
    walk = [(15, "Foreign exchange", 10), (16, "Raw materials", 11), (17, "US tariffs", 12),
            (18, "Volume change versus the original plan", 14), (19, "Offsets found to the volume cut", 15),
            (20, "Inflation", 16), (21, "Monozukuri cost savings", 17)]
    for row, label, model_row in walk:
        put(ws, f"A{row}", label)
        put(ws, f"B{row}", "JPY bn", color="666666")
        for column in "CDEF":
            put(ws, f"{column}{row}", f"=Model!{column}{model_row}-Model!$D{model_row}", color=GREEN, fmt=BN)
    put(ws, "A22", "Total versus Base", bold=True)
    put(ws, "B22", "JPY bn", color="666666")
    for column in "CDEF":
        put(ws, f"{column}22", f"=SUM({column}15:{column}21)", bold=True, fmt=BN)
        ws[f"{column}22"].border = Border(top=THIN)

    chart = BarChart()
    chart.type = "col"
    chart.title = "FY2026 operating profit by scenario (JPY bn)"
    chart.add_data(Reference(ws, min_col=3, max_col=5, min_row=7, max_row=7), from_rows=True, titles_from_data=False)
    chart.set_categories(Reference(ws, min_col=3, max_col=5, min_row=4, max_row=4))
    chart.legend = None
    chart.dataLabels = DataLabelList()
    chart.dataLabels.showVal = True
    chart.dataLabels.showSerName = False
    chart.dataLabels.showCatName = False
    chart.dataLabels.showLegendKey = False
    chart.y_axis.title = "JPY bn"
    chart.y_axis.delete = False
    chart.x_axis.delete = False
    chart.height, chart.width = 8, 14
    ws.add_chart(chart, "H4")


def build_sensitivity(wb) -> None:
    ws = wb.create_sheet("Sensitivity")
    widths(ws, {"A": 34, **{c: 11 for c in "BCDEFGH"}})
    put(ws, "A1", "Sensitivity: operating profit (JPY bn) by volume and tariff burden", bold=True, size=14)
    put(ws, "A2", "All other levers at Nissan's outlook. Same grid as the Python analysis (fig13). Profit per extra car is derived and illustrative.",
        italic=True, color="666666")
    put(ws, "A4", "Tariff burden change (down) / Retail volume, thousand cars (across)", bold=True,
        align=Alignment(wrap_text=True, vertical="center"))
    ws.row_dimensions[4].height = 42
    volumes = [2900, 3000, 3100, 3150, 3200, 3300, 3400]
    tariffs = [-0.5, -0.25, 0.0, 0.25, 0.5]
    for offset, volume in enumerate(volumes):
        put(ws, f"{chr(66 + offset)}4", volume, color=BLUE, bold=True, fmt=THOUSAND, fill=SECTION_FILL,
            align=Alignment(horizontal="center", vertical="center"))
    for index, tariff in enumerate(tariffs, start=5):
        put(ws, f"A{index}", tariff, color=BLUE, bold=True, fmt='+0%;-0%;0%', fill=SECTION_FILL,
            align=Alignment(horizontal="center"))
        for offset in range(len(volumes)):
            column = chr(66 + offset)
            put(ws, f"{column}{index}",
                f"=Inputs!$C$12+({column}$4-Inputs!$C$11)*Inputs!$C$28-$A{index}*Inputs!$C$27",
                fmt=BN, align=Alignment(horizontal="center"))
    ws.conditional_formatting.add("B5:H9", ColorScaleRule(start_type="min", start_color="F8696B",
                                                          mid_type="num", mid_value=0, mid_color="FFFFFF",
                                                          end_type="max", end_color="63BE7B"))
    put(ws, "A11", "Reading the grid: each row is a change in the FY2026 tariff burden (base 256 bn); each column is global retail volume.",
        italic=True, color="666666")


def main() -> int:
    try:
        numbers = read_numbers()
    except FileNotFoundError as error:
        print(f"[STOP] {error}. Run python src/driver_analysis.py first.")
        return 1
    wb = Workbook()
    build_guide(wb)
    build_inputs(wb, numbers)
    build_model(wb)
    build_summary(wb)
    build_sensitivity(wb)
    for sheet in wb.worksheets:
        fit_to_page(sheet)
    wb.calculation.fullCalcOnLoad = True          # Excel calculates all formulas when the file opens
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUTPUT)
    print("=" * 66)
    print("NISSAN TURNAROUND 2027 - BUILD THE EXCEL SCENARIO MODEL")
    print("=" * 66)
    print(f"[PASS] wrote {OUTPUT.relative_to(PROJECT_ROOT)} with sheets: " + ", ".join(wb.sheetnames))
    print("Next: open the file in Excel, press Ctrl+S, then run: python src/check_scenario_model.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())