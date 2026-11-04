# Data Sources

All numbers in `data/raw/` trace back to one of the sources below via the
`source_ids` column. Figures were accessed on **3 November 2026**.
Money is in **¥ billions** unless stated; volumes in **thousand units**.

## Official Nissan documents (primary sources)

| ID           | Document                                                                                                                                                                | Link                                                                                             |
| ------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| SUM-Q1FY2026 | Nissan Q1 FY2026 results summary and press release (3 Aug 2026): group, regional and volume tables, FY2026 outlook, Re:Nissan progress                                  | https://www.nissan-global.com/EN/IR/FINANCIAL_RESULTS/ASSETS/DATA/2026/20261st_summary_641_e.pdf |
| SR-FY2025    | Securities Report for FY2025, year ended 31 Mar 2026 (filed 22 Jun 2026): five-year financial summary, cash flows, cost-reduction progress, plant and portfolio targets | https://www2.nissan-global.com/EN/IR/FINANCIAL_RESULTS/ASSETS/FR/2025/PDF/fr2025.pdf             |
| PR-FY2022    | Nissan press release, FY2022 results (11 May 2023): FY2021 and FY2022 operating profit                                                                                  | https://global.nissannews.com/en/releases/230511-01-e                                            |
| PR-FY2023    | Nissan press release, FY2023 results (9 May 2024): FY2023 operating profit, FX assumptions                                                                              | https://global.nissannews.com/en/releases/240509-01-e                                            |
| IR portal    | Nissan Investor Relations, where all of the above are indexed                                                                                                           | https://www.nissan-global.com/EN/IR/FINANCIAL_RESULTS/                                           |

## Secondary sources (cross-checked)

| ID              | Source                             | Used for                                                                                                                                     | Link                                                                                                          |
| --------------- | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| THEBEEP-FY2025  | The Beep (Australia), 14 May 2026  | FY2024 operating profit of 69.8. Cross-check: 58.0 is -16.9% vs 69.8, which matches the YoY change printed in the official Q1 FY2026 release | https://thebeep.com.au/car-news/nissan-financial-results-fy2025-loss                                          |
| AMS-OPPAMA      | Automotive Manufacturing Solutions | Capacity reduction from 3.5 million to 2.5 million units (excluding China)                                                                   | https://www.automotivemanufacturingsolutions.com/news/nissan-to-halt-oppama-output-and-shift-to-kyushu/644825 |
| MOTOR1-RENISSAN | Motor1 France                      | About 20,000 job cuts (about 15 percent of workforce) under Re:Nissan                                                                        | https://fr.motor1.com/news/759430/nissan-supprime-20000-emplois-ferme-7-usines/                               |

## Market data (downloaded by `src/download_market_data.py`)

| Dataset                                                     | Provider                                          | Link                                                  |
| ----------------------------------------------------------- | ------------------------------------------------- | ----------------------------------------------------- |
| Daily share prices (7201.T, 7203.T, 7267.T, 7261.T, 7270.T) | Yahoo Finance via the `yfinance` library          | https://finance.yahoo.com                             |
| USD/JPY daily rate (series DEXJPUS)                         | Federal Reserve Bank of St. Louis (FRED)          | https://fred.stlouisfed.org/series/DEXJPUS            |
| Electric car sales by country                               | Our World in Data, based on IEA Global EV Outlook | https://ourworldindata.org/grapher/electric-car-sales |

## Known limitations

- Nissan's fiscal year runs April to March: FY2025 = April 2025 to March 2026.
- Nissan reports its China joint venture (Dongfeng) under the equity method,
  so China is largely absent from revenue and operating profit but IS
  included in global retail volumes. Do not compare consolidated
  wholesale directly with global retail.
- China volume figures cover calendar-year periods (Jan-Dec / Jan-Mar), not
  Nissan's April-March year.
- The FY2026 forecast row "Others incl. Asia ex-China" is NOT comparable with
  the actual "Others" rows (see `note` column).
- Operating profit for FY2021 to FY2024 comes from press releases; ordinary
  income, assets and cash flows come from the Securities Report.
- Figures are rounded as published, so regional sums can differ from totals by
  up to ¥0.5 billion; the validation script allows for this.
