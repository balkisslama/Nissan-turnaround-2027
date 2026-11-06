# ETL Notes: how the database is built and cleaned

ETL = Extract (read the raw files), Transform (clean and prepare), Load (insert
into the database). Run everything with one command:

    python src/run_etl.py

The database (`data/processed/nissan.db`) is deleted and rebuilt on every run,
so results are always reproducible from the raw files. Raw files are never
modified.

## Pipeline order

| Step | Script                 | What it does                                                  |
| ---- | ---------------------- | ------------------------------------------------------------- |
| 1    | `create_database.py`   | Builds the empty database from `sql/01_create_schema.sql`     |
| 2    | `load_dimensions.py`   | Loads sources, periods, geography, companies and the calendar |
| 3    | `load_nissan_facts.py` | Loads Nissan's group, regional, volume and target tables      |
| 4    | `load_market_data.py`  | Loads share prices, USD/JPY and EV sales                      |
| 5-7  | `check_*.py`           | Verify each group of tables against the raw files             |

Dimensions load before facts because every fact row points to a dimension row.

## Cleaning rules

| #   | Rule                                                                        | Applies to                      | Reason                                                                                                                                                                  |
| --- | --------------------------------------------------------------------------- | ------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Blank cells become NULL, never 0                                            | Nissan files                    | "Not published" is different from "zero"                                                                                                                                |
| 2   | Text numbers become real numbers                                            | all files                       | The database needs numeric types                                                                                                                                        |
| 3   | Place names and tickers become id numbers                                   | regional, volumes, share prices | Fact tables store ids, not names                                                                                                                                        |
| 4   | Share prices with volume 0 are dropped                                      | stock prices                    | Exchange holidays: the previous price is repeated with nothing traded, so these are not real prices. In our first download each of the five companies had 16 such rows. |
| 5   | Rows with a missing or non-positive price, rate or sales figure are dropped | market files                    | A missing value is not a value                                                                                                                                          |
| 6   | If a key appears twice, the last row is kept (and counted)                  | market files                    | Primary keys forbid duplicates; the count makes them visible                                                                                                            |
| 7   | Dates are cut to YYYY-MM-DD                                                 | market files                    | Matches the calendar table key                                                                                                                                          |

Every drop is counted and printed in the loader's "Cleaning report".

## Safety nets

- **All or nothing:** each loader runs inside one transaction; any error undoes
  everything it inserted.
- **No double loading:** loaders refuse to run if their tables already contain data.
- **Database rules:** primary keys, foreign keys and CHECK constraints reject
  impossible values (see `docs/data_model.md`).

## How correctness is proven

| Check script            | Checks | What it proves                                                                                              |
| ----------------------- | ------ | ----------------------------------------------------------------------------------------------------------- |
| `check_dimensions.py`   | 21     | Calendar complete with correct Nissan fiscal year, geography family tree, every source code known           |
| `check_nissan_facts.py` | 16     | Every CSV value equals the stored value (round trip); regions add up to the group total; blanks stayed NULL |
| `check_market_data.py`  | 8      | The raw market files, cleaned a second time with a different tool (pandas), match the database exactly      |

Together with `validate_raw_data.py` (37 checks on the raw files) and
`test_schema.py` (37 tests of the database rules), the project runs 119
automated checks.

## Known limitations

- Share prices are adjusted for dividends and splits (Yahoo's adjusted close).
- Nissan's published figures are rounded, so regional totals can differ from
  group totals by up to 0.5 (yen billions); the checks allow for this.
- Market data is a snapshot downloaded in November 2026; rerun
  `python src/download_market_data.py` and `python src/run_etl.py` to refresh it.
