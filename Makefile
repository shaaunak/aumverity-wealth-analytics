.PHONY: dev backend frontend test test-backend test-frontend build-frontend lint

dev:
	@echo "Starting AUMVERITY backend (port 8000) and frontend (port 5173)..."
	@bash -c 'trap "kill 0" EXIT; \
		(.venv/bin/uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000) & \
		(cd frontend && npm run dev) & \
		wait'

backend:
	.venv/bin/uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000

frontend:
	cd frontend && npm run dev

test: test-backend test-frontend

test-backend:
	.venv/bin/pytest

test-frontend:
	cd frontend && npm run typecheck && npm run test

build-frontend:
	cd frontend && npm run build

lint:
	.venv/bin/ruff check backend tests
