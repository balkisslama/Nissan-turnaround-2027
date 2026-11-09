-- =====================================================================
-- 03_regions.sql
-- Step 5B: Where does Nissan make money, and where does it lose it?
--
-- "segment margin" = a region's operating profit / that region's net sales.
-- Regional sales include sales between Nissan's own regions (removed on the
-- 'Eliminations' line), so segment margins are a guide, not an exact figure.
-- =====================================================================

-- QUERY q06_region_profit
-- QUESTION: How much does each region earn, and how profitable is it per yen of sales?
-- HOW IT WORKS: JOIN attaches the period and region names to each fact row.
--   The 'Eliminations' line is left out because it is not a real region.
SELECT
    p.period_id,
    g.geo_name                                                AS region,
    r.net_sales_bn,
    r.operating_profit_bn,
    ROUND(r.operating_profit_bn * 100.0 / r.net_sales_bn, 1)  AS segment_margin_pct
FROM fact_regional_results AS r
JOIN dim_period    AS p ON p.period_id = r.period_id
JOIN dim_geography AS g ON g.geo_id    = r.geo_id
WHERE g.geo_name <> 'Eliminations'
ORDER BY p.sort_order, r.operating_profit_bn DESC;

-- QUERY q07_q1_profit_swing_by_region
-- QUESTION: Which regions explain the jump in profit between Q1 FY2025 and Q1 FY2026?
-- HOW IT WORKS: "CASE WHEN period = X THEN profit END" picks out one
--   period's profit, so SUM(...) turns two rows per region into two
--   COLUMNS (a "pivot"). WITH ... AS (...) names that first result so the
--   final SELECT can reuse it.
WITH swing AS (
    SELECT
        g.geo_name AS region,
        SUM(CASE WHEN r.period_id = 'Q1_FY2025' THEN r.operating_profit_bn END) AS profit_q1_fy2025,
        SUM(CASE WHEN r.period_id = 'Q1_FY2026' THEN r.operating_profit_bn END) AS profit_q1_fy2026
    FROM fact_regional_results AS r
    JOIN dim_geography AS g ON g.geo_id = r.geo_id
    GROUP BY g.geo_name
)
SELECT
    region,
    profit_q1_fy2025,
    profit_q1_fy2026,
    ROUND(profit_q1_fy2026 - profit_q1_fy2025, 1)             AS change_bn,
    ROUND((profit_q1_fy2026 - profit_q1_fy2025) * 100.0
          / (SELECT SUM(profit_q1_fy2026 - profit_q1_fy2025) FROM swing), 1)
                                                              AS share_of_group_change_pct
FROM swing
ORDER BY change_bn DESC;

-- QUERY q08_loss_making_regions
-- QUESTION: In each period, how many regions lose money, how much, and which ones?
-- HOW IT WORKS: the inner SELECT keeps only regions with a negative profit
--   (sorted by name); GROUP_CONCAT then glues their names into one text.
SELECT
    p.period_id,
    COUNT(*)                                                  AS loss_making_regions,
    ROUND(SUM(losses.operating_profit_bn), 1)                 AS combined_loss_bn,
    GROUP_CONCAT(losses.geo_name, ', ')                       AS which_regions
FROM (
    SELECT r.period_id, g.geo_name, r.operating_profit_bn
    FROM fact_regional_results AS r
    JOIN dim_geography AS g ON g.geo_id = r.geo_id
    WHERE g.geo_name <> 'Eliminations' AND r.operating_profit_bn < 0
    ORDER BY g.geo_name
) AS losses
JOIN dim_period AS p ON p.period_id = losses.period_id
GROUP BY p.period_id
ORDER BY p.sort_order;