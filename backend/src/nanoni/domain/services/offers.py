from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.domain.enums import EntitlementStatus
from nanoni.domain.models import Entitlement, Offer, OfferCondition


def offer_is_time_active(offer: Offer, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    if not offer.active:
        return False
    if offer.starts_at and now < offer.starts_at:
        return False
    if offer.ends_at and now > offer.ends_at:
        return False
    return True


def _customer_owns_product(
    db: Session, customer_id: str, product_id: str, active_only: bool = False
) -> bool:
    stmt = select(Entitlement.id).where(
        Entitlement.customer_id == customer_id,
        Entitlement.product_id == product_id,
    )
    if active_only:
        stmt = stmt.where(Entitlement.status == EntitlementStatus.ACTIVE)
    return db.scalar(stmt.limit(1)) is not None


def offer_is_eligible(
    db: Session, offer: Offer, customer_id: str, now: datetime | None = None
) -> bool:
    if not offer_is_time_active(offer, now):
        return False
    conditions = list(db.scalars(select(OfferCondition).where(OfferCondition.offer_id == offer.id)))
    for condition in conditions:
        ctype = condition.condition_type.upper()
        cfg = condition.config or {}
        if ctype == "ALWAYS":
            continue
        if ctype == "OWNS_PRODUCT":
            if not _customer_owns_product(db, customer_id, str(cfg["product_id"])):
                return False
            continue
        if ctype == "OWNS_ACTIVE_PRODUCT":
            if not _customer_owns_product(
                db, customer_id, str(cfg["product_id"]), active_only=True
            ):
                return False
            continue
        if ctype == "NOT_OWNS_PRODUCT":
            if _customer_owns_product(db, customer_id, str(cfg["product_id"])):
                return False
            continue
        # Unknown conditions fail closed so a typo never creates an unintended discount.
        return False
    return True
