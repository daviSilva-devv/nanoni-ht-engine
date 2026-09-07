from __future__ import annotations

from datetime import UTC, datetime

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
from nanoni.integrations.telegram.publisher import TelegramPublisher


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


def process_join_request(
    db: Session,
    *,
    chat_id: str,
    telegram_user_id: str,
    publisher: TelegramPublisher,
    now: datetime | None = None,
) -> MembershipGrant | None:
    """Approve only an identified user with a currently active entitlement."""
    now = now or datetime.now(UTC)
    grant = db.scalar(
        select(MembershipGrant)
        .join(TelegramDestination, MembershipGrant.destination_id == TelegramDestination.id)
        .join(Entitlement, MembershipGrant.entitlement_id == Entitlement.id)
        .where(
            TelegramDestination.telegram_chat_id == chat_id,
            MembershipGrant.telegram_user_id == telegram_user_id,
            MembershipGrant.status.in_(
                (MembershipStatus.PENDING, MembershipStatus.ACTIVE, MembershipStatus.REMOVED)
            ),
            Entitlement.status == EntitlementStatus.ACTIVE,
            (Entitlement.expires_at.is_(None) | (Entitlement.expires_at > now)),
        )
        .order_by(Entitlement.expires_at.desc())
    )
    if not grant:
        publisher.decline_join_request(chat_id=chat_id, telegram_user_id=telegram_user_id)
        return None
    if grant.status == MembershipStatus.ACTIVE:
        return grant

    publisher.approve_join_request(chat_id=chat_id, telegram_user_id=telegram_user_id)
    grant.status = MembershipStatus.ACTIVE
    grant.joined_at = now
    grant.removed_at = None
    grant.last_error = None
    db.add(grant)
    db.flush()
    return grant


def has_expired_memberships(db: Session) -> bool:
    return (
        db.scalar(
            select(MembershipGrant.id)
            .join(Entitlement, MembershipGrant.entitlement_id == Entitlement.id)
            .where(
                MembershipGrant.status == MembershipStatus.ACTIVE,
                Entitlement.status.in_((EntitlementStatus.EXPIRED, EntitlementStatus.REVOKED)),
            )
            .limit(1)
        )
        is not None
    )


def remove_expired_memberships(
    db: Session, *, publisher: TelegramPublisher, now: datetime | None = None
) -> list[MembershipGrant]:
    """Remove active Telegram memberships whose commercial right has expired."""
    now = now or datetime.now(UTC)
    grants = list(
        db.scalars(
            select(MembershipGrant)
            .join(Entitlement, MembershipGrant.entitlement_id == Entitlement.id)
            .where(
                MembershipGrant.status == MembershipStatus.ACTIVE,
                Entitlement.status.in_((EntitlementStatus.EXPIRED, EntitlementStatus.REVOKED)),
            )
        )
    )
    for grant in grants:
        destination = db.get(TelegramDestination, grant.destination_id)
        if not destination:
            raise RuntimeError("membership grant references missing destination")
        publisher.remove_member(
            chat_id=destination.telegram_chat_id,
            telegram_user_id=grant.telegram_user_id,
        )
        grant.status = MembershipStatus.REMOVED
        grant.removed_at = now
        grant.last_error = None
        db.add(grant)
    db.flush()
    return grants
