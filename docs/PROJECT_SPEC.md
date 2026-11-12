# AUMVERITY — Project Specification

> **Tagline:** "Every asset movement explained. Every number verified."
> **Data Classification:** All data in AUMVERITY is **SYNTHETIC**. This system is an independent portfolio demonstration and is not affiliated with or an official system of Morgan Stanley or any other financial institution.

## 1. Mission & Analytical Questions

AUMVERITY is an internal-style Wealth Intelligence & Asset Movement Analytics platform designed to demonstrate practical financial data engineering, advanced SQL, quantitative attribution, data reconciliation, and stakeholder reporting.

It directly answers seven core wealth management questions:
1. Why did client assets increase or decrease over a reporting period?
2. Which advisors generated the highest inflows, outflows, and firm-style Net New Assets (NNA)?
3. What percentage of asset movement came from market performance versus client activity?
4. Which business segments are performing best?
5. Which client behaviors (transfers, withdrawals, cash deployment, fee drag) explain important changes?
6. Are management reports consistent with underlying financial data?
7. Can every important KPI be traced to SQL calculations and source records?

## 2. Product Modules

| # | Module | Purpose |
|---|--------|---------|
| 01 | **Executive Overview** | Firm-wide Beginning AUM, Ending AUM, Net Change, Market Appreciation vs. Firm-style NNA, External Net Flows, and Segment breakdown. |
| 02 | **Asset Movement Bridge** | Waterfall decomposition reconciling Beginning AUM to Ending AUM with zero unexplained residual. |
| 03 | **Advisor Explorer** | Advisor book AUM, inflows/outflows, NNA, historical advisor-client assignments, and ranking. |
| 04 | **Client & Account Intelligence** | Client household and account-level balances, transactions, and behavioral drivers. |
| 05 | **Flow Analytics** | External Net Flows vs. Firm-style NNA, internal transfer netting, dividend/reinvestment separation, posted vs. effective dates. |
| 06 | **Reconciliation Center** | Automated SQL tie-outs across raw, staging, mart, and reporting layers with variance alerts. |
| 07 | **Investigation Workspace** | Drill-down audit trail for large movements, variance breaks, and advisor book transfers. |
| 08 | **Data Lineage & Metric Dictionary** | Full KPI lineage mapping UI metrics to SQL CTEs, marts, staging tables, and raw columns. |
| 09 | **Reporting & Exports** | Formatted Excel workbooks (`openpyxl`) and Tableau-compatible CSV extracts with calculation version and as-of date metadata. |

## 3. Technical Stack

- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui patterns, Apache ECharts, TanStack Query, TanStack Table, Lucide icons, Vitest, Playwright.
- **Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic, PostgreSQL 16.
- **Analytics & Reporting:** PostgreSQL CTEs, window functions, materialized views, Pandas, NumPy, `openpyxl`, Tableau-compatible CSVs.
- **Infrastructure:** Docker Compose, `.env` configuration, `/health` & `/ready` probes, structured JSON logging.

## 4. Core Engineering & Financial Rules

- **No hardcoded KPIs:** All financial figures in the UI must come from backend SQL queries.
- **No LLM arithmetic:** All financial attribution and reconciliation must be deterministic Python/SQL using `Decimal` / `NUMERIC`.
- **USD-only starting scope:** Default reporting currency is `USD`; FX attribution is not claimed without actual FX accounting.
- **Null vs. Zero:** Missing data (`NULL`) is handled distinctly from `0.00`.
- **Dual Dates:** Both `posted_date` and `effective_date` are stored and supported, alongside UTC timestamps and explicit reporting business dates.
- **Traceability:** Every API response and export includes `calculation_version` and `as_of_date`.

## 5. User Journeys & Test Strategy

- **Unit Tests (`pytest`, `vitest`):** Health/readiness endpoints, financial attribution formulas, transfer netting rules, UI shell and component rendering.
- **Integration Tests (`pytest`):** PostgreSQL schema migrations, SQL mart tie-outs, reconciliation checks, API endpoints against live DB.
- **End-to-End Tests (`playwright`):** Navigating all 9 modules, applying date/advisor/segment filters, verifying waterfall bridge tie-out and export generation.
