.PHONY: install dev update dev-backend dev-frontend test lint typecheck format check doctor

PY ?= .venv/bin/python

install:
	bash setup.sh

# Backend + frontend together; prints the dashboard URL. Ctrl+C stops both.
# Options: make dev OPEN_BROWSER=1  BACKEND_PORT=8000  FRONTEND_PORT=3000
dev:
	bash scripts/dev.sh

# Fast-forward to the latest upstream commit, reinstall dependencies, run migrations.
# Refuses if you have uncommitted changes. Stop `make dev` first.
update:
	bash scripts/update.sh

dev-backend:
	$(PY) -m app.cli serve

dev-frontend:
	cd web && npm run dev

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check . && $(PY) -m ruff format --check .
	cd web && npm run lint

typecheck:
	$(PY) -m mypy
	cd web && npm run typecheck

format:
	$(PY) -m ruff format .
	cd web && npm run format

check: lint typecheck test

doctor:
	$(PY) -m app.cli doctor
