from decimal import Decimal

from nanoni.domain.enums import EntitlementStatus, OrderStatus, PaymentStatus
from nanoni.domain.models import (
    Community,
    CommunityVersion,
    Niche,
    Order,
    PricePlan,
    Product,
)
from nanoni.domain.services.commerce import (
    create_order,
    fulfill_order_entitlements,
    process_payment_event,
)
from nanoni.integrations.payment.mock import MockPaymentProvider


def _catalog(db):
    niche = Niche(name="Test", slug="test")
    db.add(niche)
    db.flush()
    community = Community(niche_id=niche.id, name="Community", slug="community")
    db.add(community)
    db.flush()
    version = CommunityVersion(
        community_id=community.id, version=1, name="V1", promise_snapshot={"topics": 6}
    )
    db.add(version)
    db.flush()
    product = Product(community_version_id=version.id, name="VIP V1", slug="vip-v1")
    db.add(product)
    db.flush()
    plan = PricePlan(
        product_id=product.id,
        kind="LIFETIME",
        amount=Decimal("37.90"),
        lifetime=True,
        featured=True,
    )
    db.add(plan)
    db.flush()
    return version, product, plan


def test_payment_webhook_is_idempotent_and_access_is_exactly_once(db):
    version, product, plan = _catalog(db)
    provider = MockPaymentProvider()
    order, payment = create_order(
        db,
        provider,
        telegram_user_id="12345",
        username="buyer",
        display_name="Buyer",
        price_plan_id=plan.id,
        idempotency_key="checkout-12345-v1",
    )
    assert order.status == OrderStatus.PAYMENT_PENDING
    assert payment.status == PaymentStatus.PENDING

    provider.confirm(payment.provider_charge_id)
    event = provider.parse_webhook(
        {"event_id": "evt-1", "charge_id": payment.provider_charge_id, "status": "CONFIRMED"}
    )
    process_payment_event(db, provider.name, event)
    process_payment_event(db, provider.name, event)
    assert payment.status == PaymentStatus.CONFIRMED
    assert order.status == OrderStatus.PAID

    first = fulfill_order_entitlements(db, order.id)
    second = fulfill_order_entitlements(db, order.id)
    assert len(first) == len(second) == 1
    assert first[0].id == second[0].id
    assert first[0].community_version_id == version.id
    assert first[0].product_id == product.id
    assert first[0].status == EntitlementStatus.ACTIVE
    assert first[0].expires_at is None
    assert db.get(Order, order.id).status == OrderStatus.FULFILLED
