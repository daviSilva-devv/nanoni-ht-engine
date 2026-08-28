from datetime import UTC, datetime

from sqlalchemy.orm import Session

from nanoni.domain.enums import LeadState
from nanoni.domain.models import Lead, LeadEvent

EVENT_TO_STATE = {
    "AGE_CONFIRMED": LeadState.AGE_CONFIRMED,
    "INTENT_VIP": LeadState.INTENT_VIP,
    "INTENT_FREE": LeadState.INTENT_FREE,
    "PRODUCT_VIEWED": LeadState.PRODUCT_VIEWED,
    "PLAN_SELECTED": LeadState.PLAN_SELECTED,
    "CHECKOUT_STARTED": LeadState.CHECKOUT_STARTED,
    "PAYMENT_PENDING": LeadState.PAYMENT_PENDING,
    "PAYMENT_ABANDONED": LeadState.PAYMENT_ABANDONED,
    "PAYMENT_CONFIRMED": LeadState.PAID,
    "ACCESS_PENDING": LeadState.ACCESS_PENDING,
    "ACCESS_GRANTED": LeadState.CUSTOMER_ACTIVE,
    "ACCESS_EXPIRED": LeadState.EXPIRED_CUSTOMER,
}


def record_lead_event(
    db: Session,
    lead: Lead,
    event_type: str,
    *,
    product_id: str | None = None,
    payload: dict | None = None,
) -> LeadEvent:
    event = LeadEvent(
        lead_id=lead.id,
        event_type=event_type,
        product_id=product_id,
        payload=payload or {},
    )
    db.add(event)
    target = EVENT_TO_STATE.get(event_type)
    if target:
        lead.state = target
    if product_id:
        lead.last_product_id = product_id
    lead.last_event_at = datetime.now(UTC)
    db.add(lead)
    return event
