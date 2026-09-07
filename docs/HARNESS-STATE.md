CURRENT_PHASE: 8
STATUS: WIP_BLOCKED_EXTERNAL
BRANCH: wip/phase-8
HEAD: 5c667dd (before the BravoPay implementation checkpoint commit)
LAST_GREEN_PHASE: 7
LAST_GREEN_COMMIT: 718fee7

CURRENT_WORK:
- Phase 8 Payment + Access; EXTERNAL_PIX and BravoPay are the approved V1 mode/provider.
- Deterministic implementation is GREEN; only real credential, payment, webhook, withdrawal, and compliance gates remain externally blocked.

DONE:
- Phase 6 GREEN on main; tag phase-6-green.
- Phase 7 GREEN on main at 718fee7; tag phase-7-green.
- Phase 7 closure gate: 84 passed, 1 expected PostgreSQL skip; Ruff, compileall, Alembic current/check green.
- Existing foundation includes mock payments, idempotent payment events, entitlement fulfillment, and membership-grant planning.
- Fulfillment now materializes membership grants for every active entitlement and repairs missing grants on an idempotent replay.
- Authenticated Telegram join-request webhook approves only the matching `telegram_user_id` with an active, unexpired entitlement; unknown/expired users are declined.
- Join-request replay is idempotent and a previously removed member may reenter while the entitlement remains active.
- Expiry jobs transition due entitlements and remove their active Telegram memberships exactly once.
- Provider-neutral Phase 8 focused gate: 16 tests passed; Ruff and diff checks clean.
- `BravoPayProvider` implements the official `https://bravopay.club/api/v1` transaction contract without changing the PaymentProvider boundary.
- PIX creation sends integer `amount_cents`, `method=pix`, internal Order ID as `external_reference`, correlation metadata, configured `expires_in`, Bearer auth, and `Idempotency-Key`.
- PIX response persists the documented `pix.copy_paste` and `pix.expires_at`; recheck uses `GET /transactions/{id}`.
- Dedicated BravoPay webhook verifies the raw body with HMAC-SHA256, `compare_digest`, both documented signature headers, and a five-minute timestamp tolerance before parsing any event.
- Paid, expired, failed, refunded, and chargeback events are reconciled against charge ID, Order ID, amount, and currency; event replay remains idempotent.
- Refund revokes entitlements and queues Telegram membership removal; chargeback is recorded and sends the order to `REVIEW_REQUIRED` without inventing a payment state.
- HTTP client retries timeouts, 429 (honoring numeric `Retry-After`), and 5xx with bounded backoff; errors do not expose credentials.
- Phase 8 deterministic final gate: 112 passed, 1 expected PostgreSQL skip; Ruff, compileall, and diff check clean.
- `code-review-and-quality` final review approved after recheck, refund-transition, and chargeback-state corrections.

TODO:
- Configure local-only BravoPay API key and webhook secret, with `NANONI_PAYMENT_PROVIDER=bravopay`.
- Run exactly one minimum-value unpaid PIX creation gate, then a separate real small-payment/replay gate.
- Configure public HTTPS callbacks for BravoPay and Telegram; run real join, expiry, and reentry gates.
- Before GO-LIVE, complete the written category approval and small withdrawal/descriptor checks below.

PAYMENT_PROVIDER_STATUS:
- payment mode: EXTERNAL_PIX
- official V1 provider: BravoPay
- provider decision explicitly approved by the operator
- PIX checkout remains an independent web storefront; Telegram handles identity, claim, access, support, and content only

BLOCKERS:
- BravoPay API key and webhook secret are not configured locally; no real charge was created.
- Public HTTPS BravoPay and Telegram callback URLs are not available/configured yet.
- A real small payment, webhook replay, Telegram access lifecycle, and small withdrawal have not been exercised.
- Before GO-LIVE: obtain written BravoPay acceptance of the fully disclosed lawful adult 18+ segment and confirm KYC, reserve, settlement, withdrawal, and merchant descriptor/receiver terms.
- Before accumulating material balance: validate one small withdrawal and the payer-visible descriptor/receiver.

NEXT:
- Add the local-only BravoPay credentials and public HTTPS callbacks, then resume with the single-charge real gate and end-to-end paid/access gate.

IMPORTANT_NOTES:
- Phase 8 must not merge into main until its real payment/access gate is GREEN.
- BravoPay is selected for V1; do not add or substitute another production provider without a new explicit decision.
- Never commit .env, Telegram tokens, API keys, webhook secrets, runtime media, or temporary files.
- Telegram Vault credentials previously used for real gates remain local-only and must not be printed or committed.
