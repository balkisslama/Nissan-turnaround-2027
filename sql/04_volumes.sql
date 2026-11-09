-- =====================================================================
-- 04_volumes.sql
-- Step 5C: How many cars does Nissan sell, and where is volume going?
--
-- Volumes are in thousand vehicles. "Retail" = sold to customers (includes
-- the China joint venture); "wholesale" = shipped to dealers on Nissan's
-- consolidated basis (the China joint venture is NOT included).
-- =====================================================================

-- QUERY q09_q1_retail_change_by_market
-- QUESTION: In which markets did Nissan sell more or fewer cars in Q1 FY2026 than a year earlier?
-- HOW IT WORKS: the same CASE WHEN "pivot" idea as q07. Totals are listed
--   first, then regions, then single countries (which are PART of regions).
WITH q AS (
    SELECT
        g.geo_name  AS market,
        g.geo_level AS level,
        SUM(CASE WHEN v.period_id = 'Q1_FY2025' THEN v.units_thousand END) AS q1_fy2025,
        SUM(CASE WHEN v.period_id = 'Q1_FY2026' THEN v.units_thousand END) AS q1_fy2026
    FROM fact_volumes AS v
    JOIN dim_geography AS g ON g.geo_id = v.geo_id
    WHERE v.metric = 'retail_sales' AND v.period_id IN ('Q1_FY2025', 'Q1_FY2026')
    GROUP BY g.geo_name, g.geo_level
)
SELECT
    market,
    level,
    q1_fy2025,
    q1_fy2026,
    q1_fy2026 - q1_fy2025                                     AS change_thousand,
    ROUND((q1_fy2026 * 1.0 / q1_fy2025 - 1) * 100, 1)         AS change_pct
FROM q
ORDER BY CASE level WHEN 'total' THEN 0 WHEN 'region' THEN 1 ELSE 2 END,
         change_thousand;

-- QUERY q10_retail_mix_fy2025
-- QUESTION: What share of Nissan's worldwide retail sales comes from each region and country (FY2025)?
-- HOW IT WORKS: a "subquery" (a question inside the question, in brackets)
--   finds the worldwide total, and each market is divided by it.
SELECT
    g.geo_name                                                AS market,
    g.geo_level                                               AS level,
    v.units_thousand,
    ROUND(v.units_thousand * 100.0 / (
        SELECT v2.units_thousand
        FROM fact_volumes AS v2
        JOIN dim_geography AS g2 ON g2.geo_id = v2.geo_id
        WHERE v2.period_id = 'FY2025' AND v2.metric = 'retail_sales'
          AND g2.geo_level = 'total'), 1)                     AS share_of_global_pct
FROM fact_volumes AS v
JOIN dim_geography AS g ON g.geo_id = v.geo_id
WHERE v.period_id = 'FY2025' AND v.metric = 'retail_sales'
  AND g.geo_level IN ('region', 'country')
ORDER BY CASE g.geo_level WHEN 'region' THEN 0 ELSE 1 END, v.units_thousand DESC;

-- QUERY q11_forecast_vs_actual_volume
-- QUESTION: Where does Nissan expect volume to rise or fall in FY2026, compared with FY2025?
-- HOW IT WORKS: Nissan's forecast groups "Asia outside China" together with
--   "Others", but its actual figures do not. To compare fairly, we rebuild
--   the actual FY2025 figure as Asia + Others - China. UNION ALL stacks
--   several result lists on top of each other.
WITH retail AS (
    SELECT v.period_id, g.geo_name AS market, v.units_thousand AS units
    FROM fact_volumes AS v
    JOIN dim_geography AS g ON g.geo_id = v.geo_id
    WHERE v.metric = 'retail_sales'
),
comparable AS (
    SELECT period_id, market, units
    FROM retail
    WHERE market IN ('Japan', 'North America', 'Europe', 'China', 'Total')
    UNION ALL
    SELECT 'FY2025', 'Rest of world (Asia ex-China + Others)',
           SUM(CASE WHEN market IN ('Asia', 'Others') THEN units ELSE -units END)
    FROM retail
    WHERE period_id = 'FY2025' AND market IN ('Asia', 'Others', 'China')
    UNION ALL
    SELECT period_id, 'Rest of world (Asia ex-China + Others)', units
    FROM retail
    WHERE market = 'Others incl. Asia ex-China'
),
side_by_side AS (
    SELECT
        market,
        MAX(CASE WHEN period_id = 'FY2025'  THEN units END) AS fy2025_actual,
        MAX(CASE WHEN period_id = 'FY2026F' THEN units END) AS fy2026_forecast
    FROM comparable
    WHERE period_id IN ('FY2025', 'FY2026F')
    GROUP BY market
)
SELECT
    market,
    fy2025_actual,
    fy2026_forecast,
    fy2026_forecast - fy2025_actual                           AS change_thousand,
    CASE WHEN ABS(fy2026_forecast * 1.0 / fy2025_actual - 1) < 0.0005 THEN 0.0
         ELSE ROUND((fy2026_forecast * 1.0 / fy2025_actual - 1) * 100, 1) END AS change_pct
FROM side_by_side
ORDER BY CASE market WHEN 'Total' THEN 1 ELSE 0 END, fy2025_actual DESC;

-- QUERY q12_revenue_per_vehicle
-- QUESTION: How much revenue does Nissan earn per vehicle shipped, and how did the yen move?
-- HOW IT WORKS: JPY billions divided by thousand vehicles = JPY millions per
--   vehicle. Caution: revenue also includes parts, services and finance, and
--   a weaker yen raises yen revenue without any real price increase.
SELECT
    p.period_id,
    g.net_sales_bn,
    w.units_thousand                                          AS wholesale_thousand,
    ROUND(g.net_sales_bn / w.units_thousand, 2)               AS revenue_per_vehicle_million_yen,
    g.usd_jpy_avg,
    g.eur_jpy_avg
FROM fact_group_financials AS g
JOIN dim_period    AS p  ON p.period_id = g.period_id
JOIN fact_volumes  AS w  ON w.period_id = g.period_id AND w.metric = 'wholesale'
JOIN dim_geography AS wg ON wg.geo_id = w.geo_id AND wg.geo_level = 'total'
ORDER BY p.sort_order;