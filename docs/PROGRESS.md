# AUMVERITY — Project Progress Tracker

## Phase 00 — Foundation & Application Shell

| Field | Value |
|-------|-------|
| **Task ID** | `PHASE-00` |
| **Status** | `DONE` |
| **Files Changed** | `.gitignore`, `.env.example`, `docker-compose.yml`, `infra/*`, `pyproject.toml`, `Makefile`, `README.md`, `backend/app/*`, `backend/alembic*`, `frontend/*`, `docs/*`, `tests/unit/test_health.py` |
| **Actual Verification Command** | `.venv/bin/pytest tests/unit/test_health.py` and `cd frontend && npm run typecheck && npm run test && npm run build` |
| **Actual Verification Results** | Backend unit tests: `3 passed`. Frontend: `tsc -b --noEmit` (0 errors), Vitest `1 passed`, Vite production build succeeded (`dist/`). |
| **Known Limitations** | Docker Compose build/up unverified locally because `docker` is not installed on host; local PostgreSQL 16 (`localhost:5433`) initialized via `initdb`/`pg_ctl`. |
| **Next Task** | `PHASE-01` |

## Phase 01 — Synthetic Wealth Dataset & PostgreSQL Warehouse

| Field | Value |
|-------|-------|
| **Task ID** | `PHASE-01` |
| **Status** | `DONE` |
| **Files Changed** | `backend/app/models/*`, `backend/alembic/versions/069dfddea825_phase01_warehouse_schema.py`, `sql/staging/01_staging_views.sql`, `sql/marts/01_analytics_models.sql`, `sql/reconciliation/01_reconciliation_checks.sql`, `data/generator/*`, `data/seeds/seed_manifest_demo_10753.json`, `docs/DATA_STORIES.md`, `tests/integration/test_warehouse_quality.py` |
| **Actual Verification Command** | `../.venv/bin/alembic upgrade head`, `.venv/bin/python -m data.generator --profile demo --seed 10753`, `.venv/bin/pytest tests/integration/test_warehouse_quality.py` |
| **Actual Verification Results** | Alembic applied 25 tables; demo seed (`seed=10753`, baseline `2026-09-30`) loaded in `48.93s` (`67,397` events, `555,000` valuations, `330,577` position snapshots). `9 passed` warehouse quality tests. |
| **Known Limitations** | `large` profile configured but not executed locally. |
| **Next Task** | `PHASE-02` |

## Phase 02 — Financial Intelligence Engine & SQL Attribution

| Field | Value |
|-------|-------|
| **Task ID** | `PHASE-02` |
| **Status** | `DONE` |
| **Files Changed** | `sql/marts/02_phase02_analytics.sql`, `sql/marts/03_business_questions.sql`, `backend/app/services/attribution/engine.py`, `backend/app/services/lineage/registry.py`, `tests/unit/test_attribution_regression.py` |
| **Actual Verification Command** | `psql -h localhost -p 5433 -U aumverity -d aumverity -v ON_ERROR_STOP=1 -f sql/marts/02_phase02_analytics.sql -f sql/marts/03_business_questions.sql` and `.venv/bin/pytest tests/unit/test_attribution_regression.py` |
| **Actual Verification Results** | Materialized views `mv_position_market_attribution` (`108,979` rows) and `mv_account_monthly_bridge` (`115,000` rows) plus all 9 Business Question views (`q_a`–`q_i`) compiled cleanly. All `9` Decimal attribution regression tests passed. |
| **Known Limitations** | EOD-snapshot convention (not intraday-precise). |
| **Next Task** | `PHASE-03` |

## Phase 03 — Production FastAPI v1 Analytics, Lineage & Reconciliation Service

| Field | Value |
|-------|-------|
| **Task ID** | `PHASE-03` |
| **Status** | `DONE` |
| **Files Changed** | `backend/app/schemas/{common,analytics}.py`, `backend/app/services/{metrics,reconciliation,investigations}/service.py`, `backend/app/api/v1/router.py`, `backend/app/main.py`, `tests/integration/test_api_v1.py` |
| **Actual Verification Command** | `.venv/bin/pytest` |
| **Actual Verification Results** | Full `pytest` suite: `31 passed` in `4.44s` (API contracts, filter/pagination/sorting, decimal tie-outs, reconciliation detection & demo acknowledgement, predefined investigation templates, SQLi resistance, and error envelopes). |
| **Known Limitations** | Exports service (`exports/`) and frontend analytical UI modules (`01`–`09`) scheduled for subsequent phases. |
| **Next Task** | `PHASE-04` (Frontend Analytical Modules & Interactive Data Visualizations) |

## Phase 04 — Institutional Light-First Executive Overview UI

| Field | Value |
|-------|-------|
| **Task ID** | `PHASE-04` |
| **Status** | `DONE` |
| **Files Changed** | `frontend/index.html`, `frontend/src/index.css`, `frontend/src/lib/{format,api}.ts`, `frontend/src/context/FilterContext.tsx`, `frontend/src/components/{AppShell,EChartBox,KpiDetailDrawer}.tsx`, `frontend/src/pages/{ExecutiveOverview,ModulePlaceholder}.tsx`, `frontend/src/App.tsx`, `frontend/src/App.test.tsx`, `backend/app/api/v1/router.py` |
| **Actual Verification Command** | `cd frontend && npm run typecheck && npm run test && npm run build` and `.venv/bin/pytest` |
| **Actual Verification Results** | Frontend: `tsc -b --noEmit` (`0` errors), Vitest `2 passed`, Vite production build succeeded (`dist/`). Backend: `31 passed` in `3.52s`. |
| **Known Limitations** | Browser visual QA & screenshot capture (`docs/screenshots/`) BLOCKED: Chrome remote debugging (`DevToolsActivePort`) is not enabled on the host. |
| **Next Task** | `PHASE-05` (Deep-Dive Modules: Asset Bridge, Advisor Explorer, Clients & Accounts, Flow Analytics) |

## Phase 05 — Financial Investigation Platform (Advisor, Client & Investigation Workspace)

| Field | Value |
|-------|-------|
| **Task ID** | `PHASE-05` |
| **Status** | `DONE` |
| **Files Changed** | `backend/app/api/v1/router.py`, `backend/app/schemas/analytics.py`, `frontend/src/pages/{AdvisorExplorer,AdvisorDetail,ClientAccountExplorer,InvestigationWorkspace}.tsx`, `frontend/src/lib/api.ts`, `frontend/src/App.tsx`, `tests/integration/test_api_v1.py` |
| **Actual Verification Command** | `.venv/bin/pytest` and `cd frontend && npm run typecheck && npm run test && npm run build` |
| **Actual Verification Results** | Backend: `32 passed`. Frontend: `0` TypeScript errors, Vitest `2 passed`, Vite `dist/` built cleanly. |
| **Known Limitations** | Browser visual QA blocked without Chrome remote debugging. |
| **Next Task** | `PHASE-06` |

## Phase 06 — Reconciliation Center, Period Compare, Excel & Tableau Exports, SQL Optimization

| Field | Value |
|-------|-------|
| **Task ID** | `PHASE-06` |
| **Status** | `DONE` |
| **Files Changed** | `backend/app/services/exports/{excel_service,tableau_service}.py`, `backend/app/api/v1/router.py`, `sql/marts/02_phase02_analytics.sql`, `docs/{SQL_OPTIMIZATION_CASE_STUDY,TABLEAU_INTEGRATION}.md`, `frontend/src/lib/api.ts`, `frontend/src/pages/{ReconciliationCenter,FlowAnalytics,AssetBridgePage,MetricDictionaryPage,ReportsPage}.tsx`, `frontend/src/App.tsx`, `tests/integration/test_api_v1.py` |
| **Actual Verification Command** | `.venv/bin/pytest -v` and `cd frontend && npm run typecheck && npm run test && npm run build` |
| **Actual Verification Results** | Backend: `35 passed` in `4.91s` (including Period Compare, 9-sheet Excel workbook with live formulas & Overview tie-out, and all 5 Tableau CSV extract tie-outs). SQL Optimization: `EXPLAIN (ANALYZE, BUFFERS)` improved from `143.589 ms` (external disk sort `2744kB`) to `61.639 ms` (`Index Only Scan`, `0` heap fetches, `0` temp disk blocks) via `ix_mv_acct_bridge_end_date`. Frontend: `tsc -b --noEmit` (`0` errors), Vitest `2 passed`, Vite production build completed. |
| **Known Limitations** | Tableau Desktop/Public is not installed locally so no `.twbx` binary was packaged; `docs/TABLEAU_INTEGRATION.md` documents the workbook spec and all 5 live CSV extracts are served via `/api/v1/exports/tableau/{dataset}.csv`. |
| **Next Task** | `STOP` (Phase 06 complete) |
