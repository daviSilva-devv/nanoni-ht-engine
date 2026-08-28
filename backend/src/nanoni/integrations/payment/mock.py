from decimal import Decimal
from uuid import uuid4

from nanoni.integrations.payment.base import Charge, PaymentProvider, WebhookEvent


class MockPaymentProvider(PaymentProvider):
    name = "mock"

    def __init__(self) -> None:
        self._charges: dict[str, Charge] = {}

    def create_charge(
        self, *, order_id: str, amount: Decimal, currency: str, idempotency_key: str
    ) -> Charge:
        provider_charge_id = f"mock_{order_id}"
        existing = self._charges.get(provider_charge_id)
        if existing:
            return existing
        charge = Charge(
            provider_charge_id=provider_charge_id,
            amount=amount,
            currency=currency,
            status="PENDING",
            checkout_url=f"http://localhost:8010/api/v1/mock-payments/{provider_charge_id}",
            payload={"copy_paste": f"MOCK-PIX-{provider_charge_id}", "qr_code": None},
        )
        self._charges[provider_charge_id] = charge
        return charge

    def get_charge(self, provider_charge_id: str) -> Charge:
        return self._charges[provider_charge_id]

    def confirm(self, provider_charge_id: str) -> Charge:
        current = self._charges[provider_charge_id]
        updated = Charge(
            provider_charge_id=current.provider_charge_id,
            amount=current.amount,
            currency=current.currency,
            status="CONFIRMED",
            checkout_url=current.checkout_url,
            payload=current.payload,
        )
        self._charges[provider_charge_id] = updated
        return updated

    def parse_webhook(self, payload: dict, headers: dict[str, str] | None = None) -> WebhookEvent:
        return WebhookEvent(
            provider_event_id=str(payload.get("event_id") or uuid4()),
            provider_charge_id=str(payload["charge_id"]),
            event_type=str(payload.get("event_type", "payment.updated")),
            status=str(payload["status"]),
            payload=payload,
        )
