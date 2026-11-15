# Excel Scenario Model

File: `excel/nissan_scenario_model.xlsx`, built by `python src/build_scenario_model.py`
Check: `python src/check_scenario_model.py` (15 checks)

Illustrative sensitivities on Nissan's official FY2026 profit bridge. NOT a forecast.

## Sheets

| Sheet       | Content                                                                                                          |
| ----------- | ---------------------------------------------------------------------------------------------------------------- |
| Guide       | Purpose, how to use, colour legend, caveats                                                                      |
| Inputs      | Published and derived numbers (blue), derived parameters (formulas), scenario levers (yellow), scenario dropdown |
| Model       | FY2026 operating profit for Downside, Base and Upside, plus break-even volume and headroom, all formulas         |
| Summary     | The three scenarios side by side, what moves profit versus Base, and a chart                                     |
| Sensitivity | Profit for 7 volumes x 5 tariff-burden changes (same grid as the Python analysis)                                |

Colour code: blue = typed input, black = formula, green = link to another sheet, yellow fill = a lever to change.

## Scenario levers (illustrative)

| Lever                                 | Downside | Base                     | Upside                                              |
| ------------------------------------- | -------- | ------------------------ | --------------------------------------------------- |
| Retail volume (thousand cars)         | 3,050    | 3,150 (Nissan's outlook) | 3,200                                               |
| US tariff burden change               | +10%     | 0%                       | -10%                                                |
| Delivery of Monozukuri savings        | 90%      | 100%                     | 105%                                                |
| Raw materials burden                  | 110%     | 100%                     | 95%                                                 |
| Inflation burden                      | 110%     | 100%                     | 95%                                                 |
| Delivery of offsets to the volume cut | 75%      | 100%                     | 100%                                                |
| USD/JPY                               | 145      | 150                      | 155 (no effect unless an FX sensitivity is entered) |

The downside is deliberately wider than the upside because the outlook already assumes good delivery.

## Results with the default levers

|                                        | Downside | Base  | Upside |
| -------------------------------------- | -------- | ----- | ------ |
| Operating profit FY2026 (JPY bn)       | -19.0    | 200.0 | 302.5  |
| Operating margin                       | -0.2%    | 1.5%  | 2.3%   |
| Versus Nissan's outlook                | -219.0   | 0     | +102.5 |
| Headroom to break-even (thousand cars) | -18      | 190   | 287    |

## Derived values and limits

- Three inputs are DERIVED by us (not published by Nissan): the +157 bn sales performance of the outlook,
  the profit per extra car (about JPY 1.05 million) and the FY2026 tariff burden (256 bn).
- The Base case reproduces Nissan's outlook of 200 bn (the model checks this).
- The FX sensitivity is 0: Nissan's figure is not in the documents used.
- Revenue scales with volume at constant price and mix; the profit per extra car is linear; no seasonality.

## How the model is verified

1. The workbook uses live formulas; the checker confirms the Model sheet contains no typed numbers and that
   the three scenario columns share one formula pattern.
2. Published inputs equal the verified pipeline tables.
3. After Excel calculates the file, every result is compared with an independent Python calculation, the
   Base case must equal Nissan's outlook, and the Sensitivity grid must equal the Python grid of Step 7.
