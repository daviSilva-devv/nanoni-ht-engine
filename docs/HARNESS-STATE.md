CURRENT_PHASE: 4B
STATUS: IN_PROGRESS
AGENT: Codex
BASE_COMMIT: abc9663
LAST_GREEN_PHASE: 4A
LAST_GREEN_COMMIT: abc9663
CURRENT_WORK: Telegram Publisher
BLOCKERS: none
BLOCKED_EXTERNAL: none
NEXT: Implement the TelegramPublisher boundary and gate approved-pack publication to a configured destination/topic exactly once.

DONE:
- TelegramMediaGateway: HTTPX streaming upload with progress callback, retry/backoff on 429 + 5xx, honours retry_after.
- Normal Bot API vs Local Bot API selection driven by configured upload-size limit (NANONI_TELEGRAM_BOT_API_MAX_UPLOAD_BYTES); Local API required error when file exceeds limit and no local URL set.
- Vault persistence: upload_asset_to_vault writes telegram_file_id, telegram_file_unique_id, vault_chat_id, vault_message_id on MediaAsset and a verified VaultObject row; asset -> VAULTED.
- Idempotency: enqueue_pack_vault_uploads dedupes by idempotency_key upload-vault:<asset>:<chat> and skips already-vaulted assets; upload_asset_to_vault is a no-op when a verified VaultObject already exists.
- Job handler UPLOAD_VAULT in worker with progress persisted to job.payload (bytes_sent/total_bytes), gateway always closed, asset -> FAILED on error with re-raise for retry.
- Restart recovery: engine.recover_stale requeues RUNNING jobs whose lock is older than stale_after; run_once calls it before claim_next.
- Local file is never deleted before a safe confirmation (asserted by tests).
- Admin endpoints: POST /api/v1/vault/packs/{pack_id}, GET /api/v1/vault/assets/{asset_id}; require_admin enforced; vault chat id comes from settings, never hardcoded.
- Migration bd14ac8e712f adds media_assets.vault_chat_id (+ index); down_revision 9c7a2e41f5b8.
- .env.example: NANONI_TELEGRAM_LOCAL_API_BASE_URL, NANONI_TELEGRAM_VAULT_CHAT_ID, NANONI_TELEGRAM_BOT_API_MAX_UPLOAD_BYTES.

DETERMINISTIC_GATES (all GREEN):
- pytest backend: 60 passed, 1 skipped (Postgres env gate), incl. tests/test_telegram_vault.py (6).
- ruff check src tests: clean.
- python -m compileall src: clean.
- alembic upgrade head: clean; alembic check: no new upgrade operations.

IMPORTANT_NOTES:
- Phase 4A is backend-only; no frontend changes, Next.js build gate not re-run.
- Phase 4A real gate GREEN: Telegram send + getFile succeeded with a sub-50 MB generated fixture.
- Real gate persisted telegram_file_id, telegram_file_unique_id, vault_chat_id, vault_message_id and a verified VaultObject; MediaAsset became VAULTED.
- The local fixture remained present after confirmation; a repeated service call and repeated enqueue produced no duplicate upload/job.
- Targeted closure checks: vault admin auth test passed; Alembic current is bd14ac8e712f (head), and Alembic check reports no new operations.
- Phase 4A was fast-forwarded to main and tagged phase-4a-green at abc9663.
