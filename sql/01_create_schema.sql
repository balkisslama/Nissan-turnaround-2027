-- =====================================================================
-- 01_create_schema.sql
-- Nissan Turnaround 2027 - analytical data model (star schema, SQLite)
--
-- Layout
--   5 DIMENSION tables (dim_*)  : describe WHO / WHEN / WHERE / WHICH SOURCE
--   7 FACT tables      (fact_*) : store the measured numbers
--
-- Conventions
--   * snake_case names; money columns end in _bn (JPY billions);
--     volumes are in thousand units.
--   * Dates are stored as TEXT in ISO format 'YYYY-MM-DD'.
--   * A NULL measure means "not published in the sources used".
--   * Each fact table's GRAIN (what one row represents) is stated above it.
--
-- NOTE: SQLite does not enforce foreign keys unless every connection runs
--       PRAGMA foreign_keys = ON; (the Python scripts do this).
--
-- This script is safe to re-run: it drops and recreates everything.
-- =====================================================================

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- Drop existing objects (facts first, because they depend on dimensions)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS fact_ev_sales;
DROP TABLE IF EXISTS fact_usd_jpy;
DROP TABLE IF EXISTS fact_stock_prices;
DROP TABLE IF EXISTS fact_restructuring_targets;
DROP TABLE IF EXISTS fact_volumes;
DROP TABLE IF EXISTS fact_regional_results;
DROP TABLE IF EXISTS fact_group_financials;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_company;
DROP TABLE IF EXISTS dim_geography;
DROP TABLE IF EXISTS dim_period;
DROP TABLE IF EXISTS dim_source;

-- =====================================================================
-- DIMENSIONS
-- =====================================================================

-- Where each number comes from (data lineage). Fact tables keep the codes
-- in a source_ids text column, e.g. 'SR-FY2025;PR-FY2022'.
CREATE TABLE dim_source (
    source_id    TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    publisher    TEXT NOT NULL,
    url          TEXT NOT NULL,
    source_type  TEXT NOT NULL
                 CHECK (source_type IN ('primary', 'secondary', 'market_data')),
    accessed_on  TEXT NOT NULL
);

-- Reporting periods used in Nissan's results (fiscal years and quarters).
-- Nissan's fiscal year runs April to March: FY2025 = Apr 2025 - Mar 2026.
CREATE TABLE dim_period (
    period_id     TEXT PRIMARY KEY,                 -- e.g. 'FY2025', 'Q1_FY2026'
    period_label  TEXT NOT NULL,                    -- human-readable, for reports
    period_type   TEXT NOT NULL
                  CHECK (period_type IN ('FY', 'Q1', 'FY_FORECAST')),
    fiscal_year   INTEGER NOT NULL,
    period_start  TEXT NOT NULL,
    period_end    TEXT NOT NULL,
    is_forecast   INTEGER NOT NULL CHECK (is_forecast IN (0, 1)),
    sort_order    INTEGER NOT NULL,                 -- display order in Power BI
    CHECK (period_end > period_start),
    -- a period is a forecast if and only if its type says so
    CHECK ((period_type = 'FY_FORECAST') = (is_forecast = 1))
);

-- One geography dimension shared by several fact tables (a "conformed"
-- dimension). It has levels, and a parent link: USA belongs to North America.
CREATE TABLE dim_geography (
    geo_id           INTEGER PRIMARY KEY,
    geo_name         TEXT NOT NULL UNIQUE,
    geo_level        TEXT NOT NULL
                     CHECK (geo_level IN ('total', 'region', 'country',
                                          'segment', 'adjustment')),
    parent_geo_id    INTEGER REFERENCES dim_geography (geo_id),
    definition_note  TEXT
);

-- The companies whose share prices we track (Nissan and peers).
CREATE TABLE dim_company (
    company_id        INTEGER PRIMARY KEY,
    ticker            TEXT NOT NULL UNIQUE,         -- e.g. '7201.T'
    company_name      TEXT NOT NULL,
    is_focus_company  INTEGER NOT NULL CHECK (is_focus_company IN (0, 1))
);

-- Calendar table: one row per day, with Nissan's fiscal year attached so
-- daily data (share prices, FX) can be grouped by Nissan fiscal period.
CREATE TABLE dim_date (
    date_key               TEXT PRIMARY KEY,        -- 'YYYY-MM-DD'
    calendar_year          INTEGER NOT NULL,
    calendar_quarter       INTEGER NOT NULL CHECK (calendar_quarter BETWEEN 1 AND 4),
    calendar_month         INTEGER NOT NULL CHECK (calendar_month BETWEEN 1 AND 12),
    month_name             TEXT NOT NULL,
    day_of_week            INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),  -- 1 = Monday
    is_weekend             INTEGER NOT NULL CHECK (is_weekend IN (0, 1)),
    nissan_fiscal_year     INTEGER NOT NULL,        -- Apr-Mar year
    nissan_fiscal_quarter  INTEGER NOT NULL CHECK (nissan_fiscal_quarter BETWEEN 1 AND 4)
);

-- =====================================================================
-- FACTS
-- =====================================================================

-- GRAIN: one row per reporting period (group level).
CREATE TABLE fact_group_financials (
    period_id            TEXT PRIMARY KEY REFERENCES dim_period (period_id),
        net_sales_bn     REAL NOT NULL CHECK (net_sales_bn >0),
    operating_profit_bn  REAL NOT NULL,
    ordinary_income_bn   REAL,
    net_income_bn        REAL NOT NULL,
    total_assets_bn      REAL CHECK (total_assets_bn > 0),
    net_assets_bn        REAL,
    equity_ratio_pct     REAL CHECK (equity_ratio_pct BETWEEN 0 AND 100),
    cfo_bn               REAL,                       -- operating cash flow
    cfi_bn               REAL,                       -- investing cash flow
    cff_bn               REAL,                       -- financing cash flow
    cash_end_bn          REAL CHECK (cash_end_bn >= 0),
    capex_bn             REAL CHECK (capex_bn >= 0),
    depreciation_bn      REAL CHECK (depreciation_bn >= 0),
    rnd_bn               REAL CHECK (rnd_bn >= 0),
    usd_jpy_avg          REAL CHECK (usd_jpy_avg > 0),
    eur_jpy_avg          REAL CHECK (eur_jpy_avg > 0),
    source_ids           TEXT NOT NULL
);

-- GRAIN: one row per period and region (including the 'Eliminations' line).
CREATE TABLE fact_regional_results (
    period_id            TEXT    NOT NULL REFERENCES dim_period (period_id),
    geo_id               INTEGER NOT NULL REFERENCES dim_geography (geo_id),
    net_sales_bn         REAL    NOT NULL,
    operating_profit_bn  REAL    NOT NULL,
    source_ids           TEXT    NOT NULL,
    PRIMARY KEY (period_id, geo_id)
);

-- GRAIN: one row per period, volume metric and geography.
-- metric: retail_sales (to customers), production, wholesale (to dealers).
CREATE TABLE fact_volumes (
    period_id        TEXT    NOT NULL REFERENCES dim_period (period_id),
    metric           TEXT    NOT NULL
                     CHECK (metric IN ('retail_sales', 'production', 'wholesale')),
    geo_id           INTEGER NOT NULL REFERENCES dim_geography (geo_id),
    units_thousand   INTEGER NOT NULL CHECK (units_thousand >= 0),
    note             TEXT,
    source_ids       TEXT    NOT NULL,
    PRIMARY KEY (period_id, metric, geo_id)
);

-- GRAIN: one row per restructuring target or progress marker (Re:Nissan).
CREATE TABLE fact_restructuring_targets (
    metric_id    TEXT PRIMARY KEY,
    description  TEXT NOT NULL,
    value        REAL NOT NULL,
    unit         TEXT NOT NULL
                 CHECK (unit IN ('JPY_bn', 'count', 'thousand_units', 'employees')),
    as_of        TEXT NOT NULL,
    source_ids   TEXT NOT NULL
);

-- GRAIN: one row per trading day and company.
CREATE TABLE fact_stock_prices (
    date_key    TEXT    NOT NULL REFERENCES dim_date (date_key),
    company_id  INTEGER NOT NULL REFERENCES dim_company (company_id),
    close_jpy   REAL    NOT NULL CHECK (close_jpy > 0),
    volume      INTEGER NOT NULL CHECK (volume >= 0),
    PRIMARY KEY (date_key, company_id)
);
-- Speeds up "one company over time" queries (the primary key starts with date).
CREATE INDEX idx_fact_stock_prices_company ON fact_stock_prices (company_id, date_key);

-- GRAIN: one row per day (business days only) with the USD/JPY rate.
CREATE TABLE fact_usd_jpy (
    date_key  TEXT PRIMARY KEY REFERENCES dim_date (date_key),
    usd_jpy   REAL NOT NULL CHECK (usd_jpy > 0)
);

-- GRAIN: one row per country (or aggregate, e.g. 'World') and year.
-- country_code is NULL for aggregates that are not countries.
CREATE TABLE fact_ev_sales (
    country             TEXT    NOT NULL,
    country_code        TEXT,
    year                INTEGER NOT NULL CHECK (year BETWEEN 2000 AND 2100),
    electric_car_sales  REAL    NOT NULL CHECK (electric_car_sales >= 0),
    PRIMARY KEY (country, year)
);