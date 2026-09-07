from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from nanoni.core.db import get_db
from nanoni.domain.schemas import SalesActionRequest, SalesRouterView, SalesStartRequest
from nanoni.domain.services.sales_router import (
    AgeConfirmationRequired,
    route_sales_action,
    start_sales_router,
)

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post("/start", response_model=SalesRouterView)
def start(payload: SalesStartRequest, db: Session = Depends(get_db)) -> SalesRouterView:
    view = start_sales_router(db, **payload.model_dump())
    db.commit()
    return view


@router.post("/action", response_model=SalesRouterView)
def action(payload: SalesActionRequest, db: Session = Depends(get_db)) -> SalesRouterView:
    try:
        view = route_sales_action(db, **payload.model_dump())
        db.commit()
        return view
    except AgeConfirmationRequired as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
