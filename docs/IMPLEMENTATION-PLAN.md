# Implementation Plan / Gates

The repository already completes a meaningful part of Phase 0 and establishes the domain skeleton for Phase 1/2. Do not skip gates just because classes already exist.

## Phase 0 — Foundation

Already present:

- package/config/logging;
- SQLite zero-cost mode + Postgres compose;
- Alembic initial migration;
- persistent jobs;
- admin token boundary;
- test harness.

Gate before continuing: fresh database migration + tests pass.

## Phase 1 — Domain/Admin Core

Finish editable CRUD UX for:

- niche/microniche;
- community/version;
- destinations/topics;
- product/price plans/offers;
- copy slots/variants.

Gate: a new community with six content topics and weekly/monthly/lifetime plans can be created without code changes.

## Phase 2 — Content Core

Finish:

- local file probe metadata;
- watch-folder watcher;
- approval UI;
- pack editing/ordering;
- derivatives contract;
- sha256 and duplicate review workflow.

Gate: drag/import a mixed media pack, approve only selected items and see it READY without manual DB work.

## Phase 3 — Erome public adapter

Finish:

- public album inspect;
- optional search/profile discovery only if stable and necessary;
- selected acquisition;
- content-length/progress/retry;
- fixture-based regression tests.

Gate: mixed album -> manifest -> select -> acquire selected only.

## Phase 4 — Telegram Vault + Publisher

Implement the `TelegramPublisher` boundary using Bot API/local Bot API where appropriate.

Gate: approved pack publishes to the configured destination/topic exactly once; references are saved; local purge happens only after confirmation.

## Phase 5 — Scheduler

Persisted planner + randomized windows, heavier night windows, daily microniche pack windows, queue-empty alerts.

Gate: simulated 24h has no duplicate and no out-of-window publication.

## Phase 6 — Telegram Helper

Evolve MV3 helper + localhost/native bridge for metadata and user-authorized local file import.

Gate: current Telegram post context becomes a candidate with minimal operator work.

## Phase 7 — Sales Router

18+ gate, configurable hero media/copy, short button routing, lead events, FREE route, product/plan selection.

Gate: hot lead reaches checkout choice in minimal steps.

## Phase 8 — Payment + Access

Select a production provider that explicitly accepts the lawful adult/high-risk category. Implement external-checkout mode behind feature flag, webhook verification, provider recheck, entitlement, join-request access and expiry/reentry.

Gate: real small payment grants exactly one entitlement/access and survives webhook replay.

## Phase 9 — Recovery/Upsell

Two bounded recovery touches, one post-purchase upsell, cadence/eligibility rules.

## Phase 10 — Engagement/Moderation/Metrics

Replies, unique repliers, reactions, Content Score, source score, moderation events and conversion dashboard.

## Phase 11 — Hardening/Launch

Backup/restore drill, disk quota, process restart drill, destination replacement, provider outage, alert chat, runbooks.

**V1 stop condition:** the full money path is green. Stop feature work and launch.
