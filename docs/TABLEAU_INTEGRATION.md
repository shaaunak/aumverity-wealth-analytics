# AUMVERITY — Tableau Integration & Dashboard Specification

> **Note:** Tableau Desktop / Tableau Public is not installed in this environment, so no `.twb` or `.twbx` workbook has been created or published. All five analysis-ready CSV extracts are generated directly from PostgreSQL marts via `/api/v1/exports/tableau/{dataset}.csv`.

## 1. Exported Datasets

| Dataset | Grain | Key Columns |
|---------|-------|-------------|
| `advisor_performance.csv` | Advisor × Quarter | `advisor_code`, `segment_name`, `opening_assets_usd`, `closing_assets_usd`, `firm_style_nna_usd`, `market_movement_usd`, `nna_rank` |
| `asset_movement.csv` | Bridge Step × Period | `step_key`, `label`, `amount_usd`, `step_type` |
| `segment_performance.csv` | Segment × Quarter | `segment_code`, `opening_assets_usd`, `closing_assets_usd`, `firm_style_nna_usd`, `market_movement_usd`, `nna_growth_rate_pct` |
| `monthly_flows.csv` | Month (24M history) | `period_code`, `closing_assets_usd`, `external_net_flows_usd`, `firm_style_nna_usd`, `market_driven_movement_usd` |
| `reconciliation_exceptions.csv` | Exception Issue | `issue_code`, `severity`, `expected_amount_usd`, `reported_amount_usd`, `difference_usd`, `status` |

## 2. Recommended Tableau Calculated Fields

- **Organic NNA Growth %:** `SUM([firm_style_nna_usd]) / SUM([opening_assets_usd])`
- **Market Share of Growth %:** `SUM([market_movement_usd]) / (SUM([firm_style_nna_usd]) + SUM([market_movement_usd]))`
- **Absolute Variance (USD):** `ABS([difference_usd])`

## 3. Recommended Dashboard Specification (5 Views)

1. **Executive Summary:** KPI banner (`monthly_flows.csv` latest month) + 24-month AUM & NNA trend.
2. **Advisor League Table:** Sortable bar/table of `advisor_performance.csv` colored by NNA sign (`#246B60` / `#C45B51`).
3. **Asset Movement Analysis:** Waterfall Gantt chart built from `asset_movement.csv`.
4. **Segment Performance:** Side-by-side NNA vs. Market Movement bars from `segment_performance.csv`.
5. **Reconciliation Monitoring:** Exception severity matrix and variance table from `reconciliation_exceptions.csv`.
