from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.core.db import get_db
from nanoni.core.security import require_admin
from nanoni.domain.models import Entitlement, Order, Payment
from nanoni.domain.schemas import (
    ConfirmMockPayment,
    EntitlementRead,
    OrderCreate,
    OrderRead,
    PaymentRead,
)
from nanoni.domain.services.commerce import (
    create_order,
    fulfill_order_entitlements,
    process_payment_event,
)
from nanoni.integrations.payment.bravopay import (
    BravoPayConfigurationError,
    BravoPayProvider,
    BravoPayWebhookError,
)
from nanoni.integrations.payment.mock import MockPaymentProvider
from nanoni.integrations.payment.registry import get_payment_provider

router = APIRouter(prefix="/commerce", tags=["commerce"])


@router.post("/orders", response_model=OrderRead, status_code=201)
def order_create(payload: OrderCreate, db: Session = Depends(get_db)):
    provider = get_payment_provider()
    try:
        order, _ = create_order(
            db,
            provider,
            telegram_user_id=payload.telegram_user_id,
            username=payload.username,
            display_name=payload.display_name,
            price_plan_id=payload.price_plan_id,
            idempotency_key=payload.idempotency_key,
        )
        db.commit()
        db.refresh(order)
        return order
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.get("/orders/{order_id}", response_model=OrderRead)
def order_get(order_id: str, db: Session = Depends(get_db)):
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, "order not found")
    return order


@router.get("/orders/{order_id}/payment", response_model=PaymentRead)
def order_payment(order_id: str, db: Session = Depends(get_db)):
    payment = db.scalar(select(Payment).where(Payment.order_id == order_id))
    if not payment:
        raise HTTPException(404, "payment not found")
    return payment


@router.post(
    "/mock-payments/{payment_id}/confirm",
    response_model=PaymentRead,
    dependencies=[Depends(require_admin)],
)
def mock_confirm(payment_id: str, payload: ConfirmMockPayment, db: Session = Depends(get_db)):
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "payment not found")
    provider = get_payment_provider()
    if not isinstance(provider, MockPaymentProvider):
        raise HTTPException(409, "mock endpoint disabled for configured provider")
    provider.confirm(payment.provider_charge_id)
    event = provider.parse_webhook(
        {
            "event_id": payload.provider_event_id,
            "charge_id": payment.provider_charge_id,
            "status": "CONFIRMED",
            "event_type": "payment.confirmed",
        }
    )
    updated = process_payment_event(db, provider.name, event)
    db.commit()
    db.refresh(updated)
    return updated


@router.post(
    "/orders/{order_id}/fulfill",
    response_model=list[EntitlementRead],
    dependencies=[Depends(require_admin)],
)
def fulfill(order_id: str, db: Session = Depends(get_db)):
    try:
        rows = fulfill_order_entitlements(db, order_id)
        db.commit()
        return rows
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.post("/webhooks/bravopay")
async def bravopay_webhook(request: Request, db: Session = Depends(get_db)):
    provider = get_payment_provider()
    if not isinstance(provider, BravoPayProvider):
        raise HTTPException(404, "BravoPay provider not configured")
    raw_body = await request.body()
    try:
        event = provider.parse_webhook(raw_body, dict(request.headers))
        payment = process_payment_event(db, provider.name, event)
        db.commit()
        return {"accepted": True, "payment_id": payment.id, "status": payment.status}
    except BravoPayWebhookError as exc:
        db.rollback()
        raise HTTPException(401, str(exc)) from exc
    except BravoPayConfigurationError as exc:
        db.rollback()
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.post("/webhooks/{provider_name}")
async def payment_webhook(provider_name: str, request: Request, db: Session = Depends(get_db)):
    provider = get_payment_provider()
    if provider_name != provider.name:
        raise HTTPException(404, "provider not configured")
    payload = await request.json()
    try:
        event = provider.parse_webhook(payload, dict(request.headers))
        payment = process_payment_event(db, provider.name, event)
        db.commit()
        return {"accepted": True, "payment_id": payment.id, "status": payment.status}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc


@router.post(
    "/payments/{payment_id}/recheck",
    response_model=PaymentRead,
    dependencies=[Depends(require_admin)],
)
def payment_recheck(payment_id: str, db: Session = Depends(get_db)):
    payment = db.get(Payment, payment_id)
    if not payment:
        raise HTTPException(404, "payment not found")
    provider = get_payment_provider()
    if payment.provider != provider.name:
        raise HTTPException(409, "payment provider is not currently configured")
    charge = provider.get_charge(payment.provider_charge_id)
    event = provider.event_from_charge(
        charge,
        event_id=f"recheck:{payment.id}:{charge.status}",
    )
    updated = process_payment_event(db, provider.name, event)
    db.commit()
    db.refresh(updated)
    return updated


@router.get(
    "/entitlements", response_model=list[EntitlementRead], dependencies=[Depends(require_admin)]
)
def entitlement_list(customer_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Entitlement).order_by(Entitlement.created_at.desc())
    if customer_id:
        stmt = stmt.where(Entitlement.customer_id == customer_id)
    return list(db.scalars(stmt))
