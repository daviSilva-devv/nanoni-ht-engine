from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nanoni.core.db import get_db
from nanoni.core.security import require_admin
from nanoni.domain.enums import EntitlementStatus, OrderStatus, PublicationStatus
from nanoni.domain.models import (
    Alert,
    Community,
    ContentCandidate,
    Entitlement,
    Niche,
    Order,
    Product,
    PublicationJob,
)
from nanoni.domain.schemas import DashboardSummary

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_admin)])


def _count(db: Session, model, *where) -> int:
    stmt = select(func.count()).select_from(model)
    if where:
        stmt = stmt.where(*where)
    return int(db.scalar(stmt) or 0)


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)):
    revenue = db.scalar(
        select(func.coalesce(func.sum(Order.total_amount), 0)).where(
            Order.status.in_([OrderStatus.PAID, OrderStatus.ACCESS_PENDING, OrderStatus.FULFILLED])
        )
    )
    return DashboardSummary(
        niches=_count(db, Niche),
        communities=_count(db, Community),
        active_products=_count(db, Product, Product.active.is_(True)),
        pending_content=_count(db, ContentCandidate, ContentCandidate.status == "PENDING_APPROVAL"),
        queued_publications=_count(
            db,
            PublicationJob,
            PublicationJob.status.in_([PublicationStatus.QUEUED, PublicationStatus.SCHEDULED]),
        ),
        open_alerts=_count(db, Alert, Alert.resolved_at.is_(None)),
        paid_orders=_count(
            db,
            Order,
            Order.status.in_([OrderStatus.PAID, OrderStatus.ACCESS_PENDING, OrderStatus.FULFILLED]),
        ),
        active_entitlements=_count(db, Entitlement, Entitlement.status == EntitlementStatus.ACTIVE),
        revenue_confirmed=Decimal(revenue or 0),
    )
