# AUMVERITY — System Architecture

## 1. End-to-End Data & Application Flow

```text
Synthetic Data Generator (Python / Pandas / NumPy)
  │
  ▼
PostgreSQL: raw.* tables (append-only source records, dual dates, UTC timestamps)
  │
  ▼
PostgreSQL: staging.* views/tables (type casting, deduplication, validation flags)
  │
  ▼
PostgreSQL: marts.* (CTEs, window functions, EOP snapshots, asset movement bridge)
  │
  ├──► PostgreSQL: reconciliation.* (automated tie-outs & variance checks)
  │
  ▼
FastAPI Backend (SQLAlchemy 2.0, Pydantic v2, Decimal precision)
  │
  ├──► React + TypeScript + Vite UI (ECharts, TanStack Query/Table)
  └──► Reporting & Exports (openpyxl Excel workbooks + Tableau CSVs)
```

## 2. Repository Layout

- `frontend/`: React + TypeScript + Vite analytical interface.
- `backend/`: FastAPI application, SQLAlchemy models, Alembic migrations, services.
- `data/generator/`: Deterministic synthetic wealth management data generator.
- `data/seeds/`: Seed configuration and reference tables.
- `sql/raw/`, `sql/staging/`, `sql/marts/`, `sql/reconciliation/`, `sql/tests/`: Layered SQL definitions and SQL-level data quality tests.
- `tests/unit/`, `tests/integration/`, `tests/e2e/`: Automated test suites.
- `infra/`: Dockerfiles and PostgreSQL schema initialization scripts.
- `docs/`: Project specification, methodology, data dictionary, ADRs, progress log, demo script.
- `exports/`: Generated Excel and CSV output directory (gitignored).

## 3. Infrastructure & Observability

- **Health & Readiness:**
  - `GET /health`: Liveness probe returning app version, calculation version, currency, and `SYNTHETIC` data classification.
  - `GET /ready`: Readiness probe executing `SELECT 1` against PostgreSQL (returns `200` when connected, `503` when disconnected).
- **Logging:** Single-line structured JSON logs to `stdout`.
