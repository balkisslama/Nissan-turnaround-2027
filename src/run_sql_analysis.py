"""
run_sql_analysis.py
===================
Purpose : Run the SQL analysis queries stored in sql/02_*.sql ... sql/06_*.sql,
          print each answer as a table, and save it as a CSV file in
          reports/tables/ (ready for Excel and Power BI).

          Each query in those files starts with two comment lines:
              -- QUERY q01_profit_trend
              -- QUESTION: <the business question in plain English>
          and ends with a semicolon.

Usage   : python src/run_sql_analysis.py          (run every query)
          python src/run_sql_analysis.py q07      (run only queries whose
                                                   name starts with q07)

Exit code: 0 if every selected query ran, 1 otherwise.
"""

import re
import sqlite3
import sys

import pandas as pd

from db_utils import PROJECT_ROOT, connect

SQL_DIR = PROJECT_ROOT / "sql"
OUTPUT_DIR = PROJECT_ROOT / "reports" / "tables"

# A line like "-- QUERY q01_profit_trend" starts a new query.
QUERY_MARKER = re.compile(r"^-- QUERY (\S+)[ \t]*$", re.MULTILINE)


def load_queries() -> list:
    """Read every analysis .sql file and split it into separate queries."""
    queries = []
    for path in sorted(SQL_DIR.glob("0[2-9]_*.sql")):
        parts = QUERY_MARKER.split(path.read_text(encoding="utf-8"))
        # parts = [text before the first query, name1, body1, name2, body2, ...]
        for index in range(1, len(parts), 2):
            name, body = parts[index], parts[index + 1]
            question = ""
            for line in body.splitlines():
                if line.startswith("-- QUESTION:"):
                    question = line[len("-- QUESTION:"):].strip()
            queries.append({"name": name, "question": question,
                            "sql": body.strip(), "file": path.name})
    return queries


def run_query(connection, query: dict) -> pd.DataFrame:
    """Run one query and return its answer as a table (a pandas DataFrame)."""
    return pd.read_sql(query["sql"], connection)


def main() -> int:
    wanted = sys.argv[1:]
    try:
        connection = connect()
    except FileNotFoundError as error:
        print(f"[STOP] {error}")
        return 1

    queries = [q for q in load_queries()
               if not wanted or any(q["name"].startswith(w) for w in wanted)]
    if not queries:
        print(f"[STOP] No query matches {wanted}. Names look like q01_profit_trend.")
        connection.close()
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = 0
    for query in queries:
        print("=" * 72)
        print(f"{query['name']}   ({query['file']})")
        print(f"QUESTION: {query['question']}")
        print("-" * 72)
        try:
            table = run_query(connection, query)
        except (sqlite3.Error, pd.errors.DatabaseError) as error:
            failures += 1
            print(f"[FAIL] {error}")
            continue
        print(table.to_string(index=False, na_rep=""))
        table.to_csv(OUTPUT_DIR / f"{query['name']}.csv", index=False)
    connection.close()

    print("=" * 72)
    done = len(queries) - failures
    print(f"{done} of {len(queries)} queries ran; tables saved in reports/tables/")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())