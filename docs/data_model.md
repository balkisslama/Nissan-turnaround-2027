# Data Model

The analytical database (`data/processed/nissan.db`, SQLite) is a **star
schema**: fact tables hold measurements, dimension tables hold the context
(period, geography, company, date, source). It is built by
`sql/01_create_schema.sql` via `python src/create_database.py` and its rules
are tested by `python src/test_schema.py`.

## Entity-relationship diagram

```mermaid
erDiagram
    dim_period ||--o{ fact_group_financials : "period"
    dim_period ||--o{ fact_regional_results : "period"
    dim_period ||--o{ fact_volumes : "period"
    dim_geography ||--o{ fact_regional_results : "geography"
    dim_geography ||--o{ fact_volumes : "geography"
    dim_geography |o--o{ dim_geography : "parent of"
    dim_company ||--o{ fact_stock_prices : "company"
    dim_date ||--o{ fact_stock_prices : "day"
    dim_date ||--o{ fact_usd_jpy : "day"

    dim_period {
        TEXT period_id PK
        TEXT period_label
        TEXT period_type
        INTEGER fiscal_year
        TEXT period_start
        TEXT period_end
        INTEGER is_forecast
        INTEGER sort_order
    }
    dim_geography {
        INTEGER geo_id PK
        TEXT geo_name
        TEXT geo_level
        INTEGER parent_geo_id FK
        TEXT definition_note
    }
    dim_company {
        INTEGER company_id PK
        TEXT ticker
        TEXT company_name
        INTEGER is_focus_company
    }
    dim_date {
        TEXT date_key PK
        INTEGER calendar_year
        INTEGER calendar_quarter
        INTEGER calendar_month
        TEXT month_name
        INTEGER day_of_week
        INTEGER is_weekend
        INTEGER nissan_fiscal_year
        INTEGER nissan_fiscal_quarter
    }
    dim_source {
        TEXT source_id PK
        TEXT title
        TEXT publisher
        TEXT url
        TEXT source_type
        TEXT accessed_on
    }
    fact_group_financials {
        TEXT period_id PK, FK
        REAL net_sales_bn
        REAL operating_profit_bn
        REAL net_income_bn
        REAL cfo_bn
        REAL capex_bn
        TEXT source_ids
    }
    fact_regional_results {
        TEXT period_id PK, FK
        INTEGER geo_id PK, FK
        REAL net_sales_bn
        REAL operating_profit_bn
        TEXT source_ids
    }
    fact_volumes {
        TEXT period_id PK, FK
        TEXT metric PK
        INTEGER geo_id PK, FK
        INTEGER units_thousand
        TEXT note
        TEXT source_ids
    }
    fact_stock_prices {
        TEXT date_key PK, FK
        INTEGER company_id PK, FK
        REAL close_jpy
        INTEGER volume
    }
    fact_usd_jpy {
        TEXT date_key PK, FK
        REAL usd_jpy
    }
    fact_restructuring_targets {
        TEXT metric_id PK
        TEXT description
        REAL value
        TEXT unit
        TEXT as_of
        TEXT source_ids
    }
    fact_ev_sales {
        TEXT country PK
        TEXT country_code
        INTEGER year PK
        REAL electric_car_sales
    }
```

Only the main columns are drawn for the fact tables; the full list is in
`sql/01_create_schema.sql`.

## Grain of each table

| Table                      | One row represents                                                  |
| -------------------------- | ------------------------------------------------------------------- |
| dim_period                 | one reporting period (fiscal year, first quarter, or forecast)      |
| dim_geography              | one geographic unit (total, region, country, segment or adjustment) |
| dim_company                | one listed company whose share price is tracked                     |
| dim_date                   | one calendar day, with Nissan fiscal year attached                  |
| dim_source                 | one source document                                                 |
| fact_group_financials      | one period (group level)                                            |
| fact_regional_results      | one period x region (incl. eliminations)                            |
| fact_volumes               | one period x metric x geography                                     |
| fact_restructuring_targets | one Re:Nissan target or progress marker                             |
| fact_stock_prices          | one trading day x company                                           |
| fact_usd_jpy               | one business day                                                    |
| fact_ev_sales              | one country (or aggregate) x year                                   |

## Design decisions

1. **Nissan fiscal year in `dim_date`.** FY2025 = April 2025 to March 2026, so
   daily prices and FX rates can be grouped by Nissan fiscal period.
2. **Conformed geography dimension.** One `dim_geography` serves both regional
   results and volumes; `parent_geo_id` rolls countries (USA, China) up to
   regions without double counting.
3. **Missing values are NULL, never 0.** "Not published" is different from
   "zero".
4. **Sources kept as a text list** (`source_ids`, separated by `;`) instead of
   a bridge table. Simpler for this project; a load-time check verifies that
   each code exists in `dim_source`.
5. **`fact_ev_sales` is stand-alone.** It uses country-level global data, a
   different taxonomy from Nissan's regions.
6. **Constraints enforce quality inside the database** (primary keys, foreign
   keys, CHECK rules, NOT NULL). SQLite needs `PRAGMA foreign_keys = ON` on
   every connection, which all project scripts set.

## Naming conventions

- `dim_` / `fact_` prefixes, snake_case.
- Money columns end in `_bn` (JPY billions); volumes in thousand units.
- Dates are ISO text (`YYYY-MM-DD`).
