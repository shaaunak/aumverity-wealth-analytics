# AUMVERITY — Business Case Study (Q3 2026 Synthetic Dataset)

> **Disclosure:** All entities, balances, and events are **100% SYNTHETIC** (`--profile demo --seed 10753`, 24 months ending `2026-09-30`).

## Executive Problem Statement
In Q3 2026 (`2026-07-01` to `2026-09-30`), wealth-management leadership needs to understand:
1. Whether headline AUM growth came from **advisor client acquisition (NNA)** or **equity market appreciation**.
2. Which advisors are experiencing **concentrated client outflows** (`ADV-001`) versus broad-based **multi-account NNA growth** (`ADV-002`).
3. Whether **Cash Management** sweep balances are leaking to external institutions.
4. Whether **management-reported snapshots** reconcile to the underlying transaction and valuation ledger.

## Key Analytical Findings in the Seeded Q3 2026 Dataset
- **Story A — Concentrated Advisor Outflows (`ADV-001`):** `ADV-001` in *Advisor-Led Wealth Management* experienced concentrated external outflows driven by 6 large `EXTERNAL_TRANSFER_OUT` client departures, placing `ADV-001` at the top of the outflow ranking despite broader market gains.
- **Story B — Sweep-to-External Cash Attrition:** *Cash management* accounts exhibited negative sweep cash deltas (`sweep_delta_usd < 0`) between June and September 2026 as synthetic balances moved to `EXTERNAL_WITHDRAWAL`.
- **Story C — Market-Driven Segment Growth (`Self-Directed Investing`):** *Self-Directed Investing* (`SDI`) grew primarily due to price appreciation in synthetic tech/index holdings (`SYN-EQ-TECH`, `SYN-ETF-AI`, `SYN-ETF-SPX`) rather than net new client deposits.
- **Story D — Broad-Based Advisor NNA (`ADV-002`):** `ADV-002` generated top-ranked `firm_style_nna_usd` across 15+ active client accounts, demonstrating durable organic growth rather than a single outlier deposit.
- **Story E — Reporting Integrity Exceptions (4 Seeded Discrepancies):**
  1. Duplicate feed row on `2026-09-30` (`DUPLICATE_RECORD`).
  2. `$250,000.00` understatement in `reported_nna_usd` and `reported_aum_usd` (`MISSING_TRANSACTION_AGGREGATE`).
  3. Cross-quarter internal transfer (`effective_date = 2026-09-29`, `posted_date = 2026-10-02`) (`LATE_POSTED_TRANSFER`).
  4. Three accounts carrying mismatched `advisor_id` and `segment_id` in reported snapshots (`CLASSIFICATION_MISMATCH`).

## Business Impact
- Prevents leadership from misattributing market rallies to advisor sales productivity.
- Surfaces "Positive AUM Growth / Negative NNA" advisors whose client attrition is masked by rising markets.
- Gives finance and operations teams a reproducible audit trail from executive KPIs down to individual transaction legs.
