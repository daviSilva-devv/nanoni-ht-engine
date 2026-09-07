CURRENT_PHASE: 8
STATUS: WIP_BLOCKED_EXTERNAL
BRANCH: wip/phase-8
HEAD: f5b47be (before the home-handoff checkpoint commit)
LAST_GREEN_PHASE: 7
LAST_GREEN_COMMIT: 718fee7

CURRENT_WORK:
- Phase 8 Payment + Access discovery; no production provider adapter has been implemented.

DONE:
- Phase 6 GREEN on main; tag phase-6-green.
- Phase 7 GREEN on main at 718fee7; tag phase-7-green.
- Phase 7 closure gate: 84 passed, 1 expected PostgreSQL skip; Ruff, compileall, Alembic current/check green.
- Existing foundation includes mock payments, idempotent payment events, entitlement fulfillment, and membership-grant planning.

TODO:
- Explicitly select and approve a production payment provider.
- Implement the selected provider, signed webhook verification, payment recheck, real-payment gate, Telegram access, expiry, and reentry.
- Keep external checkout disabled until the payment/compliance decision is explicit.

PAYMENT_PROVIDER_STATUS:
- decision pending
- candidates evaluated: PandaBlue / WiinPay / Iugu / Cartwave / BravoPay
- do not assume final provider until explicitly selected

BLOCKERS:
- Written provider approval for the fully disclosed lawful adult/high-risk category, including KYC, reserve, settlement, and withdrawal terms.
- Explicit compliance choice between Telegram Stars inside the bot and an independent external PIX storefront where the bot only handles identity, claim, and access.
- Production credentials, signed-webhook configuration, public HTTPS callback, and a real small payment are not available yet.

NEXT:
- At home, fetch wip/phase-8 and explicitly select the approved provider before writing any provider-specific code.

IMPORTANT_NOTES:
- Phase 8 must not merge into main until its real payment/access gate is GREEN.
- No provider candidate is selected by this checkpoint.
- Never commit .env, Telegram tokens, API keys, webhook secrets, runtime media, or temporary files.
- Telegram Vault credentials previously used for real gates remain local-only and must not be printed or committed.
