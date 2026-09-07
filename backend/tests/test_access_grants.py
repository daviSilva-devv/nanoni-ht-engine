from datetime import UTC, datetime, timedelta
from decimal import Decimal

from nanoni.domain.models import (
    Community,
    CommunityVersion,
    Customer,
    Entitlement,
    Niche,
    PricePlan,
    Product,
    TelegramDestination,
)
from nanoni.domain.services.access import (
    plan_membership_grants,
    process_join_request,
    remove_expired_memberships,
)


class StubMembershipPublisher:
    def __init__(self):
        self.approved = []
        self.declined = []
        self.removed = []

    def approve_join_request(self, *, chat_id, telegram_user_id):
        self.approved.append((chat_id, telegram_user_id))

    def decline_join_request(self, *, chat_id, telegram_user_id):
        self.declined.append((chat_id, telegram_user_id))

    def remove_member(self, *, chat_id, telegram_user_id):
        self.removed.append((chat_id, telegram_user_id))


def test_membership_grant_uses_replaceable_destination(db):
    niche = Niche(name="N", slug="n")
    db.add(niche)
    db.flush()
    community = Community(niche_id=niche.id, name="C", slug="c")
    db.add(community)
    db.flush()
    version = CommunityVersion(community_id=community.id, version=1, name="V1")
    db.add(version)
    db.flush()
    product = Product(community_version_id=version.id, name="P", slug="p")
    db.add(product)
    db.flush()
    plan = PricePlan(product_id=product.id, kind="LIFETIME", amount=Decimal("37.90"), lifetime=True)
    db.add(plan)
    db.flush()
    customer = Customer(telegram_user_id="42")
    db.add(customer)
    db.flush()
    entitlement = Entitlement(
        customer_id=customer.id,
        product_id=product.id,
        community_version_id=version.id,
        price_plan_id=plan.id,
        source_order_item_id="fake-item",
        status="ACTIVE",
    )
    # FK checks are not enabled by default in SQLite tests, so the domain unit can focus on grant planning.
    db.add(entitlement)
    db.flush()
    old = TelegramDestination(
        community_id=community.id,
        name="old",
        destination_type="VIP_FORUM",
        telegram_chat_id="old",
        status="OFFLINE",
    )
    new = TelegramDestination(
        community_id=community.id,
        name="new",
        destination_type="VIP_FORUM",
        telegram_chat_id="new",
        status="ACTIVE",
    )
    db.add_all([old, new])
    db.flush()
    old.replacement_destination_id = new.id
    db.add(old)
    db.flush()
    grants = plan_membership_grants(db, entitlement.id)
    assert any(g.destination_id == new.id for g in grants)


def test_join_request_approves_active_entitlement_and_allows_reentry(db):
    entitlement, destination = _access_fixture(db)
    grant = plan_membership_grants(db, entitlement.id)[0]
    publisher = StubMembershipPublisher()

    approved = process_join_request(
        db,
        chat_id=destination.telegram_chat_id,
        telegram_user_id=grant.telegram_user_id,
        publisher=publisher,
    )
    assert approved is grant
    assert grant.status == "ACTIVE"
    assert publisher.approved == [(destination.telegram_chat_id, grant.telegram_user_id)]

    replayed = process_join_request(
        db,
        chat_id=destination.telegram_chat_id,
        telegram_user_id=grant.telegram_user_id,
        publisher=publisher,
    )
    assert replayed is grant
    assert len(publisher.approved) == 1
    assert publisher.declined == []

    grant.status = "REMOVED"
    reentered = process_join_request(
        db,
        chat_id=destination.telegram_chat_id,
        telegram_user_id=grant.telegram_user_id,
        publisher=publisher,
    )
    assert reentered is grant
    assert grant.status == "ACTIVE"
    assert len(publisher.approved) == 2


def test_join_request_declines_unknown_or_expired_entitlement(db):
    entitlement, destination = _access_fixture(db)
    grant = plan_membership_grants(db, entitlement.id)[0]
    entitlement.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    publisher = StubMembershipPublisher()

    result = process_join_request(
        db,
        chat_id=destination.telegram_chat_id,
        telegram_user_id=grant.telegram_user_id,
        publisher=publisher,
    )
    assert result is None
    assert grant.status == "PENDING"
    assert publisher.declined == [(destination.telegram_chat_id, grant.telegram_user_id)]


def test_expired_membership_is_removed_once(db):
    entitlement, destination = _access_fixture(db)
    grant = plan_membership_grants(db, entitlement.id)[0]
    entitlement.status = "EXPIRED"
    grant.status = "ACTIVE"
    publisher = StubMembershipPublisher()

    first = remove_expired_memberships(db, publisher=publisher)
    second = remove_expired_memberships(db, publisher=publisher)
    assert first == [grant]
    assert second == []
    assert grant.status == "REMOVED"
    assert grant.removed_at is not None
    assert publisher.removed == [(destination.telegram_chat_id, grant.telegram_user_id)]


def _access_fixture(db):
    niche = Niche(name="Access", slug=f"access-{id(db)}")
    db.add(niche)
    db.flush()
    community = Community(niche_id=niche.id, name="Access", slug=f"access-{niche.id}")
    db.add(community)
    db.flush()
    version = CommunityVersion(community_id=community.id, version=1, name="V1")
    db.add(version)
    db.flush()
    product = Product(community_version_id=version.id, name="P", slug=f"p-{niche.id}")
    db.add(product)
    db.flush()
    plan = PricePlan(product_id=product.id, kind="MONTHLY", amount=Decimal("19.90"))
    db.add(plan)
    db.flush()
    customer = Customer(telegram_user_id=f"tg-{niche.id}")
    db.add(customer)
    db.flush()
    entitlement = Entitlement(
        customer_id=customer.id,
        product_id=product.id,
        community_version_id=version.id,
        price_plan_id=plan.id,
        source_order_item_id=f"item-{niche.id}",
        expires_at=datetime.now(UTC) + timedelta(days=30),
        status="ACTIVE",
    )
    destination = TelegramDestination(
        community_id=community.id,
        name="VIP",
        destination_type="VIP_FORUM",
        telegram_chat_id=f"chat-{niche.id}",
        status="ACTIVE",
    )
    db.add_all([entitlement, destination])
    db.flush()
    return entitlement, destination
