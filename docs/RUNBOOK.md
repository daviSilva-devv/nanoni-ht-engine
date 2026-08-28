# Local Runbook

## First boot

1. Copy `.env.example` -> `.env`.
2. `python scripts/init_local_dirs.py`.
3. `cd backend`.
4. `python -m pip install -e '.[dev]'`.
5. `alembic upgrade head`.
6. `python -m nanoni.scripts.seed_demo` (optional).
7. `pytest -q`.
8. `uvicorn nanoni.api.main:app --reload --port 8010`.

Swagger: `http://127.0.0.1:8010/docs`.

Admin requests use `X-Admin-Token` from `.env`.

## Fresh migration drill

Delete the local SQLite DB, run `alembic upgrade head`, then `alembic check`. A fresh schema must be reproducible without `Base.metadata.create_all()`.

## Failure principle

Never manually edit DB status to hide a problem. Resolve through an explicit admin operation/job and keep an audit trail.

## Media principle

`inbox -> processing -> remote confirmed -> published/purge`. Failed work goes to `failed`; it is not silently deleted.
