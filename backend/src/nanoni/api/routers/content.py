import hashlib
import hmac
import json
from collections.abc import Generator
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.core.config import get_settings
from nanoni.core.db import get_db
from nanoni.core.security import require_admin
from nanoni.domain.enums import ApprovalDecision
from nanoni.domain.models import ContentCandidate, ContentPack, MediaAsset, Source
from nanoni.domain.schemas import (
    CandidateDecision,
    CandidateImport,
    CandidateImportRead,
    CandidateRead,
    CandidateReview,
    EromeLocator,
    MediaManifest,
    PackItemOrder,
    PackItemSelection,
    PackRead,
    PackUpdate,
    SelectedAcquisitionRead,
    SourceCreate,
    SourceRead,
    WatchFolderScanResult,
    WatchFolderStatus,
)
from nanoni.domain.services.content import (
    ImportOutcome,
    classify_manifest,
    decide_candidate,
    import_manifest_with_classification,
    pack_read,
    reorder_pack,
    set_pack_selection,
    update_pack,
)
from nanoni.integrations.source.erome import (
    EromeAdapter,
    EromeAdapterError,
    EromeTimeout,
    UnsafeEromeUrl,
    UnsupportedEromeUrl,
)
from nanoni.integrations.source.erome_service import (
    enqueue_selected_acquisition,
    inspect_and_import,
)
from nanoni.media.importer import import_streams
from nanoni.media.runtime import ensure_runtime_layout, original_file
from nanoni.media.watch_folder import scan_watch_folder, watch_folder_status

router = APIRouter(prefix="/content", tags=["content"])
Admin = Annotated[None, Depends(require_admin)]
DB = Annotated[Session, Depends(get_db)]


def get_erome_adapter() -> Generator[EromeAdapter, None, None]:
    adapter = EromeAdapter()
    try:
        yield adapter
    finally:
        adapter.client.close()


Erome = Annotated[EromeAdapter, Depends(get_erome_adapter)]


def _raise_erome_http_error(exc: EromeAdapterError) -> None:
    if isinstance(exc, (UnsupportedEromeUrl, UnsafeEromeUrl)):
        code = status.HTTP_422_UNPROCESSABLE_ENTITY
    elif isinstance(exc, EromeTimeout):
        code = status.HTTP_504_GATEWAY_TIMEOUT
    else:
        code = status.HTTP_502_BAD_GATEWAY
    raise HTTPException(code, {"code": exc.code, "message": str(exc)}) from exc


def _import_response(outcome: ImportOutcome) -> CandidateImportRead:
    data = CandidateRead.model_validate(outcome.candidate).model_dump()
    return CandidateImportRead(
        **data,
        pack_id=outcome.pack.id,
        import_classification=outcome.classification,
    )


@router.get("/sources", response_model=list[SourceRead])
def list_sources(_: Admin, db: DB):
    return list(db.scalars(select(Source).order_by(Source.name)))


@router.post("/sources", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(payload: SourceCreate, _: Admin, db: DB):
    item = Source(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/candidates", response_model=list[CandidateRead])
def list_candidates(_: Admin, db: DB, status_filter: str | None = None):
    stmt = select(ContentCandidate).order_by(ContentCandidate.created_at.desc())
    if status_filter:
        stmt = stmt.where(ContentCandidate.status == status_filter)
    return list(db.scalars(stmt))


@router.get("/candidates/{candidate_id}", response_model=CandidateImportRead)
def candidate_detail(candidate_id: str, _: Admin, db: DB):
    candidate = db.get(ContentCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "candidate not found")
    pack = db.scalar(select(ContentPack).where(ContentPack.candidate_id == candidate_id))
    if not pack:
        raise HTTPException(status.HTTP_409_CONFLICT, "candidate has no content pack")
    return _import_response(ImportOutcome(candidate, pack, candidate.duplicate_classification))


@router.post(
    "/candidates/import",
    response_model=CandidateImportRead,
    status_code=status.HTTP_201_CREATED,
)
def import_candidate(payload: CandidateImport, _: Admin, db: DB):
    try:
        outcome = import_manifest_with_classification(
            db, source_id=payload.source_id, manifest=payload.manifest
        )
        db.commit()
        db.refresh(outcome.candidate)
        return _import_response(outcome)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post("/duplicates/classify")
def classify_duplicate(payload: CandidateImport, _: Admin, db: DB):
    return {
        "classification": classify_manifest(
            db, source_id=payload.source_id, manifest=payload.manifest
        )
    }


@router.post(
    "/manual-import",
    response_model=CandidateImportRead,
    status_code=status.HTTP_201_CREATED,
)
def manual_import(
    _: Admin,
    db: DB,
    files: Annotated[list[UploadFile], File()],
    title: Annotated[str | None, Form()] = None,
):
    try:
        outcome = import_streams(
            db,
            files=((item.filename or "upload", item.content_type, item.file) for item in files),
            root=get_settings().media_root,
            title=title,
        )
        db.commit()
        db.refresh(outcome.candidate)
        return _import_response(outcome)
    except (OSError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    finally:
        for item in files:
            item.file.close()


@router.post("/erome/inspect", response_model=MediaManifest)
def inspect_erome(payload: EromeLocator, _: Admin, adapter: Erome):
    try:
        return adapter.inspect(payload.locator)
    except EromeAdapterError as exc:
        _raise_erome_http_error(exc)


@router.post(
    "/erome/import",
    response_model=CandidateImportRead,
    status_code=status.HTTP_201_CREATED,
)
def import_erome(payload: EromeLocator, _: Admin, db: DB, adapter: Erome):
    try:
        outcome = inspect_and_import(db, payload.locator, adapter)
        db.commit()
        db.refresh(outcome.candidate)
        return _import_response(outcome)
    except EromeAdapterError as exc:
        db.rollback()
        _raise_erome_http_error(exc)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post("/packs/{pack_id}/acquire-selected", response_model=SelectedAcquisitionRead)
def acquire_selected(pack_id: str, _: Admin, db: DB):
    try:
        jobs = enqueue_selected_acquisition(db, pack_id)
        db.commit()
        return SelectedAcquisitionRead(
            pack_id=pack_id,
            jobs=[
                {"id": job.id, "status": job.status, "pack_item_id": str(job.payload["pack_item_id"])}
                for job in jobs
            ],
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


def _decision(
    candidate_id: str,
    *,
    decision: ApprovalDecision,
    payload: CandidateReview,
    db: Session,
) -> dict:
    try:
        pack = decide_candidate(
            db,
            candidate_id=candidate_id,
            decision=decision,
            target=payload.target,
            microniche_ids=payload.microniche_ids,
            selected_positions=payload.selected_positions,
            notes=payload.notes,
        )
        db.commit()
        return {
            "candidate_id": candidate_id,
            "pack_id": pack.id if pack else None,
            "decision": decision,
        }
    except (OSError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.post("/candidates/{candidate_id}/decision")
def decide(candidate_id: str, payload: CandidateDecision, _: Admin, db: DB):
    try:
        decision = ApprovalDecision(payload.decision)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "invalid approval decision"
        ) from exc
    review = CandidateReview.model_validate(payload.model_dump(exclude={"decision"}))
    return _decision(candidate_id, decision=decision, payload=review, db=db)


@router.post("/candidates/{candidate_id}/approve")
def approve(candidate_id: str, payload: CandidateReview, _: Admin, db: DB):
    return _decision(candidate_id, decision=ApprovalDecision.APPROVED, payload=payload, db=db)


@router.post("/candidates/{candidate_id}/reject")
def reject(candidate_id: str, payload: CandidateReview, _: Admin, db: DB):
    return _decision(candidate_id, decision=ApprovalDecision.REJECTED, payload=payload, db=db)


@router.post("/candidates/{candidate_id}/defer")
def defer(candidate_id: str, payload: CandidateReview, _: Admin, db: DB):
    return _decision(candidate_id, decision=ApprovalDecision.DEFERRED, payload=payload, db=db)


@router.get("/packs")
def list_packs(_: Admin, db: DB):
    rows = list(db.scalars(select(ContentPack).order_by(ContentPack.created_at.desc())))
    return [
        {
            "id": row.id,
            "candidate_id": row.candidate_id,
            "title": row.title,
            "status": row.status,
            "approved": row.approved,
            "content_score": row.content_score,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/packs/{pack_id}", response_model=PackRead)
def pack_detail(pack_id: str, _: Admin, db: DB):
    try:
        return pack_read(db, pack_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


@router.patch("/packs/{pack_id}", response_model=PackRead)
def patch_pack(pack_id: str, payload: PackUpdate, _: Admin, db: DB):
    try:
        update_pack(
            db,
            pack_id=pack_id,
            title=payload.title,
            caption=payload.caption,
            tags=payload.tags,
            microniche_ids=payload.microniche_ids,
            metadata=payload.metadata,
            provided_fields=payload.model_fields_set,
        )
        db.commit()
        return pack_read(db, pack_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.put("/packs/{pack_id}/selection", response_model=PackRead)
def select_pack_items(pack_id: str, payload: PackItemSelection, _: Admin, db: DB):
    try:
        set_pack_selection(db, pack_id, payload.selected_positions)
        db.commit()
        return pack_read(db, pack_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.put("/packs/{pack_id}/order", response_model=PackRead)
def order_pack_items(pack_id: str, payload: PackItemOrder, _: Admin, db: DB):
    try:
        reorder_pack(db, pack_id, payload.item_ids)
        db.commit()
        return pack_read(db, pack_id)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/assets/{asset_id}/original")
def get_original_asset(asset_id: str, _: Admin, db: DB):
    asset = db.get(MediaAsset, asset_id)
    if not asset or not asset.local_path:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "original asset not found")
    try:
        path = original_file(asset.local_path, get_settings().media_root)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "original asset not found") from exc
    return FileResponse(
        path,
        media_type=asset.mime,
        filename=asset.original_filename or path.name,
        content_disposition_type="inline",
    )


@router.post("/watch-folder/scan", response_model=WatchFolderScanResult)
def scan_watch(_: Admin, db: DB):
    result = scan_watch_folder(db, root=get_settings().media_root)
    db.commit()
    return WatchFolderScanResult(
        candidate_ids=result.candidate_ids,
        failed_files=result.failed_files,
        recovered_files=result.recovered_files,
    )


@router.get("/watch-folder/status", response_model=WatchFolderStatus)
def watch_status(_: Admin):
    folders, counts = watch_folder_status(get_settings().media_root)
    return WatchFolderStatus(folders=folders, counts=counts)


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
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid helper signature")
    try:
        payload = json.loads(raw)
        manifest = MediaManifest.model_validate(payload["manifest"])
        outcome = import_manifest_with_classification(
            db, source_id=payload["source_id"], manifest=manifest
        )
        db.commit()
        db.refresh(outcome.candidate)
        return outcome.candidate
    except (KeyError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc


@router.get("/runtime-layout")
def runtime_layout(_: Admin):
    layout = ensure_runtime_layout(get_settings().media_root)
    return {
        "root": str(layout["root"]),
        "folders": {
            name: str(layout[name]) for name in ("inbox", "processing", "ready", "failed", "temp")
        },
    }
