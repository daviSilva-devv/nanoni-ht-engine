from collections.abc import Mapping

from nanoni.domain.enums import (
    EntitlementStatus,
    JobStatus,
    OrderStatus,
    PaymentStatus,
    PublicationStatus,
)

TRANSITIONS: Mapping[type, dict[str, set[str]]] = {
    OrderStatus: {
        OrderStatus.CREATED: {OrderStatus.CHECKOUT_READY, OrderStatus.CANCELLED},
        OrderStatus.CHECKOUT_READY: {OrderStatus.PAYMENT_PENDING, OrderStatus.CANCELLED},
        OrderStatus.PAYMENT_PENDING: {
            OrderStatus.PAID,
            OrderStatus.EXPIRED,
            OrderStatus.REVIEW_REQUIRED,
        },
        OrderStatus.PAID: {
            OrderStatus.ACCESS_PENDING,
            OrderStatus.REVIEW_REQUIRED,
            OrderStatus.REFUNDED,
        },
        OrderStatus.ACCESS_PENDING: {OrderStatus.FULFILLED, OrderStatus.REVIEW_REQUIRED},
        OrderStatus.FULFILLED: {OrderStatus.REFUNDED, OrderStatus.REVIEW_REQUIRED},
        OrderStatus.EXPIRED: {OrderStatus.PAID, OrderStatus.CANCELLED},
        OrderStatus.REVIEW_REQUIRED: {
            OrderStatus.PAID,
            OrderStatus.ACCESS_PENDING,
            OrderStatus.CANCELLED,
            OrderStatus.REFUNDED,
        },
    },
    PaymentStatus: {
        PaymentStatus.CREATED: {PaymentStatus.PENDING, PaymentStatus.FAILED},
        PaymentStatus.PENDING: {
            PaymentStatus.CONFIRMED,
            PaymentStatus.EXPIRED,
            PaymentStatus.FAILED,
        },
        PaymentStatus.EXPIRED: {PaymentStatus.CONFIRMED},
        PaymentStatus.CONFIRMED: {PaymentStatus.REFUNDED, PaymentStatus.DUPLICATE_REVIEW},
        PaymentStatus.DUPLICATE_REVIEW: {PaymentStatus.CONFIRMED, PaymentStatus.REFUNDED},
    },
    EntitlementStatus: {
        EntitlementStatus.PENDING: {EntitlementStatus.ACTIVE, EntitlementStatus.REVOKED},
        EntitlementStatus.ACTIVE: {
            EntitlementStatus.EXPIRED,
            EntitlementStatus.SUSPENDED,
            EntitlementStatus.REVOKED,
        },
        EntitlementStatus.SUSPENDED: {
            EntitlementStatus.ACTIVE,
            EntitlementStatus.REVOKED,
            EntitlementStatus.EXPIRED,
        },
    },
    PublicationStatus: {
        PublicationStatus.QUEUED: {
            PublicationStatus.SCHEDULED,
            PublicationStatus.PUBLISHING,
            PublicationStatus.CANCELLED,
        },
        PublicationStatus.SCHEDULED: {PublicationStatus.PUBLISHING, PublicationStatus.CANCELLED},
        PublicationStatus.PUBLISHING: {PublicationStatus.PUBLISHED, PublicationStatus.FAILED},
        PublicationStatus.FAILED: {PublicationStatus.QUEUED, PublicationStatus.CANCELLED},
    },
    JobStatus: {
        JobStatus.QUEUED: {JobStatus.RUNNING, JobStatus.CANCELLED, JobStatus.SKIPPED},
        JobStatus.RUNNING: {
            JobStatus.SUCCEEDED,
            JobStatus.FAILED_RETRYABLE,
            JobStatus.FAILED_FINAL,
        },
        JobStatus.FAILED_RETRYABLE: {JobStatus.QUEUED, JobStatus.FAILED_FINAL},
    },
}


def ensure_transition(enum_type: type, current: str, target: str) -> None:
    if current == target:
        return
    allowed = TRANSITIONS.get(enum_type, {}).get(current, set())
    if target not in allowed:
        raise ValueError(f"invalid {enum_type.__name__} transition: {current} -> {target}")
