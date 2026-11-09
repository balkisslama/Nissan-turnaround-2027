-- =====================================================================
-- 05_restructuring.sql
-- Step 5D: What did Nissan promise in its recovery plan (Re:Nissan), and how far has it got?
--
-- The restructuring figures are stored one per row in fact_restructuring_targets.
-- "Pivoting" turns them into one wide row so we can calculate with them.
-- =====================================================================

-- QUERY q13_restructuring_plan
-- QUESTION: What does the Re:Nissan plan change in plants, capacity and product range, and how did the volume outlook move?
-- HOW IT WORKS: MAX(CASE WHEN metric_id = 'x' THEN value END) picks out one
--   named figure. UNION ALL stacks one result row per topic.
WITH t AS (
    SELECT
        MAX(CASE WHEN metric_id = 'plants_before'                  THEN value END) AS plants_before,
        MAX(CASE WHEN metric_id = 'plants_target'                  THEN value END) AS plants_target,
        MAX(CASE WHEN metric_id = 'capacity_before'                THEN value END) AS capacity_before,
        MAX(CASE WHEN metric_id = 'capacity_target'                THEN value END) AS capacity_target,
        MAX(CASE WHEN metric_id = 'models_before'                  THEN value END) AS models_before,
        MAX(CASE WHEN metric_id = 'models_target'                  THEN value END) AS models_target,
        MAX(CASE WHEN metric_id = 'volume_outlook_original_fy2026' THEN value END) AS volume_original,
        MAX(CASE WHEN metric_id = 'volume_outlook_revised_fy2026'  THEN value END) AS volume_revised
    FROM fact_restructuring_targets
)
SELECT 1 AS step, 'Production plants (count)' AS item,
       plants_before AS before_value, plants_target AS after_value,
       plants_target - plants_before AS change,
       ROUND((plants_target / plants_before - 1) * 100, 1) AS change_pct,
       'target for end of FY2027' AS note
FROM t
UNION ALL
SELECT 2, 'Production capacity (thousand units, excl. China)',
       capacity_before, capacity_target, capacity_target - capacity_before,
       ROUND((capacity_target / capacity_before - 1) * 100, 1),
       'target for end of FY2027'
FROM t
UNION ALL
SELECT 3, 'Product models (count)',
       models_before, models_target, models_target - models_before,
       ROUND((models_target / models_before - 1) * 100, 1),
       'target'
FROM t
UNION ALL
SELECT 4, 'FY2026 retail volume outlook (thousand units)',
       volume_original, volume_revised, volume_revised - volume_original,
       ROUND((volume_revised / volume_original - 1) * 100, 1),
       'cut announced 3 Aug 2026'
FROM t
ORDER BY step;

-- QUERY q14_progress_so_far
-- QUESTION: How much of the promised cost savings and job cuts has Nissan achieved?
-- HOW IT WORKS: achieved / target. Headcount uses consolidated employees
--   at the end of FY2024 and FY2025, which is only a rough guide to the
--   announced 20,000 job cuts.
WITH t AS (
    SELECT
        MAX(CASE WHEN metric_id = 'cost_savings_target'           THEN value END) AS savings_target,
        MAX(CASE WHEN metric_id = 'fixed_cost_savings_fy2025'     THEN value END) AS fixed_savings,
        MAX(CASE WHEN metric_id = 'variable_cost_savings_fy2025'  THEN value END) AS variable_savings,
        MAX(CASE WHEN metric_id = 'workforce_reduction_target'    THEN value END) AS job_target,
        MAX(CASE WHEN metric_id = 'employees_fy2024'              THEN value END) AS employees_before,
        MAX(CASE WHEN metric_id = 'employees_fy2025'              THEN value END) AS employees_after
    FROM fact_restructuring_targets
)
SELECT 'Cost savings vs FY2024 (JPY bn)' AS item,
       savings_target AS target,
       fixed_savings + variable_savings AS achieved,
       ROUND((fixed_savings + variable_savings) * 100.0 / savings_target, 1) AS progress_pct,
       'fixed + variable, achieved by end of FY2025' AS note
FROM t
UNION ALL
SELECT 'Workforce reduction (employees)',
       job_target,
       employees_before - employees_after,
       ROUND((employees_before - employees_after) * 100.0 / job_target, 1),
       'fall in consolidated headcount FY2024 to FY2025 (rough guide)'
FROM t;

-- QUERY q15_profit_bridge_fy2024_to_fy2025
-- QUESTION: Cost savings were large, yet operating profit did not rise. What else must have moved?
-- HOW IT WORKS: a "bridge". Start from FY2024 profit, add the savings Nissan
--   reports, and the leftover difference to the real FY2025 profit is the
--   IMPLIED effect of everything else (volume, mix, currency, tariffs,
--   other costs). Nissan does not report that figure; we infer it, and we
--   assume the savings are measured against the FY2024 baseline, as Nissan
--   states for its JPY 500 billion target.
WITH base AS (
    SELECT
        (SELECT operating_profit_bn FROM fact_group_financials WHERE period_id = 'FY2024') AS op_fy2024,
        (SELECT operating_profit_bn FROM fact_group_financials WHERE period_id = 'FY2025') AS op_fy2025,
        (SELECT value FROM fact_restructuring_targets WHERE metric_id = 'fixed_cost_savings_fy2025')
      + (SELECT value FROM fact_restructuring_targets WHERE metric_id = 'variable_cost_savings_fy2025') AS savings
)
SELECT 1 AS step, 'Operating profit FY2024' AS item, op_fy2024 AS amount_bn FROM base
UNION ALL
SELECT 2, 'Cost savings delivered (fixed + variable)', savings FROM base
UNION ALL
SELECT 3, 'IMPLIED effect of everything else (volume, mix, FX, tariffs, other costs)',
       ROUND(op_fy2025 - op_fy2024 - savings, 1) FROM base
UNION ALL
SELECT 4, 'Operating profit FY2025', op_fy2025 FROM base
ORDER BY step;