# Nanoni Engine — Real Foundation

This repository is the executable foundation for the Nanoni content/community commerce engine.
It is intentionally **not** the finished product. It is the stable base from which Codex can implement the product phase-by-phase without re-designing the core every time.

## What is already real

- FastAPI application that boots locally.
- SQLAlchemy domain model with catalog, content, publishing, commerce, access, jobs, alerts and audit tables.
- Alembic initial migration.
- CRUD/API primitives for niches, communities, products, copy, content candidates and orders.
- Persistent job queue primitives and retry-safe state transitions.
- Mock payment provider with idempotent payment confirmation.
- Entitlement/access engine separated from payment.
- Sales-router state machine and event history.
- Randomized schedule-window selector for FREE/VIP publication rules.
- Content score and source score calculations.
- Basic moderation rule engine scaffold (public community only; admin search remains unrestricted).
- Source adapter contract and Erome public-album inspector/acquirer base.
- Assisted Telegram browser-helper contract; it does not implement protected-content bypass.
- Watch-folder runtime layout and cleanup policy.
- Minimal Next.js admin shell structured around the backend API.
- Automated backend test suite including an end-to-end mock purchase/access flow.

## Product boundary

V1 is considered done only when the real path works reliably:

`collect -> approve -> publish -> external checkout/payment -> entitlement -> Telegram access`

At that point feature work stops and launch/traffic starts.

## Quick start (zero-cost local mode)

```bash
cp .env.example .env
python scripts/init_local_dirs.py
cd backend
python -m pip install -e '.[dev]'
alembic upgrade head
pytest -q
uvicorn nanoni.api.main:app --reload --port 8010
```

SQLite is the default so the base works without Docker. To use Postgres, run `docker compose up -d db` and set:

```env
NANONI_DATABASE_URL=postgresql+psycopg://nanoni:nanoni@localhost:5432/nanoni
```

Admin shell:

```bash
cd admin
npm install
npm run dev
```

## Important operational design

Heavy media lives only temporarily on the local workstation. The control plane stores metadata and Telegram references. Payment and access are separate state machines. A Telegram group can be replaced without deleting the customer's commercial entitlement.

See `docs/BASE-OFICIAL.md` for the full product contract and `docs/IMPLEMENTATION-PLAN.md` for the Codex phase gates.
