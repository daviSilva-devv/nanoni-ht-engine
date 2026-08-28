from functools import lru_cache

from nanoni.core.config import get_settings
from nanoni.integrations.payment.base import PaymentProvider
from nanoni.integrations.payment.mock import MockPaymentProvider


@lru_cache
def get_payment_provider() -> PaymentProvider:
    name = get_settings().payment_provider.lower()
    if name == "mock":
        return MockPaymentProvider()
    raise RuntimeError(f"payment provider {name!r} is not implemented/configured")
