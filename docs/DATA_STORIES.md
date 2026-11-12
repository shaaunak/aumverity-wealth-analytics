# AUMVERITY — Synthetic Data Stories & Anomaly Manifest

> **Disclosure:** All entities, accounts, transactions, prices, and narratives in this document are **100% SYNTHETIC**, generated deterministically (`--profile demo --seed 10753`, baseline `2026-09-30`) for analytical and reconciliation demonstration.

## Business Narratives

### Story A — Major Advisor Outflows (`ADV-001`)
- **Narrative:** Advisor `ADV-001` in `Advisor-Led Wealth Management` experiences concentrated external outflows in `2026-Q3` (July–September 2026) driven by 6 large client departures (`EXTERNAL_TRANSFER_OUT`).
- **SQL Discovery:** Query `marts.advisor_level_flows` for `period_code = '2026-Q3'` ordered by `external_net_flows_usd ASC`.

### Story B — Sweep-to-External Asset Retention Trend
- **Narrative:** Clients in `Cash management` accounts shift sweep cash to external institutions (`EXTERNAL_WITHDRAWAL`) between June and September 2026 following a synthetic rate-driven behavior shift.
- **SQL Discovery:** Query `marts.account_level_cash_movement` where `account_type = 'Cash management'` and `sweep_delta_usd < 0`.

### Story C — Market-Driven Segment Growth (`Self-Directed Investing`)
- **Narrative:** The `Self-Directed Investing` (`SDI`) segment exhibits substantial AUM growth in `2026-Q3` primarily from strong synthetic equity/tech ETF price appreciation (`SYN-EQ-TECH`, `SYN-ETF-AI`, `SYN-ETF-SPX`), rather than client net inflows.
- **SQL Discovery:** Query `marts.segment_level_holdings` for `2026-Q3` comparing `market_appreciation_usd` vs. `firm_style_nna_usd`.

### Story D — High-Growth Advisor (`ADV-002`)
- **Narrative:** Advisor `ADV-002` generates strong positive `firm_style_nna_usd` in `2026-Q3` across 15+ newly opened and active client accounts rather than a single outlier transaction.
- **SQL Discovery:** Query `marts.advisor_level_flows` for `period_code = '2026-Q3'` ordered by `firm_style_nna_usd DESC`, checking `active_accounts_with_flows`.

### Story E — Controlled Reporting Discrepancies (Ground Truth Preserved)
The clean ground-truth ledger (`raw.transaction_events`, `raw.account_valuations`) is preserved separately from `raw.reported_asset_snapshots`. Four controlled discrepancies are injected and documented in `data/seeds/seed_manifest_demo_10753.json`:
1. **E1 — Duplicate Feed Record:** Duplicate row in `raw.reported_asset_snapshots` on `2026-09-30` with identical `record_hash`.
2. **E2 — Missing Transaction in Reporting Aggregate:** `reported_nna_usd` and `reported_aum_usd` on `2026-09-30` are understated by `$250,000.00` for one account relative to `marts.monthly_asset_snapshots`.
3. **E3 — Late-Posted Internal Transfer:** Linked `INTERNAL_ACCOUNT_TRANSFER` with `effective_date = 2026-09-29` and `posted_date = 2026-10-02` crossing the `2026-Q3` boundary.
4. **E4 — Incorrect Advisor/Segment Classification:** Three accounts on `2026-09-30` in `raw.reported_asset_snapshots` carry mismatched `advisor_id` and `segment_id` compared to `raw.accounts`.
