import hashlib
import hmac
import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.core.config import get_settings
from nanoni.core.db import get_db
from nanoni.core.security import require_admin
from nanoni.domain.enums import ApprovalDecision
from nanoni.domain.models import ContentCandidate, ContentPack, Source
from nanoni.domain.schemas import (
    CandidateDecision,
    CandidateImport,
    CandidateRead,
    MediaManifest,
    SourceCreate,
    SourceRead,
)
from nanoni.domain.services.content import decide_candidate, import_manifest

router = APIRouter(prefix="/content", tags=["content"])


@router.get("/sources", response_model=list[SourceRead], dependencies=[Depends(require_admin)])
def list_sources(db: Session = Depends(get_db)):
    return list(db.scalars(select(Source).order_by(Source.name)))


@router.post(
    "/sources", response_model=SourceRead, status_code=201, dependencies=[Depends(require_admin)]
)
def create_source(payload: SourceCreate, db: Session = Depends(get_db)):
    item = Source(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/candidates", response_model=list[CandidateRead], dependencies=[Depends(require_admin)]
)
def list_candidates(status_filter: str | None = None, db: Session = Depends(get_db)):
    stmt = select(ContentCandidate).order_by(ContentCandidate.created_at.desc())
    if status_filter:
        stmt = stmt.where(ContentCandidate.status == status_filter)
    return list(db.scalars(stmt))


@router.post(
    "/candidates/import",
    response_model=CandidateRead,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def import_candidate(payload: CandidateImport, db: Session = Depends(get_db)):
    try:
        item = import_manifest(db, source_id=payload.source_id, manifest=payload.manifest)
        db.commit()
        db.refresh(item)
        return item
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.post("/candidates/{candidate_id}/decision", dependencies=[Depends(require_admin)])
def decide(candidate_id: str, payload: CandidateDecision, db: Session = Depends(get_db)):
    if payload.decision not in {d.value for d in ApprovalDecision}:
        raise HTTPException(422, "invalid approval decision")
    try:
        pack = decide_candidate(
            db,
            candidate_id=candidate_id,
            decision=payload.decision,
            target=payload.target,
            microniche_ids=payload.microniche_ids,
            selected_positions=payload.selected_positions,
            notes=payload.notes,
        )
        db.commit()
        return {
            "candidate_id": candidate_id,
            "pack_id": pack.id if pack else None,
            "decision": payload.decision,
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.get("/packs", dependencies=[Depends(require_admin)])
def list_packs(db: Session = Depends(get_db)):
    rows = list(db.scalars(select(ContentPack).order_by(ContentPack.created_at.desc())))
    return [
        {
            "id": row.id,
            "candidate_id": row.candidate_id,
            "title": row.title,
            "approved": row.approved,
            "content_score": row.content_score,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def _helper_signature_valid(raw: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    expected = hmac.new(
        get_settings().helper_shared_secret.encode(), raw, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/helper/manifest", response_model=CandidateRead, status_code=status.HTTP_201_CREATED)
async def helper_manifest(
    request: Request,
    x_nanoni_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    raw = await request.body()
    if not _helper_signature_valid(raw, x_nanoni_signature):
        raise HTTPException(401, "invalid helper signature")
    try:
        payload = json.loads(raw)
        source_id = payload["source_id"]
        manifest = MediaManifest.model_validate(payload["manifest"])
        candidate = import_manifest(db, source_id=source_id, manifest=manifest)
        db.commit()
        db.refresh(candidate)
        return candidate
    except (KeyError, ValueError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.get("/runtime-layout", dependencies=[Depends(require_admin)])
def runtime_layout():
    root = get_settings().media_root
    return {
        "root": str(root),
        "folders": {
            name: str(root / name)
            for name in ["inbox", "processing", "published", "failed", "temp"]
        },
    }
