# AUMVERITY — Data Dictionary

> **Status:** Phase 00 baseline conventions. Schema tables and columns will be expanded in Phase 01 as `raw`, `staging`, `marts`, and `reconciliation` tables are implemented.

## Core Data Conventions

| Convention | Standard |
|------------|----------|
| **Reporting Currency** | `USD` (starting implementation is USD-only) |
| **Monetary Precision** | `NUMERIC(18, 2)` in PostgreSQL; `decimal.Decimal` in Python |
| **Quantity / Return Precision** | `NUMERIC(18, 6)` in PostgreSQL |
| **Missing Values** | Explicit `NULL` — never coerced silently to `0.00` |
| **Timestamps** | `TIMESTAMPTZ` stored in UTC |
| **Business Dates** | Explicit `DATE` columns (`effective_date`, `posted_date`, `as_of_date`) |
| **Historical Assignments** | Slowly Changing Dimension Type 2 (`effective_from`, `effective_to`, `is_current`) for advisor-client-account relationships |
| **Calculation Version** | Semantic version string (e.g. `v1.0.0`) attached to mart rows, API responses, and exports |
| **Data Classification** | `SYNTHETIC` — all records are generated for analytical demonstration |

## Planned PostgreSQL Schemas

1. `raw`: Append-only synthetic source tables (`advisors`, `clients`, `accounts`, `advisor_assignments`, `transactions`, `eop_positions`, `market_benchmarks`).
2. `staging`: Validated, typed, and deduplicated views/tables with data quality flags (`dq_status`).
3. `marts`: Analytical tables and materialized views (`mart_aum_bridge`, `mart_advisor_performance`, `mart_segment_summary`, `mart_flow_attribution`).
4. `reconciliation`: Automated tie-out results (`recon_bridge_tieout`, `recon_internal_transfer_netting`, `recon_eop_snapshot_checks`).
