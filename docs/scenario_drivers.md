# Profit Drivers, Sensitivities and Break-even

Script: `src/driver_analysis.py` | Check: `src/check_driver_analysis.py` (12 checks)

Inputs: the official profit bridge (`data/raw/nissan_profit_bridge.csv`), the
group financials, volumes and restructuring targets. Outputs: 7 tables in
`reports/tables/` and `fig12_outlook_drivers.png`, `fig13_volume_tariff_sensitivity.png`.

## Tables

| Table                            | Content                                                                                                                                    |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| driver_items / driver_categories | Each cause and the 5 groups (external pressures, cost savings, sales performance, one-time items, other), FY2025 actual and FY2026 outlook |
| outlook_quality                  | The outlook with and without the derived sales effect; FY2025 without one-time gains and without tariffs                                   |
| break_even_volume                | Break-even volume and headroom in a low, central and high case                                                                             |
| volume_tariff_grid               | Operating profit for 7 volumes x 5 tariff-burden changes                                                                                   |
| capacity_utilisation             | Rough plant utilisation outside China                                                                                                      |
| scenario_parameters              | The inputs for the Excel scenario model (Step 8), with an `origin` column (Nissan or DERIVED)                                              |

## Derived values and assumptions (all illustrative)

1. **Sales performance FY2026 (+157 bn):** not stated by Nissan; it closes the bridge.
2. **Profit per extra car (about JPY 1.05 million):** the derived sales performance divided by the
   extra cars in the original outlook (3,300k - 3,151k). It assumes all of it is volume and that
   the relationship is linear. Low and high cases use 0.5x and 1.5x.
3. **FY2026 tariff burden (256 bn):** the FY2025 burden (286 bn) minus the stated 30 bn improvement.
4. **China production** is not published: it is assumed to equal China retail sales, plus or minus 100k cars.
5. The sensitivity grid is anchored on Nissan's CURRENT outlook (200 bn at 3.15 million cars).

## Reading the results

- The volume outlook was cut by 150k cars in August 2026 but the 200 bn profit outlook was kept. At the
  derived rate, that cut is worth about -158 bn, so the outlook depends on roughly that much from other sources.
- Around the outlook, the volume headroom to break-even is about 190k cars (6.0%); the range is 127k to 380k.
- The foreign-exchange effect is not modelled here because Nissan's yen sensitivity is not in our data.
  Step 8 leaves it as an input.

## Limits

- These are sensitivities, not forecasts.
- Quarterly seasonality, price and mix effects are not modelled separately.
- Utilisation uses consolidated global production and an assumed China figure; treat it as a range.
