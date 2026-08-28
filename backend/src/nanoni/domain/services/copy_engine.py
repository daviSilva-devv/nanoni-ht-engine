import random
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from nanoni.domain.models import CopySlot, CopyVariant


def choose_copy(
    db: Session, slot_key: str, product_id: str | None = None, rng: random.Random | None = None
) -> CopyVariant | None:
    now = datetime.now(UTC)
    stmt = (
        select(CopyVariant)
        .join(CopySlot, CopySlot.id == CopyVariant.slot_id)
        .where(
            CopySlot.key == slot_key,
            CopyVariant.active.is_(True),
            or_(CopyVariant.valid_from.is_(None), CopyVariant.valid_from <= now),
            or_(CopyVariant.valid_to.is_(None), CopyVariant.valid_to >= now),
        )
    )
    variants = list(db.scalars(stmt))
    if product_id:
        filtered = [v for v in variants if v.product_id in (None, product_id)]
        product_specific = [v for v in filtered if v.product_id == product_id]
        variants = product_specific or filtered
    else:
        variants = [v for v in variants if v.product_id is None]
    if not variants:
        return None
    chooser = rng or random.Random()
    return chooser.choices(variants, weights=[max(1, v.weight) for v in variants], k=1)[0]
