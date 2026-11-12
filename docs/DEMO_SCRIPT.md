# AUMVERITY — 3-Minute Stakeholder Demo Script (Q3 2026 Dataset)

> **Disclosure:** All figures in AUMVERITY are **SYNTHETIC** (`--profile demo --seed 10753`, `2026-Q3`: `2026-07-01` to `2026-09-30`).

## Minute 0:00 – 0:35 | Trust, Lineage & Executive Overview (`/`)
1. Point out the `SYNTHETIC` classification badge, `USD` currency label, and active period selector (`Q3 2026`).
2. Review **Opening Assets**, **Closing Assets**, **Firm-Style NNA**, **External Net Flows**, and **Market-Driven Movement**.
3. Click **Firm-Style NNA** to open the **Explainable KPI Drawer**: show the exact formula, inclusion/exclusion rules (internal transfers excluded), and SQL lineage (`marts.mv_account_monthly_bridge`).

## Minute 0:35 – 1:15 | Asset Movement Bridge (`/bridge`)
1. Open **Asset Movement Bridge** to show the Opening-to-Closing waterfall.
2. Verify that **Unexplained Residual** is explicitly isolated (`$0.00` on clean ground-truth accounts) rather than hidden in Market Movement.

## Minute 1:15 – 2:00 | Advisor Outflows vs. Organic Growth (`/advisors`, `/flows`)
1. Open **Advisor Explorer**, sort by `External Net Flows` ascending to surface **`ADV-001`** (Story A: concentrated `EXTERNAL_TRANSFER_OUT` departures).
2. Sort by `Firm-Style NNA` descending to contrast **`ADV-002`** (Story D: broad-based growth across 15+ accounts).
3. Click into **Flow & Period Compare** (`/flows`) to inspect **2026-Q3 vs 2026-Q2** attribution, advisor ranking shifts, and **Positive AUM Growth / Negative NNA** advisors.

## Minute 2:00 – 2:35 | Reconciliation Center (`/reconciliation`)
1. Open **Financial Reconciliation Center** and show the 4 detected exceptions (`DUPLICATE_RECORD`, `MISSING_TRANSACTION_AGGREGATE`, `LATE_POSTED_TRANSFER`, `CLASSIFICATION_MISMATCH`).
2. Click an exception row to compare **Reported Financial Balance** vs. **Reconstructed Financial Balance**, inspect the contributing source records, and export issue evidence CSV.

## Minute 2:35 – 3:00 | Management Reports & BI Exports (`/exports`)
1. Open **Reports & Exports** and download `AUMVerity_Wealth_Management_Quarterly_Report.xlsx` (9 worksheets with live Excel formulas) plus any of the 5 Tableau CSV extracts.
