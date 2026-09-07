from decimal import Decimal

from sqlalchemy import select

from nanoni.domain.enums import LeadState
from nanoni.domain.models import (
    Community,
    CommunityVersion,
    CopySlot,
    CopyVariant,
    Customer,
    Lead,
    LeadEvent,
    Niche,
    PricePlan,
    Product,
    TelegramDestination,
)


def _sales_catalog(db, *, product_count: int = 1):
    niche = Niche(name="Sales", slug="sales")
    db.add(niche)
    db.flush()
    community = Community(niche_id=niche.id, name="Sales Community", slug="sales-community")
    db.add(community)
    db.flush()
    version = CommunityVersion(
        community_id=community.id,
        version=1,
        name="Sales V1",
        promise_snapshot={},
    )
    db.add(version)
    db.flush()
    products = []
    for index in range(product_count):
        product = Product(
            community_version_id=version.id,
            name=f"VIP {index + 1}",
            slug=f"vip-{index + 1}",
            description=f"Product {index + 1}",
        )
        db.add(product)
        db.flush()
        db.add(
            PricePlan(
                product_id=product.id,
                kind="LIFETIME",
                amount=Decimal("37.90") + index,
                lifetime=True,
                featured=index == 0,
                sort_order=index,
            )
        )
        products.append(product)

    hero = CopySlot(key="BOT_HERO")
    vip = CopySlot(key="VIP_CTA")
    free = CopySlot(key="FREE_CTA")
    db.add_all([hero, vip, free])
    db.flush()
    db.add_all(
        [
            CopyVariant(
                slot_id=hero.id,
                text="Hero configured",
                media_asset_id="hero-media-file-id",
            ),
            CopyVariant(slot_id=vip.id, text="Enter VIP"),
            CopyVariant(slot_id=free.id, text="See FREE"),
        ]
    )
    db.add(
        TelegramDestination(
            community_id=community.id,
            name="Free",
            destination_type="FREE_CHANNEL",
            telegram_chat_id="-100123456",
            username="nanoni_free",
        )
    )
    db.commit()
    return products


def _act(client, telegram_user_id: str, action: str, **extra):
    return client.post(
        "/api/v1/sales/action",
        json={"telegram_user_id": telegram_user_id, "action": action, **extra},
    )


def test_hot_lead_reaches_checkout_choice_in_minimal_steps(client, db):
    product = _sales_catalog(db)[0]

    start = client.post("/api/v1/sales/start", json={"telegram_user_id": "hot-lead"})
    assert start.status_code == 200
    assert start.json()["stage"] == "AGE_GATE"
    assert [button["action"] for button in start.json()["buttons"]] == ["CONFIRM_AGE"]

    hero = _act(client, "hot-lead", "CONFIRM_AGE")
    assert hero.status_code == 200
    assert hero.json()["stage"] == "HERO"
    assert hero.json()["copy"] == "Hero configured"
    assert hero.json()["media_asset_id"] == "hero-media-file-id"
    assert [button["label"] for button in hero.json()["buttons"]] == [
        "Enter VIP",
        "See FREE",
    ]

    plans = _act(client, "hot-lead", "VIP")
    assert plans.status_code == 200
    assert plans.json()["stage"] == "PLAN_SELECTION"
    assert plans.json()["product_id"] == product.id
    assert len(plans.json()["plans"]) == 1

    checkout = _act(
        client,
        "hot-lead",
        "PLAN",
        product_id=product.id,
        price_plan_id=plans.json()["plans"][0]["id"],
    )
    assert checkout.status_code == 200
    assert checkout.json()["stage"] == "CHECKOUT_CHOICE"
    assert checkout.json()["checkout"]["price_plan_id"] == plans.json()["plans"][0]["id"]
    assert checkout.json()["checkout"]["order_endpoint"] == "/api/v1/commerce/orders"

    customer = db.scalar(select(Customer).where(Customer.telegram_user_id == "hot-lead"))
    lead = db.scalar(select(Lead).where(Lead.customer_id == customer.id))
    assert customer.age_confirmed_at is not None
    assert lead.state == LeadState.PLAN_SELECTED
    assert [event.event_type for event in db.scalars(select(LeadEvent).order_by(LeadEvent.created_at))] == [
        "AGE_CONFIRMED",
        "INTENT_VIP",
        "PRODUCT_VIEWED",
        "PLAN_SELECTED",
    ]


def test_router_blocks_commercial_actions_until_age_is_confirmed(client, db):
    _sales_catalog(db)

    response = _act(client, "under-gate", "VIP")

    assert response.status_code == 409
    assert response.json()["detail"] == "age confirmation required"
    assert db.scalar(select(LeadEvent)) is None


def test_free_route_records_intent_and_preserves_returning_age_confirmation(client, db):
    _sales_catalog(db)
    _act(client, "free-lead", "CONFIRM_AGE")

    free = _act(client, "free-lead", "FREE")
    returning = client.post("/api/v1/sales/start", json={"telegram_user_id": "free-lead"})

    assert free.status_code == 200
    assert free.json()["stage"] == "FREE_ROUTE"
    assert free.json()["destination_url"] == "https://t.me/nanoni_free"
    assert returning.json()["stage"] == "HERO"
    lead = db.scalar(select(Lead).join(Customer).where(Customer.telegram_user_id == "free-lead"))
    assert lead.state == LeadState.INTENT_FREE


def test_multiple_products_require_explicit_product_selection(client, db):
    products = _sales_catalog(db, product_count=2)
    _act(client, "chooser", "CONFIRM_AGE")

    discovery = _act(client, "chooser", "VIP")
    assert discovery.json()["stage"] == "PRODUCT_SELECTION"
    assert [item["id"] for item in discovery.json()["products"]] == [
        product.id for product in products
    ]

    plans = _act(client, "chooser", "PRODUCT", product_id=products[1].id)
    assert plans.status_code == 200
    assert plans.json()["stage"] == "PLAN_SELECTION"
    assert plans.json()["product_id"] == products[1].id


def test_plan_must_belong_to_selected_active_product(client, db):
    products = _sales_catalog(db, product_count=2)
    _act(client, "invalid-plan", "CONFIRM_AGE")
    other_plan = db.scalar(select(PricePlan).where(PricePlan.product_id == products[1].id))

    response = _act(
        client,
        "invalid-plan",
        "PLAN",
        product_id=products[0].id,
        price_plan_id=other_plan.id,
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "price plan not found for product"


def test_age_confirmation_is_idempotent(client, db):
    _sales_catalog(db)
    _act(client, "repeat-age", "CONFIRM_AGE")
    customer = db.scalar(select(Customer).where(Customer.telegram_user_id == "repeat-age"))
    first_confirmed_at = customer.age_confirmed_at

    _act(client, "repeat-age", "CONFIRM_AGE")

    db.refresh(customer)
    assert customer.age_confirmed_at == first_confirmed_at
    events = list(db.scalars(select(LeadEvent).where(LeadEvent.event_type == "AGE_CONFIRMED")))
    assert len(events) == 1
    assert first_confirmed_at is not None
