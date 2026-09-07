import hashlib
import hmac
import json
from decimal import Decimal

import httpx
import pytest

from nanoni.integrations.payment.bravopay import (
    BravoPayError,
    BravoPayProvider,
    BravoPayWebhookError,
)

NOW = 1_730_476_320
SECRET = "whsec_test"


def _transaction(**overrides):
    payload = {
        "id": "tx_123",
        "status": "PENDING",
        "method": "PIX",
        "amount_cents": 1990,
        "currency": "BRL",
        "external_reference": "order-123",
        "metadata": {"order_id": "order-123"},
        "pix": {
            "copy_paste": "000201BRPIX",
            "expires_at": "2026-06-01T16:30:00.000Z",
        },
    }
    payload.update(overrides)
    return payload


def _provider(handler, **kwargs):
    return BravoPayProvider(
        api_key="bp_live_test",
        webhook_secret=SECRET,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        sleeper=kwargs.pop("sleeper", lambda _: None),
        clock=lambda: NOW,
        **kwargs,
    )


def _signed_event(event_type="transaction.paid", status="PAID", **data_overrides):
    data = _transaction(status=status, **data_overrides)
    envelope = {"id": "evt_123", "type": event_type, "created": NOW, "data": data}
    raw = json.dumps(envelope, separators=(",", ":")).encode()
    signature = hmac.new(SECRET.encode(), f"{NOW}.".encode() + raw, hashlib.sha256).hexdigest()
    return raw, {"BravoPay-Signature": f"t={NOW},v1={signature}"}


def test_create_pix_charge_uses_real_contract_and_idempotency_header():
    captured = {}

    def handler(request):
        captured["request"] = request
        return httpx.Response(200, json=_transaction(external_reference=None))

    charge = _provider(handler).create_charge(
        order_id="order-123",
        amount=Decimal("19.90"),
        currency="BRL",
        idempotency_key="checkout-123",
    )

    request = captured["request"]
    body = json.loads(request.content)
    assert request.url.path == "/api/v1/transactions"
    assert request.headers["Authorization"] == "Bearer bp_live_test"
    assert request.headers["Idempotency-Key"] == "checkout-123"
    assert body == {
        "amount_cents": 1990,
        "method": "pix",
        "external_reference": "order-123",
        "metadata": {"order_id": "order-123"},
        "expires_in": 3600,
    }
    assert charge.provider_charge_id == "tx_123"
    assert charge.payload["pix"]["copy_paste"] == "000201BRPIX"
    assert charge.payload["pix"]["expires_at"] == "2026-06-01T16:30:00.000Z"
    assert charge.payload["external_reference"] == "order-123"
    assert charge.checkout_url == "http://localhost:3000/checkout/order-123"


def test_get_charge_uses_transaction_detail_endpoint():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/api/v1/transactions/tx_123"
        return httpx.Response(200, json=_transaction(status="PAID"))

    charge = _provider(handler).get_charge("tx_123")
    assert charge.status == "PAID"
    assert charge.amount == Decimal("19.90")


@pytest.mark.parametrize(
    ("event_type", "status"),
    [
        ("transaction.paid", "PAID"),
        ("transaction.expired", "EXPIRED"),
        ("transaction.failed", "FAILED"),
        ("transaction.refunded", "REFUNDED"),
    ],
)
def test_parse_signed_transaction_events(event_type, status):
    raw, headers = _signed_event(event_type, status)
    event = _provider(lambda _: None).parse_webhook(raw, headers)
    assert event.provider_event_id == "evt_123"
    assert event.provider_charge_id == "tx_123"
    assert event.event_type == event_type
    assert event.status == status
    assert event.external_reference == "order-123"
    assert event.amount == Decimal("19.90")
    assert event.currency == "BRL"


def test_webhook_accepts_documented_signature_alias():
    raw, headers = _signed_event()
    alias_headers = {"X-Bravopay-Signature": headers["BravoPay-Signature"]}
    assert _provider(lambda _: None).parse_webhook(raw, alias_headers).status == "PAID"


@pytest.mark.parametrize(
    ("raw_transform", "timestamp"),
    [(lambda raw: raw + b" ", NOW), (lambda raw: raw, NOW - 301)],
)
def test_webhook_rejects_invalid_signature_or_stale_timestamp(raw_transform, timestamp):
    raw, _ = _signed_event()
    transformed = raw_transform(raw)
    signature = hmac.new(
        SECRET.encode(), f"{timestamp}.".encode() + raw, hashlib.sha256
    ).hexdigest()
    with pytest.raises(BravoPayWebhookError):
        _provider(lambda _: None).parse_webhook(
            transformed, {"BravoPay-Signature": f"t={timestamp},v1={signature}"}
        )


def test_webhook_rejects_event_status_mismatch():
    raw, headers = _signed_event("transaction.paid", "FAILED")
    with pytest.raises(BravoPayWebhookError, match="mismatch"):
        _provider(lambda _: None).parse_webhook(raw, headers)


def test_provider_retries_429_and_5xx_with_retry_after():
    statuses = iter([429, 503, 200])
    delays = []

    def handler(_request):
        status = next(statuses)
        return httpx.Response(
            status,
            headers={"Retry-After": "2"} if status == 429 else {},
            json=_transaction() if status == 200 else {"error": {"code": "temporary"}},
        )

    charge = _provider(handler, attempts=3, sleeper=delays.append).get_charge("tx_123")
    assert charge.provider_charge_id == "tx_123"
    assert delays == [2.0, 1.0]


def test_provider_retries_timeout_then_raises_without_leaking_key():
    def handler(request):
        raise httpx.ReadTimeout("timeout", request=request)

    with pytest.raises(BravoPayError) as caught:
        _provider(handler, attempts=2).get_charge("tx_123")
    assert "bp_live_test" not in str(caught.value)


def test_provider_raises_after_repeated_5xx():
    def handler(_request):
        return httpx.Response(503, json={"error": {"code": "internal_error"}})

    with pytest.raises(BravoPayError):
        _provider(handler, attempts=2).get_charge("tx_123")
