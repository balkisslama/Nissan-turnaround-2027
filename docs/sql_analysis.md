# SQL Analysis

17 queries in `sql/02_*.sql` to `sql/06_*.sql` answer the project's business
questions. Run them all with:

    python src/run_sql_analysis.py          # prints every answer, saves CSVs
    python src/run_sql_analysis.py q07      # one query (name prefix)
    python src/check_sql_analysis.py        # 22 checks: independent recalculation

Each answer is saved as `reports/tables/<query name>.csv` (used by Excel and
Power BI). Every query begins with its business question in plain English.

## Query catalogue

| Query                          | Question                                                        | Notes                                                                                    |
| ------------------------------ | --------------------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| q01 profit trend               | How did sales, operating profit and margin change year on year? | LAG window function                                                                      |
| q02 operating vs net profit    | How far is net income from operating profit?                    | Gap = costs outside normal operations                                                    |
| q03 cash flow                  | Is Nissan generating cash?                                      | Consolidated, includes the sales finance arm; not the same as automotive free cash flow  |
| q04 balance sheet              | Is the equity ratio growing or shrinking?                       | Change in percentage points                                                              |
| q05 investment intensity       | R&D and capex relative to sales                                 | capex / depreciation above 1 = investing more than equipment wears out                   |
| q06 region profit              | Profit and segment margin per region                            | Segment sales include inter-region sales                                                 |
| q07 Q1 profit swing            | Which regions explain the Q1 FY2026 improvement?                | Pivot with CASE WHEN                                                                     |
| q08 loss-making regions        | How many regions lose money, and which?                         | Eliminations line excluded                                                               |
| q09 Q1 retail change           | Where did retail volume rise or fall?                           | USA and China are PART of North America and Asia                                         |
| q10 retail mix                 | Share of worldwide retail by region/country                     |                                                                                          |
| q11 forecast vs actual         | Where does the FY2026 outlook expect growth?                    | Actual "rest of world" rebuilt as Asia + Others - China to match the forecast definition |
| q12 revenue per vehicle        | Revenue per wholesale vehicle vs yen moves                      | Includes non-vehicle revenue; weak yen inflates yen revenue                              |
| q13 restructuring plan         | Plants, capacity, models, volume outlook                        |                                                                                          |
| q14 progress so far            | Savings and job cuts achieved vs target                         | Headcount is a rough guide                                                               |
| q15 profit bridge              | FY2024 profit + savings + implied other effects = FY2025 profit | "Other effects" is IMPLIED, not reported by Nissan                                       |
| q16 yen vs Nissan assumption   | Market USD/JPY vs Nissan's own average                          | Cross-check of two independent sources                                                   |
| q17 share price by fiscal year | Nissan vs the average of four rivals                            | Adjusted prices; first-to-last trading day of each fiscal year                           |

## Findings so far (from the database)

1. **Profit collapsed while sales barely moved.** Operating margin: 4.5% in
   FY2023, 0.6% in FY2024, 0.5% in FY2025; operating profit fell 87.7% then
   16.9% (matching Nissan's published figure) while sales fell only 0.4% and 4.9%.
2. **Final profit is far below operating profit** in FY2024 (-740.7 bn yen) and
   FY2025 (-591.1 bn), against -31.8 to -155.2 bn in FY2021-FY2023: large costs
   outside normal operations.
3. **Cash:** simple free cash flow (consolidated) was +700.4, +774.1 and +148.2 bn
   in FY2021-FY2023, then -217.5 bn (FY2024) and -119.6 bn (FY2025). The cash
   balance still grew (to 2,264.8 bn) thanks to financing inflows.
4. **Financial cushion shrank:** equity ratio 30.1% (FY2023) to 24.2% (FY2025).
5. **Europe loses money in every period** (FY2025: -54.1 bn, segment margin
   -3.1%); **North America** earns the most (FY2025: +68.7 bn).
6. **The Q1 recovery rests on North America:** 150.2 bn of the 157.1 bn regional
   profit improvement (95.6%). Nissan itself said one-time US tariff-related
   gains helped the quarter.
7. **Volume:** Q1 retail -0.8% overall; USA +10.0% and China +7.4%, but Europe
   -14.7% and Others -18.5%. North America is 41.0% of FY2025 retail (USA 28.8%),
   China 20.7%, Europe 10.1%.
8. **The FY2026 outlook assumes** China -11.2% but Europe +7.3% and Japan +7.8%,
   even though Europe retail fell 14.7% in Q1. This is a tension to test in the
   scenario model.
9. **Revenue per vehicle rose 15.6%** in Q1 while USD/JPY rose 10.3% and EUR/JPY
   12.8%, so much of the rise reflects the weaker yen.
10. **Re:Nissan progress:** cost savings 255 of 500 bn yen (51.0%); headcount
    down 12,711 (about 64% of the 20,000 target, a rough guide); plants 17 to 10,
    capacity -28.6%, models -19.6%; FY2026 volume outlook cut 4.5%.
11. **Bridge FY2024 to FY2025:** 69.8 bn profit + 255.0 bn savings would suggest
    about 324.8 bn, yet profit was 58.0 bn: an IMPLIED -266.8 bn of other
    effects (volume, mix, currency, tariffs, other costs). Splitting that figure
    is a key task for the next steps.

## Limits to keep in mind

- Q1 figures are single quarters; seasonality is not removed.
- Regional sums differ from group totals by up to 0.5 bn because published
  figures are rounded.
- Production capacity utilisation is NOT computed yet: Nissan's capacity target
  excludes China, but its published production figures include it. Step 7 will
  handle this with an explicit, documented assumption.
- Electric vehicle (EV) market analysis is left to Step 6, after inspecting the
  country names used in the EV data.
