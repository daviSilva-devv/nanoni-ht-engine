from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class NicheCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = None
    active: bool = True
    sort_order: int = 0


class NicheRead(NicheCreate, ORMModel):
    id: str
    created_at: datetime
    updated_at: datetime


class MicroNicheCreate(BaseModel):
    niche_id: str
    name: str
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = None
    active: bool = True
    sort_order: int = 0


class MicroNicheRead(MicroNicheCreate, ORMModel):
    id: str


class CommunityCreate(BaseModel):
    niche_id: str
    name: str
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = None


class CommunityRead(CommunityCreate, ORMModel):
    id: str
    active: bool


class CommunityVersionCreate(BaseModel):
    community_id: str
    version: int = Field(ge=1)
    name: str
    promise_snapshot: dict[str, Any] = Field(default_factory=dict)
    microniche_ids: list[str] = Field(default_factory=list)


class CommunityVersionRead(ORMModel):
    id: str
    community_id: str
    version: int
    name: str
    promise_snapshot: dict[str, Any]
    active_for_sale: bool
    frozen_at: datetime | None


class DestinationCreate(BaseModel):
    community_id: str | None = None
    name: str
    destination_type: str
    telegram_chat_id: str
    username: str | None = None
    protected_content: bool = False


class DestinationRead(DestinationCreate, ORMModel):
    id: str
    status: str
    replacement_destination_id: str | None


class TopicCreate(BaseModel):
    destination_id: str
    microniche_id: str | None = None
    name: str
    role: str
    message_thread_id: int


class TopicRead(TopicCreate, ORMModel):
    id: str
    active: bool


class ProductCreate(BaseModel):
    community_version_id: str
    name: str
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = None


class ProductRead(ProductCreate, ORMModel):
    id: str
    active: bool


class PricePlanCreate(BaseModel):
    product_id: str
    kind: str
    amount: Decimal = Field(gt=0)
    currency: str = "BRL"
    duration_days: int | None = Field(default=None, gt=0)
    lifetime: bool = False
    active: bool = True
    featured: bool = False
    sort_order: int = 0


class PricePlanRead(PricePlanCreate, ORMModel):
    id: str


class CopyVariantCreate(BaseModel):
    slot_key: str
    text: str = Field(min_length=1)
    product_id: str | None = None
    weight: int = Field(default=10, ge=1, le=1000)
    active: bool = True


class CopyVariantRead(ORMModel):
    id: str
    slot_id: str
    product_id: str | None
    text: str
    weight: int
    active: bool


class SourceCreate(BaseModel):
    name: str
    adapter: str
    locator: str | None = None
    default_niche_id: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class SourceRead(SourceCreate, ORMModel):
    id: str
    active: bool
    approval_count: int
    presented_count: int
    published_count: int
    engagement_score: float


class ManifestAsset(BaseModel):
    source_locator: str
    media_type: str
    mime: str | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = None
    thumbnail_ref: str | None = None
    downloadable: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class MediaManifest(BaseModel):
    source: str
    source_collection_id: str | None = None
    source_item_id: str
    source_url: str | None = None
    title: str | None = None
    caption: str | None = None
    created_at: datetime | None = None
    media: list[ManifestAsset] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateImport(BaseModel):
    source_id: str
    manifest: MediaManifest


class CandidateRead(ORMModel):
    id: str
    source_id: str
    source_item_id: str
    source_collection_id: str | None
    source_url: str | None
    title: str | None
    caption: str | None
    status: str
    manifest: dict[str, Any]


class CandidateDecision(BaseModel):
    decision: str
    target: str | None = None
    microniche_ids: list[str] = Field(default_factory=list)
    selected_positions: list[int] | None = None
    notes: str | None = None


class OrderCreate(BaseModel):
    telegram_user_id: str
    username: str | None = None
    display_name: str | None = None
    price_plan_id: str
    idempotency_key: str = Field(min_length=8, max_length=120)


class OrderRead(ORMModel):
    id: str
    customer_id: str
    status: str
    currency: str
    total_amount: Decimal
    idempotency_key: str
    checkout_url: str | None


class PaymentRead(ORMModel):
    id: str
    order_id: str
    provider: str
    provider_charge_id: str
    status: str
    amount: Decimal
    currency: str
    checkout_payload: dict[str, Any]
    confirmed_at: datetime | None


class ConfirmMockPayment(BaseModel):
    provider_event_id: str


class EntitlementRead(ORMModel):
    id: str
    customer_id: str
    product_id: str
    community_version_id: str
    price_plan_id: str
    starts_at: datetime
    expires_at: datetime | None
    status: str


class DashboardSummary(BaseModel):
    niches: int
    communities: int
    active_products: int
    pending_content: int
    queued_publications: int
    open_alerts: int
    paid_orders: int
    active_entitlements: int
    revenue_confirmed: Decimal
