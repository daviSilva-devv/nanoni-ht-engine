from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import JSON as SAJSON
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from nanoni.core.db import Base
from nanoni.domain.enums import (
    ApprovalDecision,
    AssetStatus,
    CandidateStatus,
    DestinationStatus,
    DestinationType,
    DuplicateClassification,
    EntitlementStatus,
    JobStatus,
    JobType,
    LeadState,
    MediaType,
    MembershipStatus,
    ModerationSeverity,
    OfferKind,
    OrderStatus,
    PackStatus,
    PaymentStatus,
    PlanKind,
    PublicationStatus,
    PublicationTarget,
    Severity,
    TopicRole,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


class AdminUser(TimestampMixin, Base):
    __tablename__ = "admin_users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(String(32), default="SUPERADMIN")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Setting(TimestampMixin, Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(SAJSON)


class Niche(TimestampMixin, Base):
    __tablename__ = "niches"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class MicroNiche(TimestampMixin, Base):
    __tablename__ = "microniches"
    __table_args__ = (UniqueConstraint("niche_id", "slug", name="uq_microniche_niche_slug"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    niche_id: Mapped[str] = mapped_column(ForeignKey("niches.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Community(TimestampMixin, Base):
    __tablename__ = "communities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    niche_id: Mapped[str] = mapped_column(ForeignKey("niches.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CommunityVersion(TimestampMixin, Base):
    __tablename__ = "community_versions"
    __table_args__ = (UniqueConstraint("community_id", "version", name="uq_community_version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    community_id: Mapped[str] = mapped_column(ForeignKey("communities.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    promise_snapshot: Mapped[dict] = mapped_column(SAJSON, default=dict)
    active_for_sale: Mapped[bool] = mapped_column(Boolean, default=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CommunityVersionMicroNiche(Base):
    __tablename__ = "community_version_microniches"
    community_version_id: Mapped[str] = mapped_column(
        ForeignKey("community_versions.id", ondelete="CASCADE"), primary_key=True
    )
    microniche_id: Mapped[str] = mapped_column(
        ForeignKey("microniches.id", ondelete="CASCADE"), primary_key=True
    )


class TelegramDestination(TimestampMixin, Base):
    __tablename__ = "telegram_destinations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    community_id: Mapped[str | None] = mapped_column(ForeignKey("communities.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    destination_type: Mapped[str] = mapped_column(String(32), default=DestinationType.FREE_CHANNEL)
    telegram_chat_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default=DestinationStatus.ACTIVE)
    replacement_destination_id: Mapped[str | None] = mapped_column(
        ForeignKey("telegram_destinations.id")
    )
    protected_content: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column(SAJSON, default=dict)


class Topic(TimestampMixin, Base):
    __tablename__ = "topics"
    __table_args__ = (
        UniqueConstraint("destination_id", "message_thread_id", name="uq_topic_thread"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    destination_id: Mapped[str] = mapped_column(ForeignKey("telegram_destinations.id"), index=True)
    microniche_id: Mapped[str | None] = mapped_column(ForeignKey("microniches.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    role: Mapped[str] = mapped_column(String(24), default=TopicRole.CONTENT)
    message_thread_id: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Product(TimestampMixin, Base):
    __tablename__ = "products"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    community_version_id: Mapped[str] = mapped_column(
        ForeignKey("community_versions.id"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class PricePlan(TimestampMixin, Base):
    __tablename__ = "price_plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24), default=PlanKind.MONTHLY)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    duration_days: Mapped[int | None] = mapped_column(Integer)
    lifetime: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Offer(TimestampMixin, Base):
    __tablename__ = "offers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(32), default=OfferKind.DISCOUNT)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict] = mapped_column(SAJSON, default=dict)


class OfferProduct(Base):
    __tablename__ = "offer_products"
    offer_id: Mapped[str] = mapped_column(
        ForeignKey("offers.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(24), default="TARGET")


class CopySlot(TimestampMixin, Base):
    __tablename__ = "copy_slots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class CopyVariant(TimestampMixin, Base):
    __tablename__ = "copy_variants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    slot_id: Mapped[str] = mapped_column(
        ForeignKey("copy_slots.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    media_asset_id: Mapped[str | None] = mapped_column(String(36))
    weight: Mapped[int] = mapped_column(Integer, default=10)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Source(TimestampMixin, Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    adapter: Mapped[str] = mapped_column(String(64))
    locator: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    default_niche_id: Mapped[str | None] = mapped_column(ForeignKey("niches.id"))
    config: Mapped[dict] = mapped_column(SAJSON, default=dict)
    approval_count: Mapped[int] = mapped_column(Integer, default=0)
    presented_count: Mapped[int] = mapped_column(Integer, default=0)
    published_count: Mapped[int] = mapped_column(Integer, default=0)
    engagement_score: Mapped[float] = mapped_column(Float, default=0.0)


class ContentCandidate(TimestampMixin, Base):
    __tablename__ = "content_candidates"
    __table_args__ = (
        UniqueConstraint("source_id", "source_item_id", name="uq_candidate_source_item"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), index=True)
    source_item_id: Mapped[str] = mapped_column(String(255), index=True)
    source_collection_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(500))
    caption: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default=CandidateStatus.PENDING_APPROVAL)
    duplicate_classification: Mapped[str] = mapped_column(
        String(32), default=DuplicateClassification.NEW
    )
    manifest: Mapped[dict] = mapped_column(SAJSON, default=dict)
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ContentPack(TimestampMixin, Base):
    __tablename__ = "content_packs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("content_candidates.id"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(500))
    caption: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default=PackStatus.REVIEW)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    content_score: Mapped[float] = mapped_column(Float, default=0.0)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    metadata_json: Mapped[dict] = mapped_column(SAJSON, default=dict)


class MediaAsset(TimestampMixin, Base):
    __tablename__ = "media_assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str | None] = mapped_column(
        ForeignKey("content_candidates.id"), index=True
    )
    media_type: Mapped[str] = mapped_column(String(16), default=MediaType.VIDEO)
    source_locator: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(String(500))
    mime: Mapped[str | None] = mapped_column(String(120))
    extension: Mapped[str | None] = mapped_column(String(16))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    file_size: Mapped[int | None] = mapped_column(Integer)
    bitrate: Mapped[int | None] = mapped_column(Integer)
    source_caption: Mapped[str | None] = mapped_column(Text)
    source_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    thumbnail_ref: Mapped[str | None] = mapped_column(Text)
    local_path: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    telegram_file_id: Mapped[str | None] = mapped_column(Text)
    telegram_file_unique_id: Mapped[str | None] = mapped_column(String(255), index=True)
    vault_chat_id: Mapped[str | None] = mapped_column(String(64), index=True)
    vault_message_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default=AssetStatus.DISCOVERED)
    metadata_json: Mapped[dict] = mapped_column(SAJSON, default=dict)


class PackItem(Base):
    __tablename__ = "pack_items"
    __table_args__ = (UniqueConstraint("pack_id", "position", name="uq_pack_position"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pack_id: Mapped[str] = mapped_column(
        ForeignKey("content_packs.id", ondelete="CASCADE"), index=True
    )
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(24), default="MASTER")
    selected: Mapped[bool] = mapped_column(Boolean, default=True)
    derivative_of_asset_id: Mapped[str | None] = mapped_column(ForeignKey("media_assets.id"))
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id"), index=True)
    source_external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    source_reference: Mapped[str | None] = mapped_column(Text)
    original_filename: Mapped[str | None] = mapped_column(String(500))
    metadata_json: Mapped[dict] = mapped_column(SAJSON, default=dict)


class ContentPackMicroNiche(Base):
    __tablename__ = "content_pack_microniches"
    pack_id: Mapped[str] = mapped_column(
        ForeignKey("content_packs.id", ondelete="CASCADE"), primary_key=True
    )
    microniche_id: Mapped[str] = mapped_column(
        ForeignKey("microniches.id", ondelete="CASCADE"), primary_key=True
    )


class Approval(TimestampMixin, Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(ForeignKey("content_candidates.id"), index=True)
    admin_user_id: Mapped[str | None] = mapped_column(ForeignKey("admin_users.id"))
    decision: Mapped[str] = mapped_column(String(24), default=ApprovalDecision.DEFERRED)
    target: Mapped[str | None] = mapped_column(String(16))
    microniche_id: Mapped[str | None] = mapped_column(ForeignKey("microniches.id"))
    notes: Mapped[str | None] = mapped_column(Text)


class PublicationRule(TimestampMixin, Base):
    __tablename__ = "publication_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    destination_id: Mapped[str] = mapped_column(ForeignKey("telegram_destinations.id"), index=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"), index=True)
    microniche_id: Mapped[str | None] = mapped_column(ForeignKey("microniches.id"), index=True)
    target: Mapped[str] = mapped_column(String(16), default=PublicationTarget.FREE)
    posts_per_day: Mapped[int] = mapped_column(Integer, default=1)
    randomize_within_window: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(SAJSON, default=dict)


class ScheduleWindow(TimestampMixin, Base):
    __tablename__ = "schedule_windows"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    publication_rule_id: Mapped[str] = mapped_column(
        ForeignKey("publication_rules.id", ondelete="CASCADE"), index=True
    )
    start_minute: Mapped[int] = mapped_column(Integer)  # minutes after midnight
    end_minute: Mapped[int] = mapped_column(Integer)
    weight: Mapped[int] = mapped_column(Integer, default=10)
    label: Mapped[str | None] = mapped_column(String(80))


class PublicationJob(TimestampMixin, Base):
    __tablename__ = "publication_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pack_id: Mapped[str] = mapped_column(ForeignKey("content_packs.id"), index=True)
    rule_id: Mapped[str | None] = mapped_column(ForeignKey("publication_rules.id"), index=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey("telegram_destinations.id"), index=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"), index=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default=PublicationStatus.QUEUED)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)


class Publication(TimestampMixin, Base):
    __tablename__ = "publications"
    __table_args__ = (UniqueConstraint("publication_job_id", name="uq_publication_job_once"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    publication_job_id: Mapped[str] = mapped_column(ForeignKey("publication_jobs.id"))
    pack_id: Mapped[str] = mapped_column(ForeignKey("content_packs.id"), index=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey("telegram_destinations.id"), index=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"), index=True)
    telegram_message_ids: Mapped[list] = mapped_column(SAJSON, default=list)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    copy_variant_id: Mapped[str | None] = mapped_column(ForeignKey("copy_variants.id"))


class PublicationMetric(TimestampMixin, Base):
    __tablename__ = "publication_metrics"
    __table_args__ = (UniqueConstraint("publication_id", name="uq_publication_metric"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    publication_id: Mapped[str] = mapped_column(ForeignKey("publications.id", ondelete="CASCADE"))
    reactions: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)
    unique_repliers: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    conversions: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[float] = mapped_column(Float, default=0.0)


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    telegram_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(120))
    display_name: Mapped[str | None] = mapped_column(String(160))
    age_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Lead(TimestampMixin, Base):
    __tablename__ = "leads"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(32), default=LeadState.NEW)
    last_product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"))
    last_event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LeadEvent(TimestampMixin, Base):
    __tablename__ = "lead_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    lead_id: Mapped[str] = mapped_column(ForeignKey("leads.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"))
    payload: Mapped[dict] = mapped_column(SAJSON, default=dict)


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default=OrderStatus.CREATED, index=True)
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    checkout_url: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(SAJSON, default=dict)


class OrderItem(Base):
    __tablename__ = "order_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    price_plan_id: Mapped[str] = mapped_column(ForeignKey("price_plans.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    offer_id: Mapped[str | None] = mapped_column(ForeignKey("offers.id"))


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("provider", "provider_charge_id", name="uq_payment_provider_charge"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    provider_charge_id: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(32), default=PaymentStatus.CREATED, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    checkout_payload: Mapped[dict] = mapped_column(SAJSON, default=dict)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PaymentEvent(TimestampMixin, Base):
    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_payment_event_external"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    payment_id: Mapped[str | None] = mapped_column(ForeignKey("payments.id"), index=True)
    provider: Mapped[str] = mapped_column(String(64))
    provider_event_id: Mapped[str] = mapped_column(String(160))
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(SAJSON, default=dict)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)


class Entitlement(TimestampMixin, Base):
    __tablename__ = "entitlements"
    __table_args__ = (UniqueConstraint("source_order_item_id", name="uq_entitlement_order_item"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    community_version_id: Mapped[str] = mapped_column(
        ForeignKey("community_versions.id"), index=True
    )
    price_plan_id: Mapped[str] = mapped_column(ForeignKey("price_plans.id"))
    source_order_item_id: Mapped[str] = mapped_column(ForeignKey("order_items.id"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(24), default=EntitlementStatus.PENDING, index=True)


class MembershipGrant(TimestampMixin, Base):
    __tablename__ = "membership_grants"
    __table_args__ = (
        UniqueConstraint("entitlement_id", "destination_id", name="uq_membership_entitlement_dest"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    entitlement_id: Mapped[str] = mapped_column(ForeignKey("entitlements.id"), index=True)
    destination_id: Mapped[str] = mapped_column(ForeignKey("telegram_destinations.id"), index=True)
    telegram_user_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(24), default=MembershipStatus.PENDING)
    invite_link: Mapped[str | None] = mapped_column(Text)
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class Job(TimestampMixin, Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type: Mapped[str] = mapped_column(String(48), default=JobType.DISCOVER_SOURCE, index=True)
    payload: Mapped[dict] = mapped_column(SAJSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=JobStatus.QUEUED, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lock_owner: Mapped[str | None] = mapped_column(String(120))
    idempotency_key: Mapped[str | None] = mapped_column(String(180), unique=True)
    last_error: Mapped[str | None] = mapped_column(Text)


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    severity: Mapped[str] = mapped_column(String(16), default=Severity.INFO, index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(TimestampMixin, Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor_type: Mapped[str] = mapped_column(String(32), default="SYSTEM")
    actor_id: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(SAJSON, default=dict)


class ModerationRule(TimestampMixin, Base):
    __tablename__ = "moderation_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160))
    pattern: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(24), default=ModerationSeverity.REVIEW)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    whole_word: Mapped[bool] = mapped_column(Boolean, default=False)


class ModerationEvent(TimestampMixin, Base):
    __tablename__ = "moderation_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    telegram_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    destination_id: Mapped[str | None] = mapped_column(ForeignKey("telegram_destinations.id"))
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id"))
    message_id: Mapped[str | None] = mapped_column(String(64))
    matched_rule_id: Mapped[str | None] = mapped_column(ForeignKey("moderation_rules.id"))
    severity: Mapped[str] = mapped_column(String(24), default=ModerationSeverity.REVIEW)
    excerpt: Mapped[str | None] = mapped_column(Text)
    action_taken: Mapped[str | None] = mapped_column(String(64))


class IntegrationCredentialMetadata(TimestampMixin, Base):
    __tablename__ = "integration_credentials_metadata"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    integration: Mapped[str] = mapped_column(String(80), unique=True)
    configured: Mapped[bool] = mapped_column(Boolean, default=False)
    secret_reference: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)


class OfferCondition(TimestampMixin, Base):
    __tablename__ = "offer_conditions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    offer_id: Mapped[str] = mapped_column(ForeignKey("offers.id", ondelete="CASCADE"), index=True)
    condition_type: Mapped[str] = mapped_column(String(64))
    config: Mapped[dict] = mapped_column(SAJSON, default=dict)


class SourceProfile(TimestampMixin, Base):
    __tablename__ = "source_profiles"
    __table_args__ = (UniqueConstraint("source_id", "locator", name="uq_source_profile_locator"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    locator: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict] = mapped_column(SAJSON, default=dict)


class ContentTag(TimestampMixin, Base):
    __tablename__ = "content_tags"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)


class ContentPackTag(Base):
    __tablename__ = "content_pack_tags"
    pack_id: Mapped[str] = mapped_column(
        ForeignKey("content_packs.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[str] = mapped_column(
        ForeignKey("content_tags.id", ondelete="CASCADE"), primary_key=True
    )


class Derivative(TimestampMixin, Base):
    __tablename__ = "derivatives"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    source_asset_id: Mapped[str] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    derived_asset_id: Mapped[str] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"), unique=True
    )
    kind: Mapped[str] = mapped_column(String(48))
    params: Mapped[dict] = mapped_column(SAJSON, default=dict)


class VaultObject(TimestampMixin, Base):
    __tablename__ = "vault_objects"
    __table_args__ = (UniqueConstraint("asset_id", name="uq_vault_asset"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_id: Mapped[str] = mapped_column(
        ForeignKey("media_assets.id", ondelete="CASCADE"), index=True
    )
    destination_id: Mapped[str] = mapped_column(ForeignKey("telegram_destinations.id"), index=True)
    telegram_message_id: Mapped[str] = mapped_column(String(64))
    telegram_file_id: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(SAJSON, default=dict)


class CustomerTelegramIdentity(TimestampMixin, Base):
    __tablename__ = "customer_telegram_identities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    customer_id: Mapped[str] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    telegram_user_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(120))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class InviteRecord(TimestampMixin, Base):
    __tablename__ = "invite_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    membership_grant_id: Mapped[str] = mapped_column(
        ForeignKey("membership_grants.id", ondelete="CASCADE"), index=True
    )
    invite_link: Mapped[str | None] = mapped_column(Text)
    join_request: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
