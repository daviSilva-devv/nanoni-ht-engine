# ADR-001 — Separate commercial rights from Telegram infrastructure

**Accepted.**

`CommunityVersion` is the immutable commercial promise. `TelegramDestination` is replaceable infrastructure. `Entitlement` binds a customer to the version sold. `MembershipGrant` materializes that right in a concrete Telegram destination.

Why: groups/topics can disappear or be replaced. Lifetime must survive a technical migration but must not silently expand into future commercial versions.
