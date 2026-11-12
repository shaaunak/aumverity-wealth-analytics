# AUMVERITY — Technical & Architecture Decisions

## 1. Layered PostgreSQL Warehouse (`raw`, `staging`, `marts`, `ops`)
- **Decision:** Separate immutable source/synthetic tables (`raw`), data-quality validation views (`staging`), pre-aggregated analytical materialized views (`marts`), and audit/reconciliation tracking (`ops` / `raw.reconciliation_issues`).
- **Rationale:** Mirrors institutional data-warehouse separation of duties and prevents presentation queries from scanning unindexed raw ledger tables.

## 2. Explicit Unexplained Residual (No Balancing Plugs)
- **Decision:** Compute Market Movement independently from position quantities and security price changes, and expose `Unexplained Residual = Actual Closing - Expected Closing`.
- **Rationale:** Hiding data gaps inside Market Movement destroys analytical trust. Exposing residual guarantees any missing event or pricing error is immediately visible.

## 3. Predefined Investigation Templates (No Arbitrary SQL Endpoint)
- **Decision:** Expose `POST /api/v1/investigations/run` only for curated, parameterized SQL templates (`top5_outflow_advisors`, `positive_aum_negative_nna`, `cash_sweep_attrition`, etc.).
- **Rationale:** Eliminates SQL injection and arbitrary resource-exhaustion risks while still giving analysts flexible, repeatable drill-downs.

## 4. Fixed-Point `Decimal` Arithmetic & Parameterized SQLAlchemy/Psycopg
- **Decision:** All financial calculations in Python (`backend/app/services/attribution/engine.py`) and PostgreSQL use `Decimal` / `NUMERIC(18,2)` and bound parameters.
- **Rationale:** Avoids floating-point rounding drift and SQL injection vulnerabilities.

## 5. Institutional Light-First UI & ECharts Visualization
- **Decision:** React + TypeScript + Tailwind CSS + TanStack Table + Apache ECharts with a restrained `#F6F7F4` canvas, `#122D33` ink, `#246B60` primary teal, and `#C45B51` negative accent, using `tabular-nums` for all monetary columns.
- **Rationale:** High information density and financial readability without decorative dark-mode/gaming clutter.
