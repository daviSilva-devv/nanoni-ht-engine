PYTHON ?= python

.PHONY: install test lint api seed dirs migrate reset-db

install:
	cd backend && $(PYTHON) -m pip install -e ".[dev]"

test:
	cd backend && pytest -q

lint:
	cd backend && ruff check src tests

api:
	cd backend && uvicorn nanoni.api.main:app --reload --port 8010

seed:
	cd backend && $(PYTHON) -m nanoni.scripts.seed_demo

dirs:
	$(PYTHON) scripts/init_local_dirs.py

migrate:
	cd backend && alembic upgrade head

reset-db:
	rm -f backend/nanoni.db nanoni.db
