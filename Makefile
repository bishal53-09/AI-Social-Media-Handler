.PHONY: install dev-backend dev-frontend test lint typecheck format check doctor

PY ?= .venv/bin/python

install:
	bash setup.sh

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
