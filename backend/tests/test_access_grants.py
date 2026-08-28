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
from nanoni.domain.services.access import plan_membership_grants


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
