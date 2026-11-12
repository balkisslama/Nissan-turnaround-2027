# Market Analysis

Scripts: `src/market_statistics.py`, `src/ev_market_analysis.py`
Check: `python src/check_market_analysis.py` (15 checks)

## Share prices and the yen (daily data since 1 April 2018)

| Measure                | Definition                                                                                              |
| ---------------------- | ------------------------------------------------------------------------------------------------------- |
| Total return           | last adjusted price / first adjusted price - 1                                                          |
| Annual volatility      | standard deviation of daily returns x sqrt(252)                                                         |
| Maximum drawdown       | deepest percentage fall from a previous peak                                                            |
| Drawdown now           | current percentage below the highest price so far                                                       |
| Yen correlation / beta | correlation and slope of daily share returns against daily % changes in USD/JPY, on days that have both |

Outputs: `reports/tables/market_statistics.csv`, `yen_sensitivity.csv`,
`fig09_share_price_rebased.png`, `fig10_drawdowns.png`.

## Electric car markets

Our World in Data / IEA numbers of new electric cars (battery-electric plus
plug-in hybrid) for China, Europe, the United States, Japan, Germany, France and
the United Kingdom, from 2018. Outputs: `reports/tables/ev_markets.csv`,
`ev_summary.csv`, `fig11_ev_markets.png`.

## Caveats

- Statistics show association, not cause.
- The USD/JPY series (FRED) is a New York rate, so same-day matching with Tokyo
  closing prices is loose and daily correlations are understated.
- Prices are adjusted for dividends and splits.
- Ordinary hybrids (including Nissan's e-POWER) are not counted as electric cars,
  and the data has no total car sales, so we measure growth, not market share.
- Market names are matched by alias; markets missing from the data are skipped
  and reported.
- Every statistic is recalculated independently with numpy from the raw CSV files.
