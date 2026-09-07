import hashlib
import hmac
import json
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select

from nanoni.api.routers import commerce as commerce_router
from nanoni.domain.enums import EntitlementStatus, OrderStatus, PaymentStatus
from nanoni.domain.models import (
    Community,
    CommunityVersion,
    Entitlement,
    MembershipGrant,
    Niche,
    PaymentEvent,
    PricePlan,
    Product,
    TelegramDestination,
)
from nanoni.domain.services.commerce import (
    create_order,
    fulfill_order_entitlements,
    process_payment_event,
)
from nanoni.integrations.payment.base import WebhookEvent
from nanoni.integrations.payment.bravopay import BravoPayProvider

NOW = 1_730_476_320
SECRET = "whsec_commerce"


def _catalog(db):
    niche = Niche(name="Bravo", slug="bravo")
    db.add(niche)
    db.flush()
    community = Community(niche_id=niche.id, name="Bravo", slug="bravo")
    db.add(community)
    db.flush()
    version = CommunityVersion(community_id=community.id, version=1, name="V1")
    db.add(version)
    db.flush()
    product = Product(community_version_id=version.id, name="VIP", slug="bravo-vip")
    db.add(product)
    db.flush()
    plan = PricePlan(
        product_id=product.id,
        kind="MONTHLY",
        amount=Decimal("19.90"),
        duration_days=30,
    )
    destination = TelegramDestination(
        community_id=community.id,
        name="VIP",
        destination_type="VIP_FORUM",
        telegram_chat_id="-100bravo",
        status="ACTIVE",
    )
    db.add_all([plan, destination])
    db.flush()
    return plan


def _provider():
    def handler(request):
        body = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "id": "tx_commerce",
                "status": "PENDING",
                "amount_cents": body["amount_cents"],
                "currency": "BRL",
                "pix": {"copy_paste": "PIX", "expires_at": "2026-09-07T19:00:00Z"},
            },
        )

    return BravoPayProvider(
        api_key="bp_live_test",
        webhook_secret=SECRET,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        clock=lambda: NOW,
    )


def _event(order, *, event_id="evt_paid", status="PAID", amount=Decimal("19.90")):
    return WebhookEvent(
        provider_event_id=event_id,
        provider_charge_id="tx_commerce",
        event_type=f"transaction.{status.lower()}",
        status=status,
        payload={"id": event_id},
        external_reference=order.id,
        amount=amount,
        currency="BRL",
    )


def _order(db):
    plan = _catalog(db)
    return create_order(
        db,
        _provider(),
        telegram_user_id="98765",
        username="buyer",
        display_name="Buyer",
        price_plan_id=plan.id,
        idempotency_key="bravopay-checkout",
    )


def test_paid_replay_fulfills_exactly_one_entitlement_and_grant(db):
    order, payment = _order(db)
    event = _event(order)

    process_payment_event(db, "bravopay", event)
    process_payment_event(db, "bravopay", event)
    fulfill_order_entitlements(db, order.id)
    fulfill_order_entitlements(db, order.id)

    assert payment.status == PaymentStatus.CONFIRMED
    assert order.status == OrderStatus.FULFILLED
    assert db.scalar(select(func.count()).select_from(PaymentEvent)) == 1
    assert db.scalar(select(func.count()).select_from(Entitlement)) == 1
    assert db.scalar(select(func.count()).select_from(MembershipGrant)) == 1

    recheck = _event(order, event_id="recheck-paid")
    process_payment_event(db, "bravopay", recheck)
    assert order.status == OrderStatus.FULFILLED
    assert db.scalar(select(func.count()).select_from(Entitlement)) == 1


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"amount": Decimal("20.00")}, "amount"),
        ({"external_reference": "missing-order"}, "external reference"),
        ({"currency": "USD"}, "currency"),
    ],
)
def test_reconciliation_rejects_mismatched_transaction(db, change, message):
    order, payment = _order(db)
    event = _event(order)
    event = WebhookEvent(**{**event.__dict__, **change})

    with pytest.raises(ValueError, match=message):
        process_payment_event(db, "bravopay", event)
    assert payment.status == PaymentStatus.PENDING


def test_reconciliation_rejects_unknown_provider_charge(db):
    order, _ = _order(db)
    event = WebhookEvent(**{**_event(order).__dict__, "provider_charge_id": "tx_unknown"})
    with pytest.raises(ValueError, match="unknown provider charge"):
        process_payment_event(db, "bravopay", event)


@pytest.mark.parametrize(
    ("status", "expected_payment", "expected_order"),
    [
        ("EXPIRED", PaymentStatus.EXPIRED, OrderStatus.EXPIRED),
        ("FAILED", PaymentStatus.FAILED, OrderStatus.PAYMENT_PENDING),
    ],
)
def test_terminal_unpaid_events_are_persisted(db, status, expected_payment, expected_order):
    order, payment = _order(db)
    process_payment_event(db, "bravopay", _event(order, event_id=f"evt_{status}", status=status))
    assert payment.status == expected_payment
    assert order.status == expected_order


def test_refund_revokes_fulfilled_entitlement(db):
    order, payment = _order(db)
    process_payment_event(db, "bravopay", _event(order))
    entitlement = fulfill_order_entitlements(db, order.id)[0]

    process_payment_event(
        db, "bravopay", _event(order, event_id="evt_refund", status="REFUNDED")
    )

    assert payment.status == PaymentStatus.REFUNDED
    assert order.status == OrderStatus.REFUNDED
    assert entitlement.status == EntitlementStatus.REVOKED


def test_chargeback_records_event_and_requires_review_without_fake_payment_status(db):
    order, payment = _order(db)
    process_payment_event(db, "bravopay", _event(order))
    fulfill_order_entitlements(db, order.id)

    process_payment_event(
        db, "bravopay", _event(order, event_id="evt_chargeback", status="CHARGEBACK")
    )

    assert payment.status == PaymentStatus.CONFIRMED
    assert order.status == OrderStatus.REVIEW_REQUIRED
    assert db.scalar(select(func.count()).select_from(PaymentEvent)) == 2


def test_dedicated_webhook_uses_raw_body_and_signature(client, db, monkeypatch):
    order, payment = _order(db)
    provider = _provider()
    monkeypatch.setattr(commerce_router, "get_payment_provider", lambda: provider)
    envelope = {
        "id": "evt_endpoint",
        "type": "transaction.paid",
        "created": NOW,
        "data": {
            "id": "tx_commerce",
            "status": "PAID",
            "amount_cents": 1990,
            "currency": "BRL",
            "external_reference": order.id,
        },
    }
    raw = json.dumps(envelope, separators=(",", ":")).encode()
    signature = hmac.new(SECRET.encode(), f"{NOW}.".encode() + raw, hashlib.sha256).hexdigest()

    response = client.post(
        "/api/v1/commerce/webhooks/bravopay",
        content=raw,
        headers={
            "Content-Type": "application/json",
            "BravoPay-Signature": f"t={NOW},v1={signature}",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == PaymentStatus.CONFIRMED
    assert payment.status == PaymentStatus.CONFIRMED
