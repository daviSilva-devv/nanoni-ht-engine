from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class Charge:
    provider_charge_id: str
    amount: Decimal
    currency: str
    status: str
    checkout_url: str | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class WebhookEvent:
    provider_event_id: str
    provider_charge_id: str
    event_type: str
    status: str
    payload: dict[str, Any]
    external_reference: str | None = None
    amount: Decimal | None = None
    currency: str | None = None


class PaymentProvider(ABC):
    name: str

    @abstractmethod
    def create_charge(
        self, *, order_id: str, amount: Decimal, currency: str, idempotency_key: str
    ) -> Charge: ...

    @abstractmethod
    def get_charge(self, provider_charge_id: str) -> Charge: ...

    @abstractmethod
    def parse_webhook(
        self, payload: dict[str, Any] | bytes, headers: dict[str, str] | None = None
    ) -> WebhookEvent: ...

    def event_from_charge(self, charge: Charge, *, event_id: str) -> WebhookEvent:
        return WebhookEvent(
            provider_event_id=event_id,
            provider_charge_id=charge.provider_charge_id,
            event_type="payment.recheck",
            status=charge.status,
            payload=charge.payload,
            external_reference=charge.payload.get("external_reference"),
            amount=charge.amount,
            currency=charge.currency,
        )

    def cancel_charge(self, provider_charge_id: str) -> None:
        raise NotImplementedError

    def refund(self, provider_charge_id: str) -> None:
        raise NotImplementedError
