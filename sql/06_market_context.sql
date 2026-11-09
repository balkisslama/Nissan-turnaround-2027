-- =====================================================================
-- 06_market_context.sql
-- Step 5E: What do the yen and the stock market tell us?
--
-- Fiscal year FY2017 is left out (our data only has Jan-Mar 2018 for it).
-- The latest fiscal year is only partly over, so its "days" figure is smaller.
-- =====================================================================

-- QUERY q16_yen_vs_nissan_assumption
-- QUESTION: Does the real market yen rate match the rate Nissan used in its own reports?
-- HOW IT WORKS: AVG() over every day of a fiscal year gives the market
--   average; Nissan's own average comes from fact_group_financials. LEFT JOIN
--   keeps years where Nissan published no rate (they show an empty cell).
SELECT
    'FY' || d.nissan_fiscal_year                              AS fiscal_year,
    ROUND(AVG(f.usd_jpy), 1)                                  AS market_avg_usd_jpy,
    MAX(n.usd_jpy_avg)                                        AS nissan_assumed_usd_jpy,
    ROUND(AVG(f.usd_jpy) - MAX(n.usd_jpy_avg), 1)             AS difference,
    COUNT(*)                                                  AS days_in_data
FROM fact_usd_jpy AS f
JOIN dim_date AS d ON d.date_key = f.date_key
LEFT JOIN (
    SELECT p.fiscal_year, g.usd_jpy_avg
    FROM fact_group_financials AS g
    JOIN dim_period AS p ON p.period_id = g.period_id
    WHERE p.period_type = 'FY'
) AS n ON n.fiscal_year = d.nissan_fiscal_year
WHERE d.nissan_fiscal_year >= 2018
GROUP BY d.nissan_fiscal_year
ORDER BY d.nissan_fiscal_year;

-- QUERY q17_share_price_by_fiscal_year
-- QUESTION: In each fiscal year, did Nissan's share price do better or worse than its four Japanese rivals?
-- HOW IT WORKS: step 1 (bounds) finds each company's first and last trading
--   day in each fiscal year; step 2 (returns) looks up the closing prices
--   on those two days; the final SELECT compares Nissan with the AVERAGE of
--   the four rivals. Return = last close / first close - 1 (adjusted prices).
WITH bounds AS (
    SELECT s.company_id,
           d.nissan_fiscal_year AS fy,
           MIN(s.date_key)      AS first_day,
           MAX(s.date_key)      AS last_day,
           COUNT(*)             AS trading_days
    FROM fact_stock_prices AS s
    JOIN dim_date AS d ON d.date_key = s.date_key
    WHERE d.nissan_fiscal_year >= 2018
    GROUP BY s.company_id, d.nissan_fiscal_year
),
returns AS (
    SELECT b.company_id, b.fy, b.trading_days,
           (SELECT s.close_jpy FROM fact_stock_prices AS s
             WHERE s.company_id = b.company_id AND s.date_key = b.first_day) AS first_close,
           (SELECT s.close_jpy FROM fact_stock_prices AS s
             WHERE s.company_id = b.company_id AND s.date_key = b.last_day)  AS last_close
    FROM bounds AS b
)
SELECT
    'FY' || r.fy                                              AS fiscal_year,
    ROUND(MAX(CASE WHEN c.company_name = 'Nissan'
                   THEN (r.last_close / r.first_close - 1) * 100 END), 1) AS nissan_return_pct,
    ROUND(AVG(CASE WHEN c.company_name <> 'Nissan'
                   THEN (r.last_close / r.first_close - 1) * 100 END), 1) AS rivals_avg_return_pct,
    ROUND(MAX(CASE WHEN c.company_name = 'Nissan'
                   THEN (r.last_close / r.first_close - 1) * 100 END)
        - AVG(CASE WHEN c.company_name <> 'Nissan'
                   THEN (r.last_close / r.first_close - 1) * 100 END), 1) AS nissan_minus_rivals_pts,
    MAX(r.trading_days)                                       AS trading_days
FROM returns AS r
JOIN dim_company AS c ON c.company_id = r.company_id
GROUP BY r.fy
ORDER BY r.fy;