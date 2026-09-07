from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import httpx

from nanoni.integrations.payment.base import Charge, PaymentProvider, WebhookEvent


class BravoPayError(RuntimeError):
    pass


class BravoPayConfigurationError(BravoPayError):
    pass


class BravoPayWebhookError(ValueError):
    pass


class BravoPayProvider(PaymentProvider):
    name = "bravopay"

    def __init__(
        self,
        *,
        api_key: str,
        webhook_secret: str,
        api_base_url: str = "https://bravopay.club/api/v1",
        external_checkout_base_url: str = "http://localhost:3000/checkout",
        expires_in: int = 3600,
        client: httpx.Client | None = None,
        attempts: int = 3,
        backoff_seconds: float = 0.5,
        sleeper: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.time,
        webhook_tolerance_seconds: int = 300,
    ) -> None:
        if not api_key:
            raise BravoPayConfigurationError("BravoPay API key is not configured")
        if not 60 <= expires_in <= 86400:
            raise BravoPayConfigurationError("BravoPay PIX expiry must be between 60 and 86400")
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.api_base_url = api_base_url.rstrip("/")
        self.external_checkout_base_url = external_checkout_base_url.rstrip("/")
        self.expires_in = expires_in
        self.client = client or httpx.Client(timeout=httpx.Timeout(30))
        self._owns_client = client is None
        self.attempts = max(1, attempts)
        self.backoff_seconds = max(0, backoff_seconds)
        self.sleeper = sleeper
        self.clock = clock
        self.webhook_tolerance_seconds = webhook_tolerance_seconds

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            **kwargs.pop("headers", {}),
        }
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self.client.request(
                    method, f"{self.api_base_url}{path}", headers=headers, **kwargs
                )
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt + 1 < self.attempts:
                        retry_after = response.headers.get("Retry-After")
                        delay = (
                            float(retry_after)
                            if retry_after and retry_after.replace(".", "", 1).isdigit()
                            else self.backoff_seconds * (2**attempt)
                        )
                        self.sleeper(delay)
                        continue
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise BravoPayError("BravoPay returned a non-object response")
                return payload
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt + 1 < self.attempts:
                    self.sleeper(self.backoff_seconds * (2**attempt))
                    continue
                raise BravoPayError("BravoPay request failed after retries") from exc
            except (httpx.HTTPStatusError, json.JSONDecodeError) as exc:
                raise BravoPayError("BravoPay request failed") from exc
        raise BravoPayError("BravoPay request failed after retries") from last_error

    @staticmethod
    def _amount_to_cents(amount: Decimal) -> int:
        cents = amount * 100
        if cents != cents.to_integral_value():
            raise ValueError("BravoPay amount must have at most two decimal places")
        return int(cents)

    def create_charge(
        self, *, order_id: str, amount: Decimal, currency: str, idempotency_key: str
    ) -> Charge:
        if currency.upper() != "BRL":
            raise ValueError("BravoPay PIX only supports BRL")
        body = {
            "amount_cents": self._amount_to_cents(amount),
            "method": "pix",
            "external_reference": order_id,
            "metadata": {"order_id": order_id},
            "expires_in": self.expires_in,
        }
        payload = self._request(
            "POST",
            "/transactions",
            headers={"Content-Type": "application/json", "Idempotency-Key": idempotency_key},
            json=body,
        )
        if not payload.get("external_reference"):
            payload["external_reference"] = order_id
        if not payload.get("metadata"):
            payload["metadata"] = body["metadata"]
        return self._charge_from_transaction(payload)

    def get_charge(self, provider_charge_id: str) -> Charge:
        return self._charge_from_transaction(
            self._request("GET", f"/transactions/{provider_charge_id}")
        )

    def _charge_from_transaction(self, payload: dict[str, Any]) -> Charge:
        try:
            transaction_id = str(payload["id"])
            amount = Decimal(int(payload["amount_cents"])) / 100
            currency = str(payload["currency"])
            status = str(payload["status"])
        except (KeyError, TypeError, ValueError) as exc:
            raise BravoPayError("BravoPay transaction response is invalid") from exc
        pix = payload.get("pix")
        if status.upper() == "PENDING" and (
            not isinstance(pix, dict) or not pix.get("copy_paste") or not pix.get("expires_at")
        ):
            raise BravoPayError("BravoPay PIX response is missing copy_paste or expires_at")
        return Charge(
            provider_charge_id=transaction_id,
            amount=amount,
            currency=currency,
            status=status,
            checkout_url=f"{self.external_checkout_base_url}/{payload.get('external_reference', '')}".rstrip(
                "/"
            ),
            payload=payload,
        )

    def parse_webhook(
        self, payload: dict[str, Any] | bytes, headers: dict[str, str] | None = None
    ) -> WebhookEvent:
        if not isinstance(payload, bytes):
            raise BravoPayWebhookError("BravoPay webhook verification requires the raw body")
        if not self.webhook_secret:
            raise BravoPayConfigurationError("BravoPay webhook secret is not configured")
        normalized_headers = {key.lower(): value for key, value in (headers or {}).items()}
        signature = normalized_headers.get("bravopay-signature") or normalized_headers.get(
            "x-bravopay-signature"
        )
        timestamp, supplied = self._parse_signature(signature)
        if abs(self.clock() - timestamp) > self.webhook_tolerance_seconds:
            raise BravoPayWebhookError("BravoPay webhook timestamp is outside tolerance")
        signed = str(timestamp).encode() + b"." + payload
        expected = hmac.new(self.webhook_secret.encode(), signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, supplied):
            raise BravoPayWebhookError("invalid BravoPay webhook signature")
        try:
            envelope = json.loads(payload)
            event_id = str(envelope["id"])
            event_type = str(envelope["type"])
            transaction = envelope["data"]
            charge_id = str(transaction["id"])
            status = str(transaction["status"])
            amount = Decimal(int(transaction["amount_cents"])) / 100
            currency = str(transaction["currency"])
            external_reference = str(transaction["external_reference"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BravoPayWebhookError("invalid BravoPay webhook payload") from exc
        if not event_id or not event_type.startswith("transaction."):
            raise BravoPayWebhookError("unsupported BravoPay webhook event")
        expected_status = {
            "transaction.created": "PENDING",
            "transaction.paid": "PAID",
            "transaction.expired": "EXPIRED",
            "transaction.failed": "FAILED",
            "transaction.refunded": "REFUNDED",
            "transaction.chargeback": "CHARGEBACK",
        }.get(event_type)
        if expected_status is None or status.upper() != expected_status:
            raise BravoPayWebhookError("BravoPay event type and transaction status mismatch")
        return WebhookEvent(
            provider_event_id=event_id,
            provider_charge_id=charge_id,
            event_type=event_type,
            status=status,
            payload=envelope,
            external_reference=external_reference,
            amount=amount,
            currency=currency,
        )

    @staticmethod
    def _parse_signature(signature: str | None) -> tuple[int, str]:
        try:
            parts = dict(part.split("=", 1) for part in (signature or "").split(","))
            timestamp = int(parts["t"])
            supplied = parts["v1"]
        except (KeyError, TypeError, ValueError) as exc:
            raise BravoPayWebhookError("missing or malformed BravoPay signature") from exc
        if not supplied:
            raise BravoPayWebhookError("missing or malformed BravoPay signature")
        return timestamp, supplied
