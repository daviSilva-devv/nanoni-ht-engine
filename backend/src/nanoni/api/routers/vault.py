from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.core.config import get_settings
from nanoni.core.db import get_db
from nanoni.core.security import require_admin
from nanoni.domain.models import MediaAsset, VaultObject
from nanoni.integrations.telegram.vault import enqueue_pack_vault_uploads

router = APIRouter(prefix="/vault", tags=["vault"])
Admin = Annotated[None, Depends(require_admin)]
DB = Annotated[Session, Depends(get_db)]


class VaultJobRead(BaseModel):
    id: str
    status: str
    asset_id: str


class VaultEnqueueRead(BaseModel):
    pack_id: str
    jobs: list[VaultJobRead]


class VaultAssetRead(BaseModel):
    asset_id: str
    status: str
    vault_chat_id: str | None
    vault_message_id: str | None
    telegram_file_id: str | None
    telegram_file_unique_id: str | None
    verified: bool


@router.post("/packs/{pack_id}", response_model=VaultEnqueueRead)
def enqueue_pack(pack_id: str, _: Admin, db: DB) -> VaultEnqueueRead:
    try:
        jobs = enqueue_pack_vault_uploads(
            db,
            pack_id=pack_id,
            vault_chat_id=get_settings().telegram_vault_chat_id,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    return VaultEnqueueRead(
        pack_id=pack_id,
        jobs=[
            VaultJobRead(id=job.id, status=job.status, asset_id=str(job.payload["asset_id"]))
            for job in jobs
        ],
    )


@router.get("/assets/{asset_id}", response_model=VaultAssetRead)
def asset_status(asset_id: str, _: Admin, db: DB) -> VaultAssetRead:
    asset = db.get(MediaAsset, asset_id)
    if not asset:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "media asset not found")
    vault_object = db.scalar(select(VaultObject).where(VaultObject.asset_id == asset.id))
    return VaultAssetRead(
        asset_id=asset.id,
        status=asset.status,
        vault_chat_id=asset.vault_chat_id,
        vault_message_id=asset.vault_message_id,
        telegram_file_id=asset.telegram_file_id,
        telegram_file_unique_id=asset.telegram_file_unique_id,
        verified=bool(vault_object and vault_object.verified_at),
    )
