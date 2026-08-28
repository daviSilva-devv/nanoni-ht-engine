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
        self, payload: dict[str, Any], headers: dict[str, str] | None = None
    ) -> WebhookEvent: ...

    def cancel_charge(self, provider_charge_id: str) -> None:
        raise NotImplementedError

    def refund(self, provider_charge_id: str) -> None:
        raise NotImplementedError
