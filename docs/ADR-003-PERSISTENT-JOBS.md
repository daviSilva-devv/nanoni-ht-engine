# ADR-003 — Persistent DB jobs in V1

**Accepted.**

V1 uses a DB-backed job table and small worker loop rather than mandatory Redis/Celery.

Why: near-zero fixed cost and restart safety are more valuable than premature distributed infrastructure. Job interfaces allow later replacement if measured load requires it.
