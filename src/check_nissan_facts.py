"""
check_nissan_facts.py
=====================
Purpose : Prove that the four Nissan fact tables are correct.

          1. Row counts           - nothing lost, nothing duplicated
          2. Source vs database   - every value in every CSV equals the value
                                    now stored in the database (a "round trip")
          3. Business rules (SQL) - regions add up to the group total, volumes
                                    add up, blanks stayed NULL, links are valid
          4. First look           - the first real analysis queries

Usage   : python src/check_nissan_facts.py   (after load_nissan_facts.py)

Exit code: 0 if every check passes, 1 otherwise.
"""

import csv
import sys

from db_utils import RAW_DIR, connect

results = {"passed": 0, "failed": 0}


def check(ok: bool, message: str) -> None:
    """Print one PASS/FAIL line and update the counters."""
    print(f"[{'PASS' if ok else 'FAIL'}] {message}")
    results["passed" if ok else "failed"] += 1


def ask(connection, sql: str, parameters: tuple = ()) -> list:
    """Run a SQL question and return the answer rows."""
    return connection.execute(sql, parameters).fetchall()


def read_lines(file_name: str) -> list:
    """Read a raw CSV as a list of dictionaries (all values are still text)."""
    with open(RAW_DIR / file_name, newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def same_number(csv_text: str, database_value) -> bool:
    """A blank cell must be NULL; otherwise the numbers must match."""
    if csv_text.strip() == "":
        return database_value is None
    return database_value is not None and abs(float(csv_text) - database_value) < 1e-9


# ----------------------------------------------------------------------
# 1. Row counts
# ----------------------------------------------------------------------
def check_row_counts(connection) -> None:
    print("\n--- 1. ROW COUNTS ---")
    expected = {"fact_group_financials": 8, "fact_regional_results": 18,
                "fact_volumes": 58, "fact_restructuring_targets": 17}
    for table, wanted in expected.items():
        found = ask(connection, f"SELECT COUNT(*) FROM {table}")[0][0]
        check(found == wanted, f"{table}: {found} rows (expected {wanted})")


# ----------------------------------------------------------------------
# 2. Source versus database (the round trip)
# ----------------------------------------------------------------------
def check_group_roundtrip(connection) -> None:
    columns = ["net_sales_bn", "operating_profit_bn", "ordinary_income_bn",
               "net_income_bn", "total_assets_bn", "net_assets_bn", "equity_ratio_pct",
               "cfo_bn", "cfi_bn", "cff_bn", "cash_end_bn", "capex_bn",
               "depreciation_bn", "rnd_bn", "usd_jpy_avg", "eur_jpy_avg"]
    compared, differences = 0, []
    for line in read_lines("nissan_group_financials.csv"):
        stored = ask(connection,
                     f"SELECT {', '.join(columns)}, source_ids "
                     "FROM fact_group_financials WHERE period_id = ?",
                     (line["period_id"],))
        if not stored:
            differences.append(f"{line['period_id']}: missing in database")
            continue
        stored = stored[0]
        for column, value in zip(columns, stored[:-1]):
            compared += 1
            if not same_number(line[column], value):
                differences.append(f"{line['period_id']}.{column}")
        compared += 1
        if line["source_ids"] != stored[-1]:
            differences.append(f"{line['period_id']}.source_ids")
    check(not differences,
          f"fact_group_financials: {compared} values compared with the CSV, "
          f"{len(differences)} differences" + (f" {differences[:3]}" if differences else ""))


def check_regional_roundtrip(connection) -> None:
    stored = {(period, region): (sales, profit, source)
              for period, region, sales, profit, source in ask(
                  connection,
                  "SELECT r.period_id, g.geo_name, r.net_sales_bn, "
                  "r.operating_profit_bn, r.source_ids "
                  "FROM fact_regional_results AS r "
                  "JOIN dim_geography AS g ON g.geo_id = r.geo_id")}
    compared, differences = 0, []
    for line in read_lines("nissan_regional_results.csv"):
        key = (line["period_id"], line["region"])
        if key not in stored:
            differences.append(f"{key}: missing in database")
            continue
        sales, profit, source = stored[key]
        for text, value, name in [(line["net_sales_bn"], sales, "net_sales_bn"),
                                  (line["operating_profit_bn"], profit, "operating_profit_bn")]:
            compared += 1
            if not same_number(text, value):
                differences.append(f"{key}.{name}")
        compared += 1
        if line["source_ids"] != source:
            differences.append(f"{key}.source_ids")
    check(not differences,
          f"fact_regional_results: {compared} values compared with the CSV, "
          f"{len(differences)} differences" + (f" {differences[:3]}" if differences else ""))


def check_volume_roundtrip(connection) -> None:
    stored = {(period, metric, market): (units, note, source)
              for period, metric, market, units, note, source in ask(
                  connection,
                  "SELECT v.period_id, v.metric, g.geo_name, v.units_thousand, "
                  "v.note, v.source_ids "
                  "FROM fact_volumes AS v "
                  "JOIN dim_geography AS g ON g.geo_id = v.geo_id")}
    compared, differences = 0, []
    for line in read_lines("nissan_volumes.csv"):
        key = (line["period_id"], line["metric"], line["market"])
        if key not in stored:
            differences.append(f"{key}: missing in database")
            continue
        units, note, source = stored[key]
        compared += 3
        if not same_number(line["units_thousand"], units):
            differences.append(f"{key}.units_thousand")
        if (line["note"] or None) != note:
            differences.append(f"{key}.note")
        if line["source_ids"] != source:
            differences.append(f"{key}.source_ids")
    check(not differences,
          f"fact_volumes: {compared} values compared with the CSV, "
          f"{len(differences)} differences" + (f" {differences[:3]}" if differences else ""))


def check_target_roundtrip(connection) -> None:
    stored = {metric: (description, value, unit, as_of, source)
              for metric, description, value, unit, as_of, source in ask(
                  connection,
                  "SELECT metric_id, description, value, unit, as_of, source_ids "
                  "FROM fact_restructuring_targets")}
    compared, differences = 0, []
    for line in read_lines("nissan_restructuring_targets.csv"):
        if line["metric_id"] not in stored:
            differences.append(f"{line['metric_id']}: missing in database")
            continue
        description, value, unit, as_of, source = stored[line["metric_id"]]
        compared += 5
        if line["description"] != description:
            differences.append(f"{line['metric_id']}.description")
        if not same_number(line["value"], value):
            differences.append(f"{line['metric_id']}.value")
        if line["unit"] != unit:
            differences.append(f"{line['metric_id']}.unit")
        if line["as_of"] != as_of:
            differences.append(f"{line['metric_id']}.as_of")
        if line["source_ids"] != source:
            differences.append(f"{line['metric_id']}.source_ids")
    check(not differences,
          f"fact_restructuring_targets: {compared} values compared with the CSV, "
          f"{len(differences)} differences" + (f" {differences[:3]}" if differences else ""))


# ----------------------------------------------------------------------
# 3. Business rules, checked with SQL
# ----------------------------------------------------------------------
def check_business_rules(connection) -> None:
    print("\n--- 3. BUSINESS RULES (asked in SQL) ---")

    # Regions plus eliminations must add up to the group total.
    rows = ask(connection,
               "SELECT r.period_id, SUM(r.net_sales_bn), g.net_sales_bn, "
               "SUM(r.operating_profit_bn), g.operating_profit_bn "
               "FROM fact_regional_results AS r "
               "JOIN fact_group_financials AS g ON g.period_id = r.period_id "
               "GROUP BY r.period_id ORDER BY r.period_id")
    for period, sales_sum, sales_group, profit_sum, profit_group in rows:
        check(abs(sales_sum - sales_group) <= 0.5 and abs(profit_sum - profit_group) <= 0.5,
              f"{period}: regions add up to the group "
              f"(sales {sales_sum:.1f} vs {sales_group:.1f}, "
              f"profit {profit_sum:.1f} vs {profit_group:.1f})")

    # Volumes: the regions must add up to the 'Total' row (rounding allowed).
    rows = ask(connection,
               "SELECT v.period_id, v.metric, "
               "SUM(CASE WHEN g.geo_level IN ('region', 'segment') THEN v.units_thousand END), "
               "SUM(CASE WHEN g.geo_level = 'total' THEN v.units_thousand END) "
               "FROM fact_volumes AS v JOIN dim_geography AS g ON g.geo_id = v.geo_id "
               "WHERE v.period_id <> 'FY2026F' "
               "GROUP BY v.period_id, v.metric ORDER BY v.metric, v.period_id")
    bad = [(p, m, parts, total) for p, m, parts, total in rows if abs(parts - total) > 2]
    check(len(rows) == 9 and not bad,
          f"volumes: {len(rows)} period/metric groups, regions add up to totals"
          + (f" {bad}" if bad else ""))

    # Blanks in the CSV must have stayed NULL (not turned into 0).
    nulls = ask(connection,
                "SELECT (SELECT ordinary_income_bn FROM fact_group_financials WHERE period_id = 'FY2026F'), "
                "(SELECT capex_bn FROM fact_group_financials WHERE period_id = 'FY2021')")[0]
    check(nulls == (None, None),
          "blank cells stayed NULL (FY2026F ordinary income, FY2021 capex)")

    # Every foreign key link must point to a row that exists.
    broken = ask(connection, "PRAGMA foreign_key_check")
    check(broken == [], f"no broken links between tables ({len(broken)} found)")

    # The forecast-only place must not appear in any actual period.
    misuse = ask(connection,
                 "SELECT COUNT(*) FROM fact_volumes AS v "
                 "JOIN dim_geography AS g ON g.geo_id = v.geo_id "
                 "WHERE g.geo_name = 'Others incl. Asia ex-China' "
                 "AND v.period_id <> 'FY2026F'")[0][0]
    check(misuse == 0, "'Others incl. Asia ex-China' is used only in the FY2026 forecast")

    # Every source code used by a fact row exists in dim_source.
    known = {row[0] for row in ask(connection, "SELECT source_id FROM dim_source")}
    used = set()
    for table in ["fact_group_financials", "fact_regional_results",
                  "fact_volumes", "fact_restructuring_targets"]:
        for (codes,) in ask(connection, f"SELECT source_ids FROM {table}"):
            used.update(code.strip() for code in codes.split(";"))
    check(used <= known, f"all {len(used)} source codes used in the facts exist in dim_source")


# ----------------------------------------------------------------------
# 4. First look at the data
# ----------------------------------------------------------------------
def show_first_look(connection) -> None:
    print("\n--- 4. FIRST LOOK (our first real SQL questions) ---")

    print("\nQuestion 1: how profitable is Nissan, period by period?")
    print(f"{'period':<11}{'sales (bn)':>12}{'profit (bn)':>13}{'margin %':>10}")
    for period, sales, profit, margin in ask(
            connection,
            "SELECT p.period_id, g.net_sales_bn, g.operating_profit_bn, "
            "ROUND(g.operating_profit_bn * 100.0 / g.net_sales_bn, 1) "
            "FROM fact_group_financials AS g "
            "JOIN dim_period AS p ON p.period_id = g.period_id "
            "ORDER BY p.sort_order"):
        print(f"{period:<11}{sales:>12,.1f}{profit:>13,.1f}{margin:>10.1f}")

    print("\nQuestion 2: which region earned or lost the most in FY2025?")
    print(f"{'region':<16}{'operating profit (bn)':>24}")
    for region, profit in ask(
            connection,
            "SELECT g.geo_name, r.operating_profit_bn "
            "FROM fact_regional_results AS r "
            "JOIN dim_geography AS g ON g.geo_id = r.geo_id "
            "WHERE r.period_id = 'FY2025' AND g.geo_name <> 'Eliminations' "
            "ORDER BY r.operating_profit_bn DESC"):
        print(f"{region:<16}{profit:>24,.1f}")


def main() -> int:
    print("=" * 66)
    print("NISSAN TURNAROUND 2027 - CHECK NISSAN FACT TABLES")
    print("=" * 66)

    try:
        connection = connect()
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        return 1

    check_row_counts(connection)
    print("\n--- 2. SOURCE VERSUS DATABASE (every value compared) ---")
    check_group_roundtrip(connection)
    check_regional_roundtrip(connection)
    check_volume_roundtrip(connection)
    check_target_roundtrip(connection)
    check_business_rules(connection)
    show_first_look(connection)
    connection.close()

    print("\n" + "=" * 66)
    print(f"Checks passed: {results['passed']} | failed: {results['failed']}")
    if results["failed"]:
        print("RESULT: FAILED. Read the [FAIL] lines above.")
        return 1
    print("RESULT: ALL CHECKS PASSED. Nissan facts match the raw files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())