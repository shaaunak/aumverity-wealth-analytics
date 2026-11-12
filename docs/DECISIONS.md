# AUMVERITY — Architecture & Design Decisions (ADR Log)

## ADR-001: Separate External Net Flows from Firm-Style NNA
- **Decision:** Model `external_net_flows` and `firm_style_nna` as distinct metrics, with `internal_transfers` tracked separately and netted to zero at the firm level.
- **Rationale:** Wealth management firms report NNA including credited dividends/interest and eligible asset acquisitions, while internal transfers between firm accounts must not inflate firm-level NNA.

## ADR-002: No Residual-As-Market-Movement
- **Decision:** Never compute Market Appreciation as `Ending AUM - Beginning AUM - Net Flows`. Compute Market Appreciation from position/return attribution and surface any discrepancy as `unreconciled_variance`.
- **Rationale:** Disguising data breaks or missing transactions inside "Market Performance" destroys analytical trust.

## ADR-003: PostgreSQL Schemas (`raw`, `staging`, `marts`, `reconciliation`)
- **Decision:** Organize PostgreSQL into four explicit schemas representing the analytical lineage pipeline.
- **Rationale:** Mirrors production warehouse architecture and makes KPI lineage transparent in Module 08.

## ADR-004: USD-Only Initial Scope
- **Decision:** Restrict initial implementation to `USD` and exclude FX attribution.
- **Rationale:** Avoids fabricated FX calculations until full multi-currency lot accounting is built.

## ADR-005: Deterministic Arithmetic Only
- **Decision:** Use PostgreSQL `NUMERIC` and Python `Decimal` for all financial calculations; prohibit LLM arithmetic.
- **Rationale:** Guarantees exact tie-outs across SQL, API, UI, and Excel/CSV exports.
