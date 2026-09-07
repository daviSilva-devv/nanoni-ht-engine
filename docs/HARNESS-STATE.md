CURRENT_PHASE: 8
STATUS: BLOCKED_EXTERNAL
AGENT: Codex
BASE_COMMIT: 718fee7
LAST_GREEN_PHASE: 7
LAST_GREEN_COMMIT: 718fee7
CURRENT_WORK: Payment + Access
BLOCKERS: Production PIX merchant approval and Telegram payment-mode compliance decision
BLOCKED_EXTERNAL: Obtain written merchant approval for the fully disclosed lawful adult category and choose either Telegram Stars inside the bot or an independent external PIX storefront where the bot only handles identity/claim/access.
NEXT: After the external decision, configure the approved provider credentials, HMAC webhook secret, public HTTPS webhook URL, and backend egress-IP whitelist; then implement and run the real small-payment gate.

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
- pytest backend: 69 passed, 1 skipped (Postgres env gate), incl. Telegram Vault and Publisher coverage.
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
- Phase 4B real gate GREEN: a vaulted telegram_file_id was published to the configured Telegram destination and message references were persisted.
- Publication queue and delivery are idempotent; an atomic PUBLISHING marker prevents automatic replay after ambiguous timeout/5xx outcomes.
- Publication worker reuses Telegram file IDs, supports destination topics/protected content, and persists Publication rows before local purge.
- Purge is restricted to assets backed by verified VaultObjects and occurs only after confirmed publication persistence; failure paths retain local files.
- Fresh-database migration gate passed through 45d9ee8b602a; Alembic check found no pending operations.
- Phase 4B was fast-forwarded to main and tagged phase-4b-green at 69ca546.
- Phase 5 GREEN: persisted PublicationPlan slots with weighted random windows, configurable spacing, target/microniche inventory selection, and idempotent dispatch creation.
- Simulated 24h gate produced no duplicate or out-of-window publications and preserved global minimum spacing across topic rules.
- Empty inventory persists SKIPPED_NO_CONTENT slots and opens one deduplicated queue-empty alert; stock-days endpoint reports remaining eligible packs.
- Fresh-database migration gate passed through 9af4f0aa31d8; backend gate is 73 passed, 1 expected PostgreSQL skip.
- Phase 5 was fast-forwarded to main and tagged phase-5-green at 473d140.
- Phase 6 deterministic implementation: MV3 selects the visible Telegram message, extracts scoped post/album metadata, and submits a normalized signed manifest.
- The localhost bridge can auto-create the telegram-helper source and returns candidate + pack identity in one action.
- Optional operator-selected files are streamed into processing and linked to the same candidate; duplicate/replayed files do not create duplicate pack items, and purged assets can be restored.
- Helper manifest and file endpoints use HMAC authentication; file-link signatures expire after five minutes.
- Phase 6 deterministic gate: 77 passed, 1 expected PostgreSQL skip; Ruff, compileall, Alembic check, JS syntax, and MV3 manifest parsing are green.
- Phase 6 real browser gate GREEN: Telegram Helper created Candidate 2c70e144-8eaa-4920-83be-4664f7fb3bee through the operator-authenticated Telegram Web flow.
- The real Candidate is backed by the telegram-helper Source, linked to its pack, retains Telegram post context, and contains six persisted media items.
- Phase 6 was fast-forwarded to main and tagged phase-6-green at 369a831.
- Phase 7 GREEN: public Sales Router enforces explicit 18+ confirmation, renders configured hero copy/media and configurable VIP/FREE CTA labels, and records lead transitions.
- A single active product skips product discovery; multiple active products require an explicit choice, and only active plans belonging to the selected product reach CHECKOUT_CHOICE.
- FREE routing resolves an active FREE destination through its public username or configured invite URL and preserves the lead history.
- Phase 7 gate reaches checkout choice in four calls from a new lead (start, age confirmation, VIP intent, plan choice), with the product step removed when unambiguous.
- Phase 7 closure gate: 84 passed, 1 expected PostgreSQL skip; Ruff, compileall, Alembic current, and Alembic check are green.
- Phase 7 was fast-forwarded to main and tagged phase-7-green at 718fee7.
- Phase 8 provider discovery: GGPIXAPI publicly documents adult-content PIX, dynamic PIX creation, transaction status lookup, externalId idempotency, and optional HMAC-SHA256 webhook authentication.
- No production payment-provider configuration or credentials are present in the process environment or a local .env.
- Telegram's current official digital-goods policy requires Telegram Stars for sales performed inside bots/mini apps, even when an external website exists; external PIX must therefore remain an independent storefront flow pending explicit compliance approval.
