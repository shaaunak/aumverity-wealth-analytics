# AUMVERITY — Interview Preparation Guide

> **Context:** AUMVERITY is a synthetic-data portfolio project built to demonstrate wealth-management data analytics, SQL engineering, financial reconciliation, and stakeholder BI reporting.

## 1. What Problem Does AUMVERITY Solve?
Wealth-management leadership routinely asks: *"Why did client assets change by \$X this quarter, and how much came from advisor inflows versus market appreciation?"* Standard BI dashboards often conflate internal account transfers with Net New Assets (NNA), hide valuation gaps inside "market movement," or fail to catch stale/duplicate management reporting feeds. AUMVERITY separates **External Net Flows**, **Firm-Style Net New Assets**, **Price-Driven Market Movement**, **Fees & Commissions**, and **Unexplained Residual** so every dollar is auditable back to source SQL records.

## 2. Why SQL Was Used
- **Set-based financial precision:** Aggregating 67,397+ transaction events and 115,000+ monthly account-bridge rows in PostgreSQL using CTEs, window functions (`RANK()`, `LAG()`), and `NUMERIC(18,2)` arithmetic avoids floating-point drift and keeps business logic close to the data.
- **Lineage & governance:** Every KPI in the UI maps to a documented SQL view/materialized view in `marts` and `ops`, allowing analysts to inspect the exact query behind any figure.

## 3. Why PostgreSQL Was Selected
- **Strict schemas (`raw`, `staging`, `marts`, `ops`)** enforce separation between immutable source feeds, data-quality-checked staging views, materialized analytical marts, and operational reconciliation logs.
- **Materialized views + covering indexes:** PostgreSQL `MATERIALIZED VIEW`s (`marts.mv_account_monthly_bridge`, `marts.mv_position_market_attribution`) combined with covering B-tree `INCLUDE` indexes (`ix_mv_acct_bridge_end_date`) deliver sub-100ms analytical API responses on local hardware.
- **DECIMAL/NUMERIC support:** Native fixed-point `NUMERIC` prevents IEEE-754 rounding errors in multi-billion-dollar AUM reconciliations.

## 4. How Financial Data Is Validated
- **Staging DQ gates:** `staging.stg_account_valuations` and related staging checks verify `cash + securities = total_equity`, non-negative quantities, and balanced `INTERNAL_ACCOUNT_TRANSFER` legs (`SUM(CREDIT - DEBIT) = 0`).
- **Automated reconciliation:** `ops` / `raw.reconciliation_issues` compares `raw.reported_asset_snapshots` against `marts.monthly_asset_snapshots` and flags duplicate hashes (`DUPLICATE_RECORD`), understated aggregates (`MISSING_TRANSACTION_AGGREGATE`), cross-period effective/posted lags (`LATE_POSTED_TRANSFER`), and advisor/segment mismatches (`CLASSIFICATION_MISMATCH`).

## 5. How Attribution Works
$$\text{Closing Assets} = \text{Opening Assets} + \text{Firm-Style NNA} + \text{Market Movement} - \text{Fees \& Commissions} + \text{Other Adjustments} + \text{Unexplained Residual}$$
- **Market Movement** is calculated bottom-up from position quantity $\times$ price change (adjusted for stock splits), **never** as `Closing - Opening - Flows`.
- **Unexplained Residual** (`Actual Closing - Expected Closing`) is explicitly surfaced and never hidden inside market movement.
- **Dividends & Reinvestments:** Credited dividends enter cash without double-counting when reinvested into securities (which is a cash-for-security trade, not new NNA).

## 6. How Performance Was Optimized
- Replaced a multi-table raw join (`143.589 ms`, external disk sort `2744kB`) with `marts.mv_account_monthly_bridge` backed by covering index `ix_mv_acct_bridge_end_date` (`61.639 ms`, `Index Only Scan`, `Heap Fetches: 0`, `0` temp disk blocks). See `docs/SQL_OPTIMIZATION_CASE_STUDY.md`.

## 7. How Reconciliation Prevents Inaccurate Reporting
Management feeds (`raw.reported_asset_snapshots`) are never assumed to match the underlying transaction ledger. Four seeded discrepancies (duplicate feed row, \$250,000 understatement, late-posted Q3/Q4 boundary transfer, and 3 misclassified accounts) are surfaced in the Financial Reconciliation Center with side-by-side **Reported vs. Reconstructed** balances and source-record evidence.

## 8. What Happens When a Client Changes Advisors
`raw.advisor_assignment_history` and `raw.account_classification_history` track effective-dated ownership. Transfers between advisors inside the firm perimeter are tagged `INTERNAL_ACCOUNT_TRANSFER` (`SUM(legs) = 0`), so they **do not** inflate firm-wide NNA while still remaining traceable at the advisor-book level.

## 9. How the System Could Scale to Millions of Transactions
- Partition `raw.transaction_events` and `raw.account_valuations` by `effective_date` (monthly/quarterly range partitions).
- Replace full materialized view refreshes with incremental partition refreshes or dbt incremental models.
- Use read replicas for analytical FastAPI endpoints (`SET TRANSACTION READ ONLY`) and pre-aggregate daily/monthly rollups per advisor and segment.
