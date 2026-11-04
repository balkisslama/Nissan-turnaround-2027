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

### Data quality

Hand-collected figures are verified by an automated script
(`python src/validate_raw_data.py`) that checks structure, duplicates, source
references, whether regional figures add up to group totals, and whether
computed margins match Nissan's published margins.

## 7. Project Progress

- [x] Step 1: Environment and repository setup
- [x] Step 2: Data acquisition and validation
- [ ] Step 3: Data model (SQL)
- [ ] Step 4: ETL and cleaning
- [ ] Step 5: SQL analysis
- [ ] Step 6-10: Python analysis, Excel scenario model, recommendations
- [ ] Step 11: Power BI dashboard
- [ ] Step 12-14: Report, slides, final polish

## 8. Key Findings

_To be completed at the end of the project._

## 9. Author

**<Your Name>**: Software Engineer, AI/ML Engineer and Data Scientist
[LinkedIn](https://www.linkedin.com/in/your-profile) - [GitHub](https://github.com/your-username)
