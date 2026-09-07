from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.domain.enums import (
    EntitlementStatus,
    LeadState,
    OrderStatus,
    PaymentStatus,
)
from nanoni.domain.models import (
    CommunityVersion,
    Customer,
    Entitlement,
    Lead,
    Order,
    OrderItem,
    Payment,
    PaymentEvent,
    PricePlan,
    Product,
)
from nanoni.domain.services.access import plan_membership_grants
from nanoni.domain.services.sales import record_lead_event
from nanoni.domain.transitions import ensure_transition
from nanoni.integrations.payment.base import PaymentProvider, WebhookEvent
from nanoni.jobs.engine import enqueue


def get_or_create_customer(
    db: Session,
    *,
    telegram_user_id: str,
    username: str | None = None,
    display_name: str | None = None,
) -> Customer:
    customer = db.scalar(select(Customer).where(Customer.telegram_user_id == telegram_user_id))
    if customer:
        if username is not None:
            customer.username = username
        if display_name is not None:
            customer.display_name = display_name
        db.add(customer)
        return customer
    customer = Customer(
        telegram_user_id=telegram_user_id, username=username, display_name=display_name
    )
    db.add(customer)
    db.flush()
    db.add(Lead(customer_id=customer.id, state=LeadState.NEW))
    db.flush()
    return customer


def create_order(
    db: Session,
    provider: PaymentProvider,
    *,
    telegram_user_id: str,
    username: str | None,
    display_name: str | None,
    price_plan_id: str,
    idempotency_key: str,
) -> tuple[Order, Payment]:
    existing = db.scalar(select(Order).where(Order.idempotency_key == idempotency_key))
    if existing:
        payment = db.scalar(select(Payment).where(Payment.order_id == existing.id))
        if not payment:
            raise RuntimeError("idempotent order exists without payment")
        return existing, payment

    plan = db.get(PricePlan, price_plan_id)
    if not plan or not plan.active:
        raise ValueError("price plan not found or inactive")
    product = db.get(Product, plan.product_id)
    if not product or not product.active:
        raise ValueError("product not found or inactive")

    customer = get_or_create_customer(
        db, telegram_user_id=telegram_user_id, username=username, display_name=display_name
    )
    order = Order(
        customer_id=customer.id,
        status=OrderStatus.CREATED,
        currency=plan.currency,
        total_amount=plan.amount,
        idempotency_key=idempotency_key,
    )
    db.add(order)
    db.flush()
    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        price_plan_id=plan.id,
        quantity=1,
        unit_amount=plan.amount,
    )
    db.add(item)
    db.flush()

    charge = provider.create_charge(
        order_id=order.id,
        amount=Decimal(plan.amount),
        currency=plan.currency,
        idempotency_key=idempotency_key,
    )
    ensure_transition(OrderStatus, order.status, OrderStatus.CHECKOUT_READY)
    order.status = OrderStatus.CHECKOUT_READY
    order.checkout_url = charge.checkout_url
    payment = Payment(
        order_id=order.id,
        provider=provider.name,
        provider_charge_id=charge.provider_charge_id,
        status=PaymentStatus.PENDING,
        amount=charge.amount,
        currency=charge.currency,
        checkout_payload=charge.payload,
    )
    db.add(payment)
    ensure_transition(OrderStatus, order.status, OrderStatus.PAYMENT_PENDING)
    order.status = OrderStatus.PAYMENT_PENDING
    db.add(order)

    lead = db.scalar(select(Lead).where(Lead.customer_id == customer.id))
    if lead:
        record_lead_event(
            db, lead, "CHECKOUT_STARTED", product_id=product.id, payload={"order_id": order.id}
        )
        record_lead_event(
            db, lead, "PAYMENT_PENDING", product_id=product.id, payload={"order_id": order.id}
        )
    db.flush()
    return order, payment


def _payment_status_from_provider(status: str) -> str:
    normalized = status.upper()
    if normalized in {"CONFIRMED", "PAID", "APPROVED"}:
        return PaymentStatus.CONFIRMED
    if normalized in {"EXPIRED"}:
        return PaymentStatus.EXPIRED
    if normalized in {"FAILED", "CANCELLED", "REJECTED"}:
        return PaymentStatus.FAILED
    return PaymentStatus.PENDING


def process_payment_event(db: Session, provider_name: str, event: WebhookEvent) -> Payment:
    existing_event = db.scalar(
        select(PaymentEvent).where(
            PaymentEvent.provider == provider_name,
            PaymentEvent.provider_event_id == event.provider_event_id,
        )
    )
    if existing_event and existing_event.processed:
        if not existing_event.payment_id:
            raise RuntimeError("processed payment event without payment")
        payment = db.get(Payment, existing_event.payment_id)
        if not payment:
            raise RuntimeError("payment event references missing payment")
        return payment

    payment = db.scalar(
        select(Payment).where(
            Payment.provider == provider_name,
            Payment.provider_charge_id == event.provider_charge_id,
        )
    )
    if not payment:
        raise ValueError("unknown provider charge")

    payment_event = existing_event or PaymentEvent(
        payment_id=payment.id,
        provider=provider_name,
        provider_event_id=event.provider_event_id,
        event_type=event.event_type,
        payload=event.payload,
    )
    db.add(payment_event)

    target = _payment_status_from_provider(event.status)
    if target != payment.status:
        ensure_transition(PaymentStatus, payment.status, target)
        payment.status = target
    if target == PaymentStatus.CONFIRMED:
        payment.confirmed_at = datetime.now(UTC)
        order = db.get(Order, payment.order_id)
        if not order:
            raise RuntimeError("payment order missing")
        if order.status != OrderStatus.PAID:
            ensure_transition(OrderStatus, order.status, OrderStatus.PAID)
            order.status = OrderStatus.PAID
            db.add(order)
        enqueue(
            db,
            job_type="FULFILL_ACCESS",
            payload={"order_id": order.id},
            idempotency_key=f"fulfill-order:{order.id}",
        )
        lead = db.scalar(select(Lead).where(Lead.customer_id == order.customer_id))
        if lead:
            record_lead_event(db, lead, "PAYMENT_CONFIRMED", payload={"order_id": order.id})
    payment_event.processed = True
    db.add(payment_event)
    db.add(payment)
    db.flush()
    return payment


def fulfill_order_entitlements(db: Session, order_id: str) -> list[Entitlement]:
    order = db.get(Order, order_id)
    if not order:
        raise ValueError("order not found")
    if order.status == OrderStatus.FULFILLED:
        entitlements = list(
            db.scalars(
                select(Entitlement)
                .join(OrderItem, Entitlement.source_order_item_id == OrderItem.id)
                .where(OrderItem.order_id == order.id)
            )
        )
        for entitlement in entitlements:
            plan_membership_grants(db, entitlement.id)
        return entitlements
    if order.status != OrderStatus.PAID and order.status != OrderStatus.ACCESS_PENDING:
        raise ValueError(f"order {order.id} is not paid")
    if order.status == OrderStatus.PAID:
        ensure_transition(OrderStatus, order.status, OrderStatus.ACCESS_PENDING)
        order.status = OrderStatus.ACCESS_PENDING
        db.add(order)

    items = list(db.scalars(select(OrderItem).where(OrderItem.order_id == order.id)))
    entitlements: list[Entitlement] = []
    now = datetime.now(UTC)
    for item in items:
        existing = db.scalar(select(Entitlement).where(Entitlement.source_order_item_id == item.id))
        if existing:
            entitlements.append(existing)
            continue
        plan = db.get(PricePlan, item.price_plan_id)
        product = db.get(Product, item.product_id)
        if not plan or not product:
            raise RuntimeError("order item references missing catalog data")
        version = db.get(CommunityVersion, product.community_version_id)
        if not version:
            raise RuntimeError("product community version missing")
        expires_at = None if plan.lifetime else now + timedelta(days=int(plan.duration_days or 0))
        if not plan.lifetime and not plan.duration_days:
            raise RuntimeError("non-lifetime plan must have duration_days")
        entitlement = Entitlement(
            customer_id=order.customer_id,
            product_id=product.id,
            community_version_id=version.id,
            price_plan_id=plan.id,
            source_order_item_id=item.id,
            starts_at=now,
            expires_at=expires_at,
            status=EntitlementStatus.ACTIVE,
        )
        db.add(entitlement)
        db.flush()
        entitlements.append(entitlement)

    ensure_transition(OrderStatus, order.status, OrderStatus.FULFILLED)
    order.status = OrderStatus.FULFILLED
    db.add(order)
    lead = db.scalar(select(Lead).where(Lead.customer_id == order.customer_id))
    if lead:
        record_lead_event(db, lead, "ACCESS_GRANTED", payload={"order_id": order.id})
    for entitlement in entitlements:
        plan_membership_grants(db, entitlement.id)
    db.flush()
    return entitlements


def expire_due_entitlements(db: Session, *, now: datetime | None = None) -> list[Entitlement]:
    now = now or datetime.now(UTC)
    rows = list(
        db.scalars(
            select(Entitlement).where(
                Entitlement.status == EntitlementStatus.ACTIVE,
                Entitlement.expires_at.is_not(None),
                Entitlement.expires_at <= now,
            )
        )
    )
    for entitlement in rows:
        ensure_transition(EntitlementStatus, entitlement.status, EntitlementStatus.EXPIRED)
        entitlement.status = EntitlementStatus.EXPIRED
        db.add(entitlement)
    db.flush()
    return rows
