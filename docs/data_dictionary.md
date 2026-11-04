# Data Dictionary: raw files in `data/raw/`

Units: money in **¥ billions** (`_bn`), volumes in **thousand units**.
Empty cell = value not published in the sources used.

## nissan_group_financials.csv (one row per period)

| Column                            | Meaning                                                                                                            |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| period_id                         | Unique key, e.g. `FY2025`, `Q1_FY2026`, `FY2026F` (F = forecast)                                                   |
| period_type                       | `FY` full year, `Q1` first quarter, `FY_FORECAST` company outlook                                                  |
| fiscal_year                       | Fiscal year number; FY2025 = April 2025 to March 2026                                                              |
| period_start, period_end          | Period dates (ISO format)                                                                                          |
| is_forecast                       | 1 = management forecast, 0 = actual result                                                                         |
| net_sales_bn                      | Consolidated net sales (revenue)                                                                                   |
| operating_profit_bn               | Operating profit (core business profit, before interest and tax)                                                   |
| ordinary_income_bn                | Ordinary income (operating profit plus financial items)                                                            |
| net_income_bn                     | Net income attributable to owners of the parent                                                                    |
| total_assets_bn, net_assets_bn    | Balance sheet totals at period end                                                                                 |
| equity_ratio_pct                  | Net assets as a percentage of total assets                                                                         |
| cfo_bn, cfi_bn, cff_bn            | Cash flows from operating, investing and financing activities (consolidated, including the sales finance business) |
| cash_end_bn                       | Cash and equivalents at end of the year                                                                            |
| capex_bn, depreciation_bn, rnd_bn | Capital expenditure, depreciation, research and development costs                                                  |
| usd_jpy_avg, eur_jpy_avg          | Average exchange rates used by Nissan (yen per USD / EUR)                                                          |
| source_ids                        | Source codes, separated by `;` (see `data_sources.md`)                                                             |

## nissan_regional_results.csv (one row per period and region)

| Column                            | Meaning                                                                                                       |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| period_id                         | `Q1_FY2025`, `Q1_FY2026` or `FY2025`                                                                          |
| region                            | Japan, North America, Europe, Asia, Others, or Eliminations (internal sales removed to avoid double counting) |
| net_sales_bn, operating_profit_bn | Segment results                                                                                               |
| source_ids                        | Source codes                                                                                                  |

## nissan_volumes.csv (one row per period, metric and market)

| Column         | Meaning                                                                                           |
| -------------- | ------------------------------------------------------------------------------------------------- |
| period_id      | Period, including `FY2026F` forecast                                                              |
| metric         | `retail_sales` (to customers), `production`, `wholesale` (shipped to dealers, consolidated basis) |
| market         | Region, country or segment name                                                                   |
| market_level   | `total`, `region`, `country` (a part of a region, never added to regions) or `segment`            |
| units_thousand | Thousand vehicles                                                                                 |
| note           | Caveats, e.g. forecast definitions                                                                |
| source_ids     | Source codes                                                                                      |

## nissan_restructuring_targets.csv (one row per metric)

| Column      | Meaning                                                                    |
| ----------- | -------------------------------------------------------------------------- |
| metric_id   | Unique key                                                                 |
| description | What the number means                                                      |
| value, unit | The number and its unit (`JPY_bn`, `count`, `thousand_units`, `employees`) |
| as_of       | Date or month the value refers to                                          |
| source_ids  | Source codes                                                               |

## Market data files (created by `src/download_market_data.py`)

| File                    | Columns                                                                  |
| ----------------------- | ------------------------------------------------------------------------ |
| stock_prices_daily.csv  | date, ticker, company, close_jpy (adjusted close, yen), volume           |
| usd_jpy_daily.csv       | date, usd_jpy (yen per US dollar)                                        |
| ev_sales_by_country.csv | country, country_code, year, electric_car_sales (new electric cars sold) |
