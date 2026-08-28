from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.domain.enums import (
    DestinationStatus,
    DestinationType,
    EntitlementStatus,
    MembershipStatus,
)
from nanoni.domain.models import (
    CommunityVersion,
    Customer,
    Entitlement,
    MembershipGrant,
    TelegramDestination,
)


def resolve_destination(
    db: Session, destination: TelegramDestination, max_hops: int = 5
) -> TelegramDestination:
    current = destination
    seen = {current.id}
    for _ in range(max_hops):
        if current.status == DestinationStatus.ACTIVE:
            return current
        if not current.replacement_destination_id:
            return current
        replacement = db.get(TelegramDestination, current.replacement_destination_id)
        if not replacement or replacement.id in seen:
            return current
        seen.add(replacement.id)
        current = replacement
    return current


def plan_membership_grants(db: Session, entitlement_id: str) -> list[MembershipGrant]:
    entitlement = db.get(Entitlement, entitlement_id)
    if not entitlement:
        raise ValueError("entitlement not found")
    if entitlement.status != EntitlementStatus.ACTIVE:
        raise ValueError("entitlement is not active")
    version = db.get(CommunityVersion, entitlement.community_version_id)
    customer = db.get(Customer, entitlement.customer_id)
    if not version or not customer:
        raise RuntimeError("entitlement references missing version/customer")
    destinations = list(
        db.scalars(
            select(TelegramDestination).where(
                TelegramDestination.community_id == version.community_id,
                TelegramDestination.destination_type == DestinationType.VIP_FORUM,
            )
        )
    )
    grants: list[MembershipGrant] = []
    for base in destinations:
        destination = resolve_destination(db, base)
        existing = db.scalar(
            select(MembershipGrant).where(
                MembershipGrant.entitlement_id == entitlement.id,
                MembershipGrant.destination_id == destination.id,
            )
        )
        if existing:
            grants.append(existing)
            continue
        grant = MembershipGrant(
            entitlement_id=entitlement.id,
            destination_id=destination.id,
            telegram_user_id=customer.telegram_user_id,
            status=MembershipStatus.PENDING,
        )
        db.add(grant)
        db.flush()
        grants.append(grant)
    return grants
