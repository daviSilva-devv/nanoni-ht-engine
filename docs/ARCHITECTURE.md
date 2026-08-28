# Architecture

## Goal

One generic engine must operate one community at launch and many communities later without code branches per commercial niche.

## Runtime split

### Control Plane (light, 24/7 when launched)

Owns durable state:

- catalog/configuration;
- customers/leads;
- orders/payments;
- entitlements/membership grants;
- persistent jobs;
- alerts/audit;
- bot/sales routing;
- admin API.

### Media Worker (local workstation)

Owns temporary heavy work:

- source inspection;
- selective acquisition;
- ffprobe/FFmpeg later;
- preview generation;
- hashing/deduplication;
- upload to Telegram Vault/publisher;
- purge after confirmed remote persistence.

Both can run in one process during development. They are separated in code/contracts so moving the control plane to a tiny 24/7 host later does not require a rewrite.

## Domain boundaries

- `Catalog`: Niche, MicroNiche, Community, CommunityVersion, Destination, Topic, Product, PricePlan, Offer, Copy.
- `Content`: Source, Candidate, Manifest, Pack, Asset, Approval.
- `Publishing`: Rule, Window, PublicationJob, Publication, Metrics.
- `Commerce`: Customer, Lead, Order, Payment, PaymentEvent.
- `Access`: Entitlement, MembershipGrant.
- `Operations`: Job, Alert, Audit, Moderation.

## Critical separations

1. `CommunityVersion != TelegramDestination` — a group can be replaced without deleting rights already sold.
2. `Payment != Entitlement != MembershipGrant` — receiving money does not directly execute Telegram actions.
3. `MediaManifest != downloaded file` — inspect first, acquire selected media later.
4. `Admin search != public moderation` — internal organization does not use a naive word blacklist.
5. `SourceAdapter != Content Engine` — adding a site must not change pack/approval/publishing code.

## Idempotency

- Order: unique `idempotency_key`.
- Provider payment: unique `(provider, provider_charge_id)`.
- Provider webhook: unique `(provider, provider_event_id)`.
- Entitlement: unique `source_order_item_id`.
- Membership: unique `(entitlement_id, destination_id)`.
- Publication: unique `publication_job_id`.
- Persistent Job: optional unique `idempotency_key`.

## Current external-integration status

Implemented contracts + mocks:

- payment provider;
- source adapters;
- Telegram publisher boundary;
- helper manifest bridge.

Real external credentials/providers are deliberately not hardcoded in the foundation.
