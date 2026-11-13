# Nissan Turnaround 2027: A Data-Driven Recovery Case Study

> An end-to-end analysis of Nissan Motor Co.'s current financial and operational
> challenges, with quantified recommendations for FY2026-FY2027.

![Status](https://img.shields.io/badge/status-in%20progress-yellow)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![SQL](https://img.shields.io/badge/SQL-SQLite-lightgrey)
![Power BI](https://img.shields.io/badge/Power%20BI-dashboard-F2C811)
![Excel](https://img.shields.io/badge/Excel-scenario%20model-217346)

## 1. Business Problem

Nissan is executing **Re:Nissan**, a restructuring plan built around roughly
¥500 billion in cost savings, about 20,000 job cuts and a smaller manufacturing
footprint, with the goal of returning to operating profit in FY2026
(April 2026 - March 2027). Early results are encouraging but mixed: North
America is recovering while Europe and China remain weak.

**Core question:** Where does Nissan make and lose money, why, and which
concrete moves would make the recovery durable in 2027 rather than driven by
one-off gains?

## 2. Deliverables

| Deliverable                 | Location     |
| --------------------------- | ------------ |
| SQL analysis scripts        | `/sql`       |
| Python notebooks            | `/notebooks` |
| Excel scenario model        | `/excel`     |
| Power BI dashboard          | `/powerbi`   |
| Executive report and slides | `/reports`   |

## 3. Tech Stack

Python (pandas, matplotlib, seaborn) - SQL (SQLite) - Excel - Power BI - Git/GitHub

## 4. Repository Structure

```text
nissan-turnaround-2027/
├── data/
│   ├── raw/            # Source data exactly as collected
│   └── processed/      # Cleaned data and the SQLite database
├── sql/                # Numbered, commented SQL scripts
├── notebooks/          # Exploratory and statistical analysis
├── src/                # Reusable Python modules and scripts
├── excel/              # Scenario model workbook
├── powerbi/            # Dashboard file and exports
├── reports/            # Executive report, slides, figures
├── docs/               # Data dictionary, methodology, glossary
├── requirements.txt
└── README.md
```

## 5. How to Reproduce

```bash
git clone https://github.com/Balkis Slama/nissan-turnaround-2027.git
cd nissan-turnaround-2027
python -m venv .venv
source .venv/bin/activate        # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/check_setup.py
```

## 6. Data Sources

Full details, links and limitations: [`docs/data_sources.md`](docs/data_sources.md).
Column definitions: [`docs/data_dictionary.md`](docs/data_dictionary.md).

| Source                                          | Used for                                                                               |
| ----------------------------------------------- | -------------------------------------------------------------------------------------- |
| Nissan Investor Relations and Securities Report | Financials FY2021-FY2025, regional results, volumes, FY2026 outlook, Re:Nissan targets |
| Yahoo Finance                                   | Daily share prices of Nissan, Toyota, Honda, Mazda, Subaru                             |
| FRED (St. Louis Fed)                            | USD/JPY exchange rate                                                                  |
| Our World in Data / IEA                         | Electric car sales by country                                                          |

> **Note on fiscal years:** Nissan's FY2025 = April 2025 - March 2026.

### Raw data quality

Hand-collected figures are verified by an automated script
(`python src/validate_raw_data.py`) that checks structure, duplicates, source
references, whether regional figures add up to group totals, and whether
computed margins match Nissan's published margins.

## 7. Data Model

The analysis runs on a **star schema** in SQLite: 7 fact tables (financials,
regional results, volumes, restructuring targets, share prices, FX, EV sales)
around 5 dimensions (period, geography, company, date, source). The database
enforces data quality itself through primary keys, foreign keys and CHECK
rules, covered by 37 automated tests.

Diagram, table grains and design decisions: [`docs/data_model.md`](docs/data_model.md).

## 8. ETL Pipeline

One command rebuilds the whole database from the raw files and proves it is
correct:

```powershell
python src/run_etl.py
```

It builds the empty database, loads the dimensions, Nissan's results and the
market data, then runs 45 checks, including a "round trip" that compares every
stored value with the raw files and an independent second cleaning of the
market data. Cleaning rules (for example dropping exchange-holiday share price
rows) are documented in [`docs/etl_notes.md`](docs/etl_notes.md).

## 9. SQL Analysis

17 documented SQL queries (`sql/02_*.sql` to `sql/06_*.sql`) answer the
project's business questions: profitability and cash, regional profit, volumes,
Re:Nissan progress and market context.

```powershell
python src/run_sql_analysis.py     # runs all queries, saves tables to reports/tables/
python src/check_sql_analysis.py   # 22 checks: every answer recalculated independently with pandas
```

Query catalogue and findings: [`docs/sql_analysis.md`](docs/sql_analysis.md).

## 10. Charts and Nissan's Official Profit Bridge

```powershell
python src/validate_bridge_data.py   # 14 checks on Nissan's profit bridge data
python src/make_charts.py            # draws 8 charts into reports/figures/
python src/check_charts.py           # 18 checks: numbers, closing waterfalls, image sanity
```

![Sales and margin](reports/figures/fig01_sales_and_margin.png)

![FY2025 profit bridge](reports/figures/fig06_profit_bridge_fy2025.png)

![FY2026 outlook bridge](reports/figures/fig07_profit_bridge_fy2026_outlook.png)

![Volume changes](reports/figures/fig08_volume_changes.png)

## 10. Charts, Profit Bridge and Market Analysis

```powershell
python src/validate_bridge_data.py     # 14 checks on Nissan's official profit bridge data
python src/make_charts.py              # 8 charts into reports/figures/
python src/check_charts.py             # 18 checks: numbers, closing waterfalls, image sanity
python src/market_statistics.py        # share price statistics and yen sensitivity
python src/ev_market_analysis.py       # electric car markets
python src/check_market_analysis.py    # 15 checks: independent recalculation with numpy
```

![Sales and margin](reports/figures/fig01_sales_and_margin.png)

![FY2025 profit bridge](reports/figures/fig06_profit_bridge_fy2025.png)

![FY2026 outlook bridge](reports/figures/fig07_profit_bridge_fy2026_outlook.png)

![Volume changes](reports/figures/fig08_volume_changes.png)

![Share prices since April 2018](reports/figures/fig09_share_price_rebased.png)

![Drawdowns](reports/figures/fig10_drawdowns.png)

![Electric car markets](reports/figures/fig11_ev_markets.png)

### Findings so far (preliminary)

- **Profit collapsed while sales barely moved:** operating margin fell from
  4.5% (FY2023) to 0.5% (FY2025) although sales fell only 5%.
- **US tariffs (-286 bn yen) outweighed all of Nissan's cost savings (+227 bn yen)
  in FY2025**, according to Nissan's own breakdown. Even without tariffs the
  margin would have been about 2.9%, below FY2023's 4.5%, so tariffs are not
  the whole story: inflation (-95) and weaker sales performance (-35) also hurt.
- **The FY2026 outlook (200 bn yen) relies on +340 bn yen of cost savings and a
  derived +157 bn yen from sales performance**, but the volume outlook was cut
  from 3.3 to 3.15 million cars while the profit target was kept.
- **Europe loses money in every period; North America earns the most**, and
  about 96% of the Q1 FY2026 profit improvement comes from North America,
  where Nissan itself reports one-time tariff-related gains.
- **The FY2026 outlook assumes a European volume recovery (+7.3%)** although
  European retail fell 14.7% in Q1: a key assumption to stress-test.
- Much of the Q1 rise in revenue per vehicle (+15.6%) mirrors the weaker yen
  (USD/JPY +10.3%).

Details and caveats: [`docs/profit_bridge.md`](docs/profit_bridge.md),
[`docs/market_analysis.md`](docs/market_analysis.md).

## 11. Profit Drivers and Sensitivities

```powershell
python src/driver_analysis.py          # drivers, break-even headroom, volume/tariff grid, utilisation
python src/check_driver_analysis.py    # 12 checks: independent recalculation in plain Python
```

![Outlook drivers](reports/figures/fig12_outlook_drivers.png)

![Volume and tariff sensitivity](reports/figures/fig13_volume_tariff_sensitivity.png)

- **Without the derived +157 bn from sales, the FY2026 outlook would be 43 bn, not 200 bn.**
- **FY2025 without one-time gains was an operating loss of about 90 bn yen**; adding back the 286 bn
  tariff cost gives +196 bn (a 1.6% margin).
- At the derived rate of about JPY 1.05 million per extra car, the August volume cut (150k cars) is
  worth about -158 bn, yet the 200 bn outlook was kept.
- Around the outlook, volume headroom to break-even is about 190k cars (6.0%); each 10% of the tariff
  burden is worth about 26 bn.
- Plants outside China are roughly 85-93% utilised against the 2.5 million target capacity (rough estimate).

All derived values are flagged and illustrative: see [`docs/scenario_drivers.md`](docs/scenario_drivers.md).

## 12. Quality Assurance

Every layer is tested, and answers are always recalculated with a second,
independent method:

| Layer              | Command                               | Checks |
| ------------------ | ------------------------------------- | ------ |
| Raw data           | `python src/validate_raw_data.py`     | 37     |
| Database rules     | `python src/test_schema.py`           | 37     |
| ETL pipeline       | `python src/run_etl.py`               | 45     |
| SQL analysis       | `python src/check_sql_analysis.py`    | 22     |
| Profit bridge data | `python src/validate_bridge_data.py`  | 14     |
| Charts             | `python src/check_charts.py`          | 18     |
| Market analysis    | `python src/check_market_analysis.py` | 15     |
| Driver analysis    | `python src/check_driver_analysis.py` | 12     |

In total the project runs **200 automated checks**.

## 13. Project Progress

- [x] Step 1: Environment and repository setup
- [x] Step 2: Data acquisition and validation
- [x] Step 3: Data model (SQL star schema)
- [x] Step 4: ETL and cleaning (one-command pipeline)
- [x] Step 5: SQL analysis (17 queries, independently verified)
- [x] Step 6: Python analysis (official profit bridge, 11 charts, market statistics, EV markets)
- [x] Step 7: Profit drivers, break-even headroom and sensitivities
- [ ] Steps 8-10: Excel scenario model, peer benchmark, recommendations
- [ ] Step 11: Power BI dashboard
- [ ] Step 12-14: Report, slides, final polish

## 14. Key Findings

_To be completed at the end of the project._

## 15. Author

**<Your Name>**: Software Engineer, AI/ML Engineer and Data Scientist
[LinkedIn](https://www.linkedin.com/in/your-profile) - [GitHub](https://github.com/your-username)
