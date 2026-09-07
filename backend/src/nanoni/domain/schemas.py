from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class AdminConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NicheUpdate(AdminConfigUpdate):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = None
    active: bool | None = None
    sort_order: int | None = None


class MicroNicheUpdate(NicheUpdate):
    niche_id: str | None = None


class CommunityUpdate(AdminConfigUpdate):
    niche_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = None
    active: bool | None = None


class CommunityVersionUpdate(AdminConfigUpdate):
    version: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    promise_snapshot: dict[str, Any] | None = None
    microniche_ids: list[str] | None = None
    active_for_sale: bool | None = None


class DestinationUpdate(AdminConfigUpdate):
    community_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    destination_type: str | None = None
    telegram_chat_id: str | None = None
    username: str | None = None
    status: str | None = None
    replacement_destination_id: str | None = None
    protected_content: bool | None = None


class TopicUpdate(AdminConfigUpdate):
    destination_id: str | None = None
    microniche_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    role: str | None = None
    message_thread_id: int | None = Field(default=None, ge=1)
    active: bool | None = None


class ProductUpdate(AdminConfigUpdate):
    community_version_id: str | None = None
    name: str | None = Field(default=None, min_length=1, max_length=160)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = None
    active: bool | None = None


class PricePlanUpdate(AdminConfigUpdate):
    product_id: str | None = None
    kind: str | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    duration_days: int | None = Field(default=None, gt=0)
    lifetime: bool | None = None
    active: bool | None = None
    featured: bool | None = None
    sort_order: int | None = None


class OfferProductInput(BaseModel):
    product_id: str
    role: str = Field(default="TARGET", min_length=1, max_length=24)


class OfferConditionInput(BaseModel):
    condition_type: str = Field(min_length=1, max_length=64)
    config: dict[str, Any] = Field(default_factory=dict)


class OfferCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    kind: str
    active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    products: list[OfferProductInput] = Field(default_factory=list)
    conditions: list[OfferConditionInput] = Field(default_factory=list)


class OfferUpdate(AdminConfigUpdate):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    kind: str | None = None
    active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    config: dict[str, Any] | None = None
    products: list[OfferProductInput] | None = None
    conditions: list[OfferConditionInput] | None = None


class CopySlotCreate(BaseModel):
    key: str = Field(pattern=r"^[A-Z0-9][A-Z0-9_]*$", max_length=64)
    description: str | None = None
    active: bool = True


class CopySlotUpdate(AdminConfigUpdate):
    key: str | None = Field(default=None, pattern=r"^[A-Z0-9][A-Z0-9_]*$", max_length=64)
    description: str | None = None
    active: bool | None = None


class CopyVariantAdminCreate(BaseModel):
    slot_id: str
    product_id: str | None = None
    text: str = Field(min_length=1)
    media_asset_id: str | None = None
    weight: int = Field(default=10, ge=1, le=1000)
    active: bool = True
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class CopyVariantUpdate(AdminConfigUpdate):
    slot_id: str | None = None
    product_id: str | None = None
    text: str | None = Field(default=None, min_length=1)
    media_asset_id: str | None = None
    weight: int | None = Field(default=None, ge=1, le=1000)
    active: bool | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None


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
    external_item_id: str | None = None
    media_type: str
    source_reference: str | None = None
    source_locator: str | None = None
    original_filename: str | None = None
    mime_type: str | None = None
    mime: str | None = None
    size: int | None = Field(default=None, ge=0)
    duration: float | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = Field(default=None, ge=0)
    thumbnail_ref: str | None = None
    downloadable: bool = True
    sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    local_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_aliases(self) -> "ManifestAsset":
        self.source_reference = self.source_reference or self.source_locator
        self.source_locator = self.source_locator or self.source_reference
        self.mime_type = self.mime_type or self.mime
        self.mime = self.mime or self.mime_type
        self.size = self.size if self.size is not None else self.file_size
        self.file_size = self.file_size if self.file_size is not None else self.size
        self.duration = self.duration if self.duration is not None else self.duration_seconds
        self.duration_seconds = (
            self.duration_seconds if self.duration_seconds is not None else self.duration
        )
        return self


class MediaManifest(BaseModel):
    source: str
    source_external_id: str | None = None
    source_collection_id: str | None = None
    source_item_id: str | None = None
    context: str | None = None
    source_url: str | None = None
    title: str | None = None
    caption: str | None = None
    discovered_at: datetime | None = None
    created_at: datetime | None = None
    media: list[ManifestAsset] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_source_fields(self) -> "MediaManifest":
        external_id = self.source_external_id or self.source_item_id
        if not external_id:
            raise ValueError("source_external_id or source_item_id is required")
        self.source_external_id = external_id
        self.source_item_id = external_id
        self.context = self.context or self.source_url
        self.source_url = self.source_url or self.context
        self.discovered_at = self.discovered_at or self.created_at
        self.created_at = self.created_at or self.discovered_at
        return self


class CandidateImport(BaseModel):
    source_id: str
    manifest: MediaManifest


class HelperManifestImport(BaseModel):
    source_id: str | None = None
    manifest: MediaManifest


class HelperFileImportRead(BaseModel):
    candidate_id: str
    pack_id: str
    asset_ids: list[str]


class EromeLocator(BaseModel):
    locator: str = Field(min_length=1, max_length=2048)


class CandidateRead(ORMModel):
    id: str
    source_id: str
    source_item_id: str
    source_collection_id: str | None
    source_url: str | None
    title: str | None
    caption: str | None
    status: str
    duplicate_classification: str = "NEW"
    manifest: dict[str, Any]


class CandidateImportRead(CandidateRead):
    pack_id: str
    import_classification: str


class PackItemSelection(BaseModel):
    selected_positions: list[int]


class PackItemOrder(BaseModel):
    item_ids: list[str]


class PackUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    caption: str | None = None
    tags: list[str] | None = None
    microniche_ids: list[str] | None = None
    metadata: dict[str, Any] | None = None


class MediaAssetRead(ORMModel):
    id: str
    media_type: str
    source_locator: str | None
    original_filename: str | None
    mime: str | None
    mime_type: str | None = Field(validation_alias="mime")
    duration_seconds: float | None
    duration: float | None = Field(validation_alias="duration_seconds")
    width: int | None
    height: int | None
    file_size: int | None
    size: int | None = Field(validation_alias="file_size")
    sha256: str | None
    telegram_file_id: str | None
    telegram_file_unique_id: str | None
    vault_chat_id: str | None
    vault_message_id: str | None
    status: str
    metadata_json: dict[str, Any]


class PackItemRead(BaseModel):
    id: str
    position: int
    selected: bool
    role: str
    source_id: str | None
    source_external_id: str | None
    source_reference: str | None
    original_filename: str | None
    metadata: dict[str, Any]
    asset: MediaAssetRead


class PackRead(BaseModel):
    id: str
    candidate_id: str | None
    title: str | None
    caption: str | None
    status: str
    approved: bool
    archived: bool
    metadata: dict[str, Any]
    tags: list[str]
    microniche_ids: list[str]
    items: list[PackItemRead]


class WatchFolderStatus(BaseModel):
    folders: dict[str, str]
    counts: dict[str, int]


class WatchFolderScanResult(BaseModel):
    candidate_ids: list[str]
    failed_files: list[str]
    recovered_files: list[str]


class AcquisitionJobRead(BaseModel):
    id: str
    status: str
    pack_item_id: str


class SelectedAcquisitionRead(BaseModel):
    pack_id: str
    jobs: list[AcquisitionJobRead]


class CandidateDecision(BaseModel):
    decision: str
    target: str | None = None
    microniche_ids: list[str] = Field(default_factory=list)
    selected_positions: list[int] | None = None
    notes: str | None = None


class CandidateReview(BaseModel):
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
