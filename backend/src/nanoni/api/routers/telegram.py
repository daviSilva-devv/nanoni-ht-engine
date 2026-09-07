import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from nanoni.core.config import get_settings
from nanoni.core.db import get_db
from nanoni.domain.services.access import process_join_request
from nanoni.integrations.telegram.publisher import BotAPITelegramPublisher

router = APIRouter(prefix="/telegram", tags=["telegram"])


class TelegramChat(BaseModel):
    id: int


class TelegramUser(BaseModel):
    id: int


class TelegramJoinRequest(BaseModel):
    chat: TelegramChat
    from_: TelegramUser = Field(alias="from")


class TelegramUpdate(BaseModel):
    update_id: int
    chat_join_request: TelegramJoinRequest | None = None


@router.post("/webhook")
def telegram_webhook(
    update: TelegramUpdate,
    secret: Annotated[str | None, Header(alias="X-Telegram-Bot-Api-Secret-Token")] = None,
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if (
        not settings.telegram_webhook_secret
        or secret is None
        or not secrets.compare_digest(secret, settings.telegram_webhook_secret)
    ):
        raise HTTPException(401, "invalid Telegram webhook secret")
    request = update.chat_join_request
    if request is None:
        return {"accepted": True, "handled": False}

    publisher = BotAPITelegramPublisher(
        bot_token=settings.telegram_bot_token,
        api_base_url=settings.telegram_api_base_url,
    )
    try:
        grant = process_join_request(
            db,
            chat_id=str(request.chat.id),
            telegram_user_id=str(request.from_.id),
            publisher=publisher,
        )
        db.commit()
        return {"accepted": True, "handled": True, "approved": grant is not None}
    finally:
        publisher.close()
