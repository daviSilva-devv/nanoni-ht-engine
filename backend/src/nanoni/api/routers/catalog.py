from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nanoni.core.db import get_db
from nanoni.core.security import require_admin
from nanoni.domain.models import (
    Community,
    CommunityVersion,
    CommunityVersionMicroNiche,
    CopySlot,
    CopyVariant,
    MicroNiche,
    Niche,
    PricePlan,
    Product,
    TelegramDestination,
    Topic,
)
from nanoni.domain.schemas import (
    CommunityCreate,
    CommunityRead,
    CommunityVersionCreate,
    CommunityVersionRead,
    CopyVariantCreate,
    CopyVariantRead,
    DestinationCreate,
    DestinationRead,
    MicroNicheCreate,
    MicroNicheRead,
    NicheCreate,
    NicheRead,
    PricePlanCreate,
    PricePlanRead,
    ProductCreate,
    ProductRead,
    TopicCreate,
    TopicRead,
)

router = APIRouter(prefix="/catalog", tags=["catalog"], dependencies=[Depends(require_admin)])


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="unique/foreign-key constraint failed") from exc


@router.get("/niches", response_model=list[NicheRead])
def list_niches(db: Session = Depends(get_db)):
    return list(db.scalars(select(Niche).order_by(Niche.sort_order, Niche.name)))


@router.post("/niches", response_model=NicheRead, status_code=status.HTTP_201_CREATED)
def create_niche(payload: NicheCreate, db: Session = Depends(get_db)):
    item = Niche(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return item


@router.get("/microniches", response_model=list[MicroNicheRead])
def list_microniches(niche_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(MicroNiche).order_by(MicroNiche.sort_order, MicroNiche.name)
    if niche_id:
        stmt = stmt.where(MicroNiche.niche_id == niche_id)
    return list(db.scalars(stmt))


@router.post("/microniches", response_model=MicroNicheRead, status_code=201)
def create_microniche(payload: MicroNicheCreate, db: Session = Depends(get_db)):
    if not db.get(Niche, payload.niche_id):
        raise HTTPException(404, "niche not found")
    item = MicroNiche(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return item


@router.get("/communities", response_model=list[CommunityRead])
def list_communities(db: Session = Depends(get_db)):
    return list(db.scalars(select(Community).order_by(Community.name)))


@router.post("/communities", response_model=CommunityRead, status_code=201)
def create_community(payload: CommunityCreate, db: Session = Depends(get_db)):
    if not db.get(Niche, payload.niche_id):
        raise HTTPException(404, "niche not found")
    item = Community(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return item


@router.get("/community-versions", response_model=list[CommunityVersionRead])
def list_community_versions(community_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(CommunityVersion).order_by(
        CommunityVersion.community_id, CommunityVersion.version.desc()
    )
    if community_id:
        stmt = stmt.where(CommunityVersion.community_id == community_id)
    return list(db.scalars(stmt))


@router.post("/community-versions", response_model=CommunityVersionRead, status_code=201)
def create_community_version(payload: CommunityVersionCreate, db: Session = Depends(get_db)):
    if not db.get(Community, payload.community_id):
        raise HTTPException(404, "community not found")
    missing = [mid for mid in payload.microniche_ids if not db.get(MicroNiche, mid)]
    if missing:
        raise HTTPException(422, detail={"missing_microniche_ids": missing})
    data = payload.model_dump(exclude={"microniche_ids"})
    item = CommunityVersion(**data)
    db.add(item)
    db.flush()
    for mid in dict.fromkeys(payload.microniche_ids):
        db.add(CommunityVersionMicroNiche(community_version_id=item.id, microniche_id=mid))
    _commit(db)
    db.refresh(item)
    return item


@router.post("/destinations", response_model=DestinationRead, status_code=201)
def create_destination(payload: DestinationCreate, db: Session = Depends(get_db)):
    if payload.community_id and not db.get(Community, payload.community_id):
        raise HTTPException(404, "community not found")
    item = TelegramDestination(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return item


@router.get("/destinations", response_model=list[DestinationRead])
def list_destinations(db: Session = Depends(get_db)):
    return list(db.scalars(select(TelegramDestination).order_by(TelegramDestination.name)))


@router.post("/topics", response_model=TopicRead, status_code=201)
def create_topic(payload: TopicCreate, db: Session = Depends(get_db)):
    if not db.get(TelegramDestination, payload.destination_id):
        raise HTTPException(404, "destination not found")
    if payload.microniche_id and not db.get(MicroNiche, payload.microniche_id):
        raise HTTPException(404, "microniche not found")
    item = Topic(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return item


@router.get("/topics", response_model=list[TopicRead])
def list_topics(destination_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Topic).order_by(Topic.name)
    if destination_id:
        stmt = stmt.where(Topic.destination_id == destination_id)
    return list(db.scalars(stmt))


@router.post("/products", response_model=ProductRead, status_code=201)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    if not db.get(CommunityVersion, payload.community_version_id):
        raise HTTPException(404, "community version not found")
    item = Product(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return item


@router.get("/products", response_model=list[ProductRead])
def list_products(db: Session = Depends(get_db)):
    return list(db.scalars(select(Product).order_by(Product.name)))


@router.post("/price-plans", response_model=PricePlanRead, status_code=201)
def create_price_plan(payload: PricePlanCreate, db: Session = Depends(get_db)):
    if not db.get(Product, payload.product_id):
        raise HTTPException(404, "product not found")
    if payload.lifetime and payload.duration_days is not None:
        raise HTTPException(422, "lifetime plan cannot have duration_days")
    if not payload.lifetime and not payload.duration_days:
        raise HTTPException(422, "non-lifetime plan needs duration_days")
    item = PricePlan(**payload.model_dump())
    db.add(item)
    _commit(db)
    db.refresh(item)
    return item


@router.get("/price-plans", response_model=list[PricePlanRead])
def list_price_plans(product_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(PricePlan).order_by(PricePlan.product_id, PricePlan.sort_order, PricePlan.amount)
    if product_id:
        stmt = stmt.where(PricePlan.product_id == product_id)
    return list(db.scalars(stmt))


@router.post("/copy-variants", response_model=CopyVariantRead, status_code=201)
def create_copy_variant(payload: CopyVariantCreate, db: Session = Depends(get_db)):
    slot = db.scalar(select(CopySlot).where(CopySlot.key == payload.slot_key))
    if not slot:
        slot = CopySlot(key=payload.slot_key, description=f"Copy slot {payload.slot_key}")
        db.add(slot)
        db.flush()
    item = CopyVariant(
        slot_id=slot.id,
        product_id=payload.product_id,
        text=payload.text,
        weight=payload.weight,
        active=payload.active,
    )
    db.add(item)
    _commit(db)
    db.refresh(item)
    return item


@router.get("/copy-variants", response_model=list[CopyVariantRead])
def list_copy_variants(slot_key: str | None = None, db: Session = Depends(get_db)):
    stmt = select(CopyVariant)
    if slot_key:
        stmt = stmt.join(CopySlot, CopySlot.id == CopyVariant.slot_id).where(
            CopySlot.key == slot_key
        )
    return list(db.scalars(stmt.order_by(CopyVariant.created_at.desc())))
