from functools import lru_cache

from nanoni.core.config import get_settings
from nanoni.integrations.payment.base import PaymentProvider
from nanoni.integrations.payment.bravopay import BravoPayProvider
from nanoni.integrations.payment.mock import MockPaymentProvider


@lru_cache
def get_payment_provider() -> PaymentProvider:
    name = get_settings().payment_provider.lower()
    if name == "mock":
        return MockPaymentProvider()
    if name == "bravopay":
        settings = get_settings()
        return BravoPayProvider(
            api_key=settings.bravopay_api_key,
            webhook_secret=settings.bravopay_webhook_secret,
            api_base_url=settings.bravopay_api_base_url,
            external_checkout_base_url=settings.external_checkout_base_url,
            expires_in=settings.bravopay_pix_expires_in,
        )
    raise RuntimeError(f"payment provider {name!r} is not implemented/configured")
