from decimal import Decimal

from nanoni.domain.models import (
    Community,
    CommunityVersion,
    Customer,
    Entitlement,
    Niche,
    Offer,
    OfferCondition,
    PricePlan,
    Product,
)
from nanoni.domain.services.offers import offer_is_eligible


def test_offer_conditions_are_generic_and_fail_closed(db):
    niche = Niche(name="N", slug="no")
    db.add(niche)
    db.flush()
    community = Community(niche_id=niche.id, name="C", slug="co")
    db.add(community)
    db.flush()
    version = CommunityVersion(community_id=community.id, version=1, name="V")
    db.add(version)
    db.flush()
    product = Product(community_version_id=version.id, name="P", slug="po")
    db.add(product)
    db.flush()
    plan = PricePlan(product_id=product.id, kind="LIFETIME", amount=Decimal("37.90"), lifetime=True)
    db.add(plan)
    db.flush()
    customer = Customer(telegram_user_id="9")
    db.add(customer)
    db.flush()
    entitlement = Entitlement(
        customer_id=customer.id,
        product_id=product.id,
        community_version_id=version.id,
        price_plan_id=plan.id,
        source_order_item_id="oi",
        status="ACTIVE",
    )
    db.add(entitlement)
    db.flush()
    offer = Offer(name="Upgrade", kind="UPGRADE")
    db.add(offer)
    db.flush()
    db.add(
        OfferCondition(
            offer_id=offer.id, condition_type="OWNS_PRODUCT", config={"product_id": product.id}
        )
    )
    db.flush()
    assert offer_is_eligible(db, offer, customer.id)
    db.add(OfferCondition(offer_id=offer.id, condition_type="UNKNOWN_RULE", config={}))
    db.flush()
    assert not offer_is_eligible(db, offer, customer.id)
