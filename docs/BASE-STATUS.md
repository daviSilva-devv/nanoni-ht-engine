# Base Status — what is real today

## Green / executable

- Backend boots under FastAPI.
- SQLite zero-cost local mode.
- Postgres deployment path and compose file.
- Full initial Alembic schema from empty DB.
- Generic domain schema for catalog, products/versioning, content packs, publishing, customers, payments, entitlements, membership, jobs, moderation and audit.
- Admin-token protected control-plane endpoints.
- Content manifest import and selective pack approval.
- Public Erome mixed-album HTML parser and selective acquisition boundary.
- Manual/watch-folder content ingestion.
- Persistent idempotent jobs/retry primitives.
- Random schedule windows including cross-midnight/night weighting.
- Configurable weighted copy engine.
- Mock external-payment flow with replay-safe webhook event handling.
- Exactly-once entitlement creation per order item.
- Replaceable Telegram destination membership planning.
- Content/source scoring primitives.
- Rule-driven public moderation separated from admin search.
- Browser-helper manifest bridge with HMAC.
- Minimal admin UI shell consuming the backend read APIs.

## Intentionally not fake-completed

These are real next phases, not empty files pretending to be done:

- Telegram Bot API publisher/vault integration.
- Real adult/high-risk-friendly PIX provider selection and credentials.
- Telegram join-request membership executor.
- FFmpeg/ffprobe media probing and 50-second derivative generation.
- Full admin CRUD forms/approval swipe UI.
- Real Erome network fixture regression (requires live/recorded fixture at implementation time).
- Native local bridge for helper file imports.
- Reaction/reply Telegram event collector.
- Production deployment/monitoring.

The foundation keeps interfaces and durable state ready for these without claiming they already exist.
