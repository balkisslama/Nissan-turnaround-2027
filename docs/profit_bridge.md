# Official Profit Bridge

`data/raw/nissan_profit_bridge.csv` holds Nissan's own breakdown of the change
in operating profit, from the Q4 FY2025 results presentation script
(13 May 2026):
https://www.nissan-global.com/EN/IR/FINANCIAL_RESULTS/ASSETS/DATA/2025/20254th_presentation_script_115_e.pdf

It is NOT loaded into the SQL database: it is a small supplementary dataset
read directly by the Python charts (and, later, by Excel and Power BI).
Validate it with `python src/validate_bridge_data.py`.

## Columns

| Column     | Meaning                                                                               |
| ---------- | ------------------------------------------------------------------------------------- |
| bridge_id  | `FY2025_ACTUAL` (FY2024 to FY2025) or `FY2026_OUTLOOK` (FY2025 to the FY2026 outlook) |
| step       | 0 = starting profit, then each cause, last = ending profit                            |
| item       | The cause (or the starting / ending profit)                                           |
| item_type  | `start`, `change` or `end`                                                            |
| amount_bn  | JPY billions (profit level for start/end; change for causes)                          |
| is_derived | 1 = computed by us, not stated by Nissan                                              |
| note       | Explanation or caveat                                                                 |
| source_ids | Source code (`SCRIPT-Q4FY2025`)                                                       |

## Derived values (flagged, never hidden)

- **FY2025 bridge, "Rounding difference" (+0.3):** the stated causes are rounded,
  so this small item makes the bridge close exactly.
- **FY2026 outlook, "Sales performance" (+157.0):** Nissan's script did not state
  it. It is derived as 200 - 58 - (sum of the stated causes) so that the bridge
  closes, and is most likely volume and mix. The outlook assumed 3.3 million
  units; on 3 August 2026 Nissan cut the volume outlook to 3.15 million while
  keeping the 200 bn yen operating profit outlook.

## Reading the bridge

- FY2025: US tariffs (-286.0) outweighed the cost savings (Monozukuri, +227.0).
  Before tariffs and all else equal, operating profit would have been about
  344 bn yen (a 2.9% margin), still below the 4.5% margin of FY2023.
- FY2026 outlook: the tariff burden improves by 30 bn yen (so it stays at about
  256 bn yen if the figures hold: derived arithmetic, 286 - 30). The outlook
  depends on +340.0 bn yen of manufacturing cost savings and the derived +157.0.

## Relation to the SQL query q15

Step 5's `q15` estimated the "implied other effects" of FY2025 at -266.8 bn
yen, using the cumulative savings of 255 bn yen (fixed 200 + variable 55). The
official bridge credits 227 bn yen of year-on-year Monozukuri savings and puts
everything else at about -238.8 bn yen (including the rounding difference).
The two figures measure savings differently, which explains the gap of about
28 bn yen; both show a headwind of roughly a quarter of a trillion yen.

## Limits

- Figures are rounded as published.
- The FY2026 outlook bridge was issued in May 2026, before the August cut in the
  volume outlook, and may be out of date.
