-- =====================================================================
-- 02_profitability.sql
-- Step 5A: Is Nissan making money, and is the profit "real"?
--
-- Each query starts with a "-- QUERY name" line and a "-- QUESTION:" line
-- (the question in plain English). The runner script src/run_sql_analysis.py
-- reads these lines, runs the SQL below them and saves the result.
-- Money is in JPY billions (bn). "FY2025" = April 2025 to March 2026.
-- =====================================================================

-- QUERY q01_profit_trend
-- QUESTION: How did sales, operating profit and the profit margin change from year to year?
-- HOW IT WORKS: LAG(x) OVER (ORDER BY year) fetches the value of x from the
--   PREVIOUS row, so we can compare each year with the year before it.
SELECT
    p.period_id,
    p.is_forecast,
    g.net_sales_bn,
    g.operating_profit_bn,
    ROUND(g.operating_profit_bn * 100.0 / g.net_sales_bn, 1)  AS operating_margin_pct,
    ROUND((g.net_sales_bn / LAG(g.net_sales_bn) OVER (ORDER BY p.fiscal_year) - 1) * 100, 1)
                                                              AS sales_growth_pct,
    ROUND((g.operating_profit_bn / LAG(g.operating_profit_bn) OVER (ORDER BY p.fiscal_year) - 1) * 100, 1)
                                                              AS profit_growth_pct
FROM fact_group_financials AS g
JOIN dim_period AS p ON p.period_id = g.period_id
WHERE p.period_type IN ('FY', 'FY_FORECAST')
ORDER BY p.fiscal_year;

-- QUERY q02_operating_vs_net_profit
-- QUESTION: How far is the final profit (net income) from what the business itself earns (operating profit)?
-- HOW IT WORKS: a simple subtraction. A big negative gap means large costs
--   outside normal operations (restructuring, write-downs, taxes...).
SELECT
    p.period_id,
    g.operating_profit_bn,
    g.ordinary_income_bn,
    g.net_income_bn,
    ROUND(g.net_income_bn - g.operating_profit_bn, 1)         AS gap_bn
FROM fact_group_financials AS g
JOIN dim_period AS p ON p.period_id = g.period_id
WHERE p.period_type = 'FY'
ORDER BY p.fiscal_year;

-- QUERY q03_cash_flow
-- QUESTION: Is Nissan generating cash, or burning it?
-- HOW IT WORKS: "simple free cash flow" = cash from operations + cash from
--   investing. Caution: these are CONSOLIDATED figures, which include the
--   car-loan (sales finance) business, so they differ from Nissan's
--   "automotive free cash flow".
SELECT
    p.period_id,
    g.cfo_bn                                                  AS cash_from_operations_bn,
    g.cfi_bn                                                  AS cash_from_investing_bn,
    ROUND(g.cfo_bn + g.cfi_bn, 1)                             AS simple_free_cash_flow_bn,
    g.cff_bn                                                  AS cash_from_financing_bn,
    g.cash_end_bn,
    ROUND(g.cash_end_bn - LAG(g.cash_end_bn) OVER (ORDER BY p.fiscal_year), 1)
                                                              AS cash_change_bn
FROM fact_group_financials AS g
JOIN dim_period AS p ON p.period_id = g.period_id
WHERE p.period_type = 'FY' AND g.cfo_bn IS NOT NULL
ORDER BY p.fiscal_year;

-- QUERY q04_balance_sheet_strength
-- QUESTION: Is Nissan's financial cushion (equity ratio) growing or shrinking?
-- HOW IT WORKS: equity ratio = net assets / total assets. LAG gives last
--   year's ratio so we can show the change in percentage POINTS.
SELECT
    p.period_id,
    g.total_assets_bn,
    g.net_assets_bn,
    g.equity_ratio_pct,
    ROUND(g.equity_ratio_pct - LAG(g.equity_ratio_pct) OVER (ORDER BY p.fiscal_year), 1)
                                                              AS change_in_points
FROM fact_group_financials AS g
JOIN dim_period AS p ON p.period_id = g.period_id
WHERE p.period_type = 'FY' AND g.total_assets_bn IS NOT NULL
ORDER BY p.fiscal_year;

-- QUERY q05_investment_intensity
-- QUESTION: How much does Nissan spend on R&D and on plants and equipment, relative to its sales?
-- HOW IT WORKS: ratios. capex / depreciation above 1 means Nissan invests
--   more than its equipment wears out. Only periods that publish these
--   figures appear.
SELECT
    p.period_id,
    g.net_sales_bn,
    g.rnd_bn,
    ROUND(g.rnd_bn * 100.0 / g.net_sales_bn, 1)               AS rnd_pct_of_sales,
    g.capex_bn,
    ROUND(g.capex_bn * 100.0 / g.net_sales_bn, 1)             AS capex_pct_of_sales,
    g.depreciation_bn,
    ROUND(g.capex_bn / g.depreciation_bn, 2)                  AS capex_to_depreciation
FROM fact_group_financials AS g
JOIN dim_period AS p ON p.period_id = g.period_id
WHERE g.rnd_bn IS NOT NULL
ORDER BY p.sort_order;