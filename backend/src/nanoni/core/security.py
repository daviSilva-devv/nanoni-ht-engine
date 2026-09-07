import hashlib
import hmac
import time

from fastapi import Header, HTTPException, status

from nanoni.core.config import get_settings


def require_admin(x_admin_token: str | None = Header(default=None)) -> None:
    expected = get_settings().admin_token
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid admin token")


def verify_helper_signature(body: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    secret = get_settings().helper_shared_secret.encode()
    digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def verify_helper_upload_signature(
    candidate_id: str,
    timestamp: str | None,
    signature: str | None,
    *,
    now: int | None = None,
    max_age_seconds: int = 300,
) -> bool:
    if not timestamp or not signature:
        return False
    try:
        issued_at = int(timestamp)
    except ValueError:
        return False
    current = int(time.time()) if now is None else now
    if abs(current - issued_at) > max_age_seconds:
        return False
    message = f"{timestamp}:{candidate_id}".encode()
    expected = hmac.new(
        get_settings().helper_shared_secret.encode(), message, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
