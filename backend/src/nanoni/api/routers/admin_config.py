from collections.abc import Callable
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nanoni.core.db import get_db
from nanoni.core.security import require_admin
from nanoni.domain.enums import DestinationStatus, DestinationType, OfferKind, PlanKind, TopicRole
from nanoni.domain.models import (
    Community,
    CommunityVersion,
    CommunityVersionMicroNiche,
    CopySlot,
    CopyVariant,
    Entitlement,
    MicroNiche,
    Niche,
    Offer,
    OfferCondition,
    OfferProduct,
    PricePlan,
    Product,
    TelegramDestination,
    Topic,
)
from nanoni.domain.schemas import (
    CommunityCreate,
    CommunityUpdate,
    CommunityVersionCreate,
    CommunityVersionUpdate,
    CopySlotCreate,
    CopySlotUpdate,
    CopyVariantAdminCreate,
    CopyVariantUpdate,
    DestinationCreate,
    DestinationUpdate,
    MicroNicheCreate,
    MicroNicheUpdate,
    NicheCreate,
    NicheUpdate,
    OfferCreate,
    OfferUpdate,
    PricePlanCreate,
    PricePlanUpdate,
    ProductCreate,
    ProductUpdate,
    TopicCreate,
    TopicUpdate,
)

router = APIRouter(
    prefix="/admin-config", tags=["admin-config"], dependencies=[Depends(require_admin)]
)


def _get(db: Session, model: type, item_id: str):
    item = db.get(model, item_id)
    if not item:
        raise HTTPException(404, f"{model.__tablename__} item not found")
    return item


def _exists(db: Session, model: type, item_id: str | None, label: str) -> None:
    if item_id is not None and not db.get(model, item_id):
        raise HTTPException(422, f"{label} not found")


def _enum(value: str, enum_type: type, label: str) -> None:
    if value not in {item.value for item in enum_type}:
        choices = ", ".join(item.value for item in enum_type)
        raise HTTPException(422, f"invalid {label}; expected one of: {choices}")


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "operation conflicts with an existing value or relation") from exc


def _values(payload) -> dict[str, Any]:
    return payload.model_dump(exclude_unset=True)


def _apply(item, payload, *, exclude: set[str] | None = None) -> None:
    for key, value in _values(payload).items():
        if not exclude or key not in exclude:
            setattr(item, key, value)


def _row(item) -> dict[str, Any]:
    result = {column.name: getattr(item, column.name) for column in item.__table__.columns}
    return {
        key: str(value) if isinstance(value, Decimal) else value for key, value in result.items()
    }


def _count(db: Session, model: type, criterion) -> int:
    return int(db.scalar(select(func.count()).select_from(model).where(criterion)) or 0)


def _delete_item(
    db: Session,
    item,
    dependencies: list[tuple[str, type, Any]],
    cleanup: Callable[[], None] | None = None,
) -> Response:
    blockers = [label for label, model, criterion in dependencies if _count(db, model, criterion)]
    if blockers:
        raise HTTPException(409, f"cannot remove: dependent {', '.join(blockers)} exist")
    if cleanup:
        cleanup()
    db.delete(item)
    _commit(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _validate_plan(data: dict[str, Any], current: PricePlan | None = None) -> None:
    kind = data.get("kind", current.kind if current else None)
    lifetime = data.get("lifetime", current.lifetime if current else False)
    duration = data.get("duration_days", current.duration_days if current else None)
    if kind:
        _enum(kind, PlanKind, "plan kind")
    if lifetime and duration is not None:
        raise HTTPException(422, "lifetime plan cannot have duration_days")
    if not lifetime and not duration:
        raise HTTPException(422, "non-lifetime plan needs duration_days")
    if kind == PlanKind.LIFETIME and not lifetime:
        raise HTTPException(422, "LIFETIME kind requires lifetime=true")


def _version_row(db: Session, item: CommunityVersion) -> dict[str, Any]:
    result = _row(item)
    result["microniche_ids"] = list(
        db.scalars(
            select(CommunityVersionMicroNiche.microniche_id).where(
                CommunityVersionMicroNiche.community_version_id == item.id
            )
        )
    )
    return result


def _replace_version_micros(db: Session, version_id: str, ids: list[str]) -> None:
    for item_id in dict.fromkeys(ids):
        _exists(db, MicroNiche, item_id, "microniche")
    db.execute(
        delete(CommunityVersionMicroNiche).where(
            CommunityVersionMicroNiche.community_version_id == version_id
        )
    )
    db.add_all(
        [
            CommunityVersionMicroNiche(community_version_id=version_id, microniche_id=item_id)
            for item_id in dict.fromkeys(ids)
        ]
    )


def _offer_row(db: Session, item: Offer) -> dict[str, Any]:
    result = _row(item)
    result["products"] = [
        _row(row)
        for row in db.scalars(select(OfferProduct).where(OfferProduct.offer_id == item.id))
    ]
    result["conditions"] = [
        _row(row)
        for row in db.scalars(select(OfferCondition).where(OfferCondition.offer_id == item.id))
    ]
    return result


def _replace_offer_relations(db: Session, offer_id: str, products, conditions) -> None:
    if products is not None:
        db.execute(delete(OfferProduct).where(OfferProduct.offer_id == offer_id))
        for link in products:
            product_id = link["product_id"] if isinstance(link, dict) else link.product_id
            role = link.get("role", "TARGET") if isinstance(link, dict) else link.role
            _exists(db, Product, product_id, "product")
            db.add(OfferProduct(offer_id=offer_id, product_id=product_id, role=role))
    if conditions is not None:
        db.execute(delete(OfferCondition).where(OfferCondition.offer_id == offer_id))
        db.add_all(
            [
                OfferCondition(
                    offer_id=offer_id,
                    condition_type=row["condition_type"]
                    if isinstance(row, dict)
                    else row.condition_type,
                    config=row.get("config", {}) if isinstance(row, dict) else row.config,
                )
                for row in conditions
            ]
        )


# Niche
@router.get("/niches")
def niches_list(db: Session = Depends(get_db)):
    return [_row(row) for row in db.scalars(select(Niche).order_by(Niche.sort_order, Niche.name))]


@router.post("/niches", status_code=201)
def niches_create(payload: NicheCreate, db: Session = Depends(get_db)):
    item = Niche(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.get("/niches/{item_id}")
def niches_get(item_id: str, db: Session = Depends(get_db)):
    return _row(_get(db, Niche, item_id))


@router.patch("/niches/{item_id}")
def niches_update(item_id: str, payload: NicheUpdate, db: Session = Depends(get_db)):
    item = _get(db, Niche, item_id)
    _apply(item, payload)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.delete("/niches/{item_id}", status_code=204)
def niches_delete(item_id: str, db: Session = Depends(get_db)):
    item = _get(db, Niche, item_id)
    return _delete_item(
        db,
        item,
        [
            ("microniches", MicroNiche, MicroNiche.niche_id == item.id),
            ("communities", Community, Community.niche_id == item.id),
        ],
    )


# MicroNiche
@router.get("/microniches")
def microniches_list(niche_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(MicroNiche).order_by(MicroNiche.sort_order, MicroNiche.name)
    if niche_id:
        stmt = stmt.where(MicroNiche.niche_id == niche_id)
    return [_row(row) for row in db.scalars(stmt)]


@router.post("/microniches", status_code=201)
def microniches_create(payload: MicroNicheCreate, db: Session = Depends(get_db)):
    _exists(db, Niche, payload.niche_id, "niche")
    item = MicroNiche(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.get("/microniches/{item_id}")
def microniches_get(item_id: str, db: Session = Depends(get_db)):
    return _row(_get(db, MicroNiche, item_id))


@router.patch("/microniches/{item_id}")
def microniches_update(item_id: str, payload: MicroNicheUpdate, db: Session = Depends(get_db)):
    item = _get(db, MicroNiche, item_id)
    data = _values(payload)
    if "niche_id" in data:
        _exists(db, Niche, data["niche_id"], "niche")
    _apply(item, payload)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.delete("/microniches/{item_id}", status_code=204)
def microniches_delete(item_id: str, db: Session = Depends(get_db)):
    item = _get(db, MicroNiche, item_id)
    return _delete_item(
        db,
        item,
        [
            (
                "community versions",
                CommunityVersionMicroNiche,
                CommunityVersionMicroNiche.microniche_id == item.id,
            ),
            ("topics", Topic, Topic.microniche_id == item.id),
        ],
    )


# Community
@router.get("/communities")
def communities_list(db: Session = Depends(get_db)):
    return [_row(row) for row in db.scalars(select(Community).order_by(Community.name))]


@router.post("/communities", status_code=201)
def communities_create(payload: CommunityCreate, db: Session = Depends(get_db)):
    _exists(db, Niche, payload.niche_id, "niche")
    item = Community(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.get("/communities/{item_id}")
def communities_get(item_id: str, db: Session = Depends(get_db)):
    return _row(_get(db, Community, item_id))


@router.patch("/communities/{item_id}")
def communities_update(item_id: str, payload: CommunityUpdate, db: Session = Depends(get_db)):
    item = _get(db, Community, item_id)
    data = _values(payload)
    if "niche_id" in data:
        _exists(db, Niche, data["niche_id"], "niche")
    _apply(item, payload)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.delete("/communities/{item_id}", status_code=204)
def communities_delete(item_id: str, db: Session = Depends(get_db)):
    item = _get(db, Community, item_id)
    return _delete_item(
        db,
        item,
        [
            ("versions", CommunityVersion, CommunityVersion.community_id == item.id),
            ("destinations", TelegramDestination, TelegramDestination.community_id == item.id),
        ],
    )


# CommunityVersion
@router.get("/community-versions")
def versions_list(community_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(CommunityVersion).order_by(
        CommunityVersion.community_id, CommunityVersion.version
    )
    if community_id:
        stmt = stmt.where(CommunityVersion.community_id == community_id)
    return [_version_row(db, row) for row in db.scalars(stmt)]


@router.post("/community-versions", status_code=201)
def versions_create(payload: CommunityVersionCreate, db: Session = Depends(get_db)):
    _exists(db, Community, payload.community_id, "community")
    data = payload.model_dump(exclude={"microniche_ids"})
    item = CommunityVersion(**data)
    db.add(item)
    db.flush()
    _replace_version_micros(db, item.id, payload.microniche_ids)
    _commit(db)
    db.refresh(item)
    return _version_row(db, item)


@router.get("/community-versions/{item_id}")
def versions_get(item_id: str, db: Session = Depends(get_db)):
    return _version_row(db, _get(db, CommunityVersion, item_id))


@router.patch("/community-versions/{item_id}")
def versions_update(item_id: str, payload: CommunityVersionUpdate, db: Session = Depends(get_db)):
    item = _get(db, CommunityVersion, item_id)
    data = _values(payload)
    immutable_changes = {"version", "promise_snapshot", "microniche_ids"}.intersection(data)
    sold = db.scalar(
        select(func.count())
        .select_from(Entitlement)
        .join(Product, Product.id == Entitlement.product_id)
        .where(Product.community_version_id == item.id)
    )
    if immutable_changes and sold:
        raise HTTPException(409, "sold community version promises are immutable")
    if "microniche_ids" in data:
        _replace_version_micros(db, item.id, data.pop("microniche_ids"))
    for key, value in data.items():
        setattr(item, key, value)
    _commit(db)
    db.refresh(item)
    return _version_row(db, item)


@router.delete("/community-versions/{item_id}", status_code=204)
def versions_delete(item_id: str, db: Session = Depends(get_db)):
    item = _get(db, CommunityVersion, item_id)
    return _delete_item(
        db,
        item,
        [("products", Product, Product.community_version_id == item.id)],
        cleanup=lambda: db.execute(
            delete(CommunityVersionMicroNiche).where(
                CommunityVersionMicroNiche.community_version_id == item.id
            )
        ),
    )


# Destination
@router.get("/destinations")
def destinations_list(community_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(TelegramDestination).order_by(TelegramDestination.name)
    if community_id:
        stmt = stmt.where(TelegramDestination.community_id == community_id)
    return [_row(row) for row in db.scalars(stmt)]


def _validate_destination(db: Session, data: dict[str, Any], current_id: str | None = None) -> None:
    if data.get("community_id"):
        _exists(db, Community, data["community_id"], "community")
    if data.get("destination_type"):
        _enum(data["destination_type"], DestinationType, "destination type")
    if data.get("status"):
        _enum(data["status"], DestinationStatus, "destination status")
    replacement = data.get("replacement_destination_id")
    if replacement:
        _exists(db, TelegramDestination, replacement, "replacement destination")
        if replacement == current_id:
            raise HTTPException(422, "destination cannot replace itself")


@router.post("/destinations", status_code=201)
def destinations_create(payload: DestinationCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    _validate_destination(db, data)
    item = TelegramDestination(**data)
    db.add(item)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.get("/destinations/{item_id}")
def destinations_get(item_id: str, db: Session = Depends(get_db)):
    return _row(_get(db, TelegramDestination, item_id))


@router.patch("/destinations/{item_id}")
def destinations_update(item_id: str, payload: DestinationUpdate, db: Session = Depends(get_db)):
    item = _get(db, TelegramDestination, item_id)
    data = _values(payload)
    _validate_destination(db, data, item.id)
    _apply(item, payload)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.delete("/destinations/{item_id}", status_code=204)
def destinations_delete(item_id: str, db: Session = Depends(get_db)):
    item = _get(db, TelegramDestination, item_id)
    return _delete_item(db, item, [("topics", Topic, Topic.destination_id == item.id)])


# Topic
@router.get("/topics")
def topics_list(destination_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Topic).order_by(Topic.name)
    if destination_id:
        stmt = stmt.where(Topic.destination_id == destination_id)
    return [_row(row) for row in db.scalars(stmt)]


def _validate_topic(db: Session, data: dict[str, Any]) -> None:
    if data.get("destination_id"):
        _exists(db, TelegramDestination, data["destination_id"], "destination")
    if data.get("microniche_id"):
        _exists(db, MicroNiche, data["microniche_id"], "microniche")
    if data.get("role"):
        _enum(data["role"], TopicRole, "topic role")
    if data.get("role") in {TopicRole.GENERAL, TopicRole.REQUESTS} and data.get("microniche_id"):
        raise HTTPException(422, "GENERAL and REQUESTS topics cannot target a microniche")


@router.post("/topics", status_code=201)
def topics_create(payload: TopicCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    _validate_topic(db, data)
    item = Topic(**data)
    db.add(item)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.get("/topics/{item_id}")
def topics_get(item_id: str, db: Session = Depends(get_db)):
    return _row(_get(db, Topic, item_id))


@router.patch("/topics/{item_id}")
def topics_update(item_id: str, payload: TopicUpdate, db: Session = Depends(get_db)):
    item = _get(db, Topic, item_id)
    data = _values(payload)
    effective = {"role": item.role, "microniche_id": item.microniche_id, **data}
    _validate_topic(db, effective)
    _apply(item, payload)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.delete("/topics/{item_id}", status_code=204)
def topics_delete(item_id: str, db: Session = Depends(get_db)):
    return _delete_item(db, _get(db, Topic, item_id), [])


# Product
@router.get("/products")
def products_list(db: Session = Depends(get_db)):
    return [_row(row) for row in db.scalars(select(Product).order_by(Product.name))]


@router.post("/products", status_code=201)
def products_create(payload: ProductCreate, db: Session = Depends(get_db)):
    _exists(db, CommunityVersion, payload.community_version_id, "community version")
    item = Product(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.get("/products/{item_id}")
def products_get(item_id: str, db: Session = Depends(get_db)):
    return _row(_get(db, Product, item_id))


@router.patch("/products/{item_id}")
def products_update(item_id: str, payload: ProductUpdate, db: Session = Depends(get_db)):
    item = _get(db, Product, item_id)
    data = _values(payload)
    if "community_version_id" in data:
        _exists(db, CommunityVersion, data["community_version_id"], "community version")
    _apply(item, payload)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.delete("/products/{item_id}", status_code=204)
def products_delete(item_id: str, db: Session = Depends(get_db)):
    item = _get(db, Product, item_id)
    return _delete_item(
        db,
        item,
        [
            ("price plans", PricePlan, PricePlan.product_id == item.id),
            ("offers", OfferProduct, OfferProduct.product_id == item.id),
            ("copy variants", CopyVariant, CopyVariant.product_id == item.id),
        ],
    )


# PricePlan
@router.get("/price-plans")
def plans_list(product_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(PricePlan).order_by(PricePlan.sort_order, PricePlan.amount)
    if product_id:
        stmt = stmt.where(PricePlan.product_id == product_id)
    return [_row(row) for row in db.scalars(stmt)]


@router.post("/price-plans", status_code=201)
def plans_create(payload: PricePlanCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    _exists(db, Product, payload.product_id, "product")
    _validate_plan(data)
    item = PricePlan(**data)
    db.add(item)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.get("/price-plans/{item_id}")
def plans_get(item_id: str, db: Session = Depends(get_db)):
    return _row(_get(db, PricePlan, item_id))


@router.patch("/price-plans/{item_id}")
def plans_update(item_id: str, payload: PricePlanUpdate, db: Session = Depends(get_db)):
    item = _get(db, PricePlan, item_id)
    data = _values(payload)
    if "product_id" in data:
        _exists(db, Product, data["product_id"], "product")
    _validate_plan(data, item)
    _apply(item, payload)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.delete("/price-plans/{item_id}", status_code=204)
def plans_delete(item_id: str, db: Session = Depends(get_db)):
    return _delete_item(db, _get(db, PricePlan, item_id), [])


# Offer
@router.get("/offers")
def offers_list(db: Session = Depends(get_db)):
    return [_offer_row(db, row) for row in db.scalars(select(Offer).order_by(Offer.name))]


@router.post("/offers", status_code=201)
def offers_create(payload: OfferCreate, db: Session = Depends(get_db)):
    _enum(payload.kind, OfferKind, "offer kind")
    if payload.starts_at and payload.ends_at and payload.ends_at <= payload.starts_at:
        raise HTTPException(422, "offer ends_at must be after starts_at")
    item = Offer(**payload.model_dump(exclude={"products", "conditions"}))
    db.add(item)
    db.flush()
    _replace_offer_relations(db, item.id, payload.products, payload.conditions)
    _commit(db)
    db.refresh(item)
    return _offer_row(db, item)


@router.get("/offers/{item_id}")
def offers_get(item_id: str, db: Session = Depends(get_db)):
    return _offer_row(db, _get(db, Offer, item_id))


@router.patch("/offers/{item_id}")
def offers_update(item_id: str, payload: OfferUpdate, db: Session = Depends(get_db)):
    item = _get(db, Offer, item_id)
    data = _values(payload)
    products = data.pop("products", None)
    conditions = data.pop("conditions", None)
    if data.get("kind"):
        _enum(data["kind"], OfferKind, "offer kind")
    starts_at = data.get("starts_at", item.starts_at)
    ends_at = data.get("ends_at", item.ends_at)
    if starts_at and ends_at and ends_at <= starts_at:
        raise HTTPException(422, "offer ends_at must be after starts_at")
    for key, value in data.items():
        setattr(item, key, value)
    _replace_offer_relations(db, item.id, products, conditions)
    _commit(db)
    db.refresh(item)
    return _offer_row(db, item)


@router.delete("/offers/{item_id}", status_code=204)
def offers_delete(item_id: str, db: Session = Depends(get_db)):
    item = _get(db, Offer, item_id)
    return _delete_item(
        db,
        item,
        [],
        cleanup=lambda: (
            db.execute(delete(OfferProduct).where(OfferProduct.offer_id == item.id)),
            db.execute(delete(OfferCondition).where(OfferCondition.offer_id == item.id)),
        ),
    )


# CopySlot
@router.get("/copy-slots")
def slots_list(db: Session = Depends(get_db)):
    return [_row(row) for row in db.scalars(select(CopySlot).order_by(CopySlot.key))]


@router.post("/copy-slots", status_code=201)
def slots_create(payload: CopySlotCreate, db: Session = Depends(get_db)):
    item = CopySlot(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.get("/copy-slots/{item_id}")
def slots_get(item_id: str, db: Session = Depends(get_db)):
    return _row(_get(db, CopySlot, item_id))


@router.patch("/copy-slots/{item_id}")
def slots_update(item_id: str, payload: CopySlotUpdate, db: Session = Depends(get_db)):
    item = _get(db, CopySlot, item_id)
    _apply(item, payload)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.delete("/copy-slots/{item_id}", status_code=204)
def slots_delete(item_id: str, db: Session = Depends(get_db)):
    item = _get(db, CopySlot, item_id)
    return _delete_item(db, item, [("variants", CopyVariant, CopyVariant.slot_id == item.id)])


# CopyVariant
@router.get("/copy-variants")
def variants_list(slot_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(CopyVariant).order_by(CopyVariant.created_at.desc())
    if slot_id:
        stmt = stmt.where(CopyVariant.slot_id == slot_id)
    return [_row(row) for row in db.scalars(stmt)]


def _validate_variant(db: Session, data: dict[str, Any]) -> None:
    if data.get("slot_id"):
        _exists(db, CopySlot, data["slot_id"], "copy slot")
    if data.get("product_id"):
        _exists(db, Product, data["product_id"], "product")
    start = data.get("valid_from")
    end = data.get("valid_to")
    if start and end and end <= start:
        raise HTTPException(422, "valid_to must be after valid_from")


@router.post("/copy-variants", status_code=201)
def variants_create(payload: CopyVariantAdminCreate, db: Session = Depends(get_db)):
    data = payload.model_dump()
    _validate_variant(db, data)
    item = CopyVariant(**data)
    db.add(item)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.get("/copy-variants/{item_id}")
def variants_get(item_id: str, db: Session = Depends(get_db)):
    return _row(_get(db, CopyVariant, item_id))


@router.patch("/copy-variants/{item_id}")
def variants_update(item_id: str, payload: CopyVariantUpdate, db: Session = Depends(get_db)):
    item = _get(db, CopyVariant, item_id)
    data = _values(payload)
    effective = {"valid_from": item.valid_from, "valid_to": item.valid_to, **data}
    _validate_variant(db, effective)
    _apply(item, payload)
    _commit(db)
    db.refresh(item)
    return _row(item)


@router.delete("/copy-variants/{item_id}", status_code=204)
def variants_delete(item_id: str, db: Session = Depends(get_db)):
    return _delete_item(db, _get(db, CopyVariant, item_id), [])
