from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "nanoni-engine", "version": "0.2.0"}
