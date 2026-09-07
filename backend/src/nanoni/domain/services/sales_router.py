from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.domain.enums import DestinationStatus, DestinationType
from nanoni.domain.models import (
    Community,
    CommunityVersion,
    Customer,
    Lead,
    PricePlan,
    Product,
    TelegramDestination,
)
from nanoni.domain.schemas import (
    SalesButton,
    SalesCheckoutChoice,
    SalesPlanChoice,
    SalesProductChoice,
    SalesRouterView,
)
from nanoni.domain.services.commerce import get_or_create_customer
from nanoni.domain.services.copy_engine import choose_copy
from nanoni.domain.services.sales import record_lead_event


class AgeConfirmationRequired(RuntimeError):
    pass


def _lead_for_customer(db: Session, customer: Customer) -> Lead:
    lead = db.scalar(select(Lead).where(Lead.customer_id == customer.id))
    if not lead:
        raise RuntimeError("customer is missing lead")
    return lead


def _customer_and_lead(
    db: Session,
    *,
    telegram_user_id: str,
    username: str | None = None,
    display_name: str | None = None,
) -> tuple[Customer, Lead]:
    customer = get_or_create_customer(
        db,
        telegram_user_id=telegram_user_id,
        username=username,
        display_name=display_name,
    )
    return customer, _lead_for_customer(db, customer)


def _copy(db: Session, key: str, fallback: str, *, product_id: str | None = None) -> str:
    variant = choose_copy(db, key, product_id=product_id)
    return variant.text if variant else fallback


def _hero_view(db: Session, lead: Lead) -> SalesRouterView:
    hero = choose_copy(db, "BOT_HERO")
    return SalesRouterView(
        stage="HERO",
        lead_id=lead.id,
        copy_text=hero.text if hero else "Escolha como deseja continuar.",
        media_asset_id=hero.media_asset_id if hero else None,
        buttons=[
            SalesButton(label=_copy(db, "VIP_CTA", "Quero VIP"), action="VIP"),
            SalesButton(label=_copy(db, "FREE_CTA", "Ver FREE"), action="FREE"),
        ],
    )


def start_sales_router(
    db: Session,
    *,
    telegram_user_id: str,
    username: str | None = None,
    display_name: str | None = None,
) -> SalesRouterView:
    customer, lead = _customer_and_lead(
        db,
        telegram_user_id=telegram_user_id,
        username=username,
        display_name=display_name,
    )
    if customer.age_confirmed_at:
        return _hero_view(db, lead)
    return SalesRouterView(
        stage="AGE_GATE",
        lead_id=lead.id,
        copy_text="Confirme que você tem 18 anos ou mais.",
        buttons=[SalesButton(label="Tenho 18 anos ou mais", action="CONFIRM_AGE")],
    )


def _active_products(db: Session) -> list[Product]:
    return list(
        db.scalars(
            select(Product)
            .join(CommunityVersion, CommunityVersion.id == Product.community_version_id)
            .join(Community, Community.id == CommunityVersion.community_id)
            .where(
                Product.active.is_(True),
                CommunityVersion.active_for_sale.is_(True),
                Community.active.is_(True),
            )
            .order_by(Product.name, Product.id)
        )
    )


def _get_active_product(db: Session, product_id: str) -> Product:
    product = db.scalar(
        select(Product)
        .join(CommunityVersion, CommunityVersion.id == Product.community_version_id)
        .join(Community, Community.id == CommunityVersion.community_id)
        .where(
            Product.id == product_id,
            Product.active.is_(True),
            CommunityVersion.active_for_sale.is_(True),
            Community.active.is_(True),
        )
    )
    if not product:
        raise ValueError("product not found or inactive")
    return product


def _plan_selection(db: Session, lead: Lead, product: Product) -> SalesRouterView:
    plans = list(
        db.scalars(
            select(PricePlan)
            .where(PricePlan.product_id == product.id, PricePlan.active.is_(True))
            .order_by(PricePlan.featured.desc(), PricePlan.sort_order, PricePlan.amount, PricePlan.id)
        )
    )
    if not plans:
        raise ValueError("product has no active price plans")
    return SalesRouterView(
        stage="PLAN_SELECTION",
        lead_id=lead.id,
        copy_text=product.description or product.name,
        product_id=product.id,
        plans=[
            SalesPlanChoice(
                id=plan.id,
                kind=plan.kind,
                amount=plan.amount,
                currency=plan.currency,
                duration_days=plan.duration_days,
                lifetime=plan.lifetime,
                featured=plan.featured,
            )
            for plan in plans
        ],
        buttons=[
            SalesButton(
                label=f"{plan.kind} — {plan.currency} {plan.amount}",
                action="PLAN",
                product_id=product.id,
                price_plan_id=plan.id,
            )
            for plan in plans
        ],
    )


def _free_destination_url(db: Session) -> str:
    destination = db.scalar(
        select(TelegramDestination)
        .where(
            TelegramDestination.destination_type == DestinationType.FREE_CHANNEL,
            TelegramDestination.status == DestinationStatus.ACTIVE,
        )
        .order_by(TelegramDestination.created_at, TelegramDestination.id)
    )
    if not destination:
        raise ValueError("active FREE destination not configured")
    invite_url = destination.metadata_json.get("invite_url")
    if invite_url:
        return str(invite_url)
    if destination.username:
        return f"https://t.me/{destination.username.lstrip('@')}"
    raise ValueError("FREE destination requires username or metadata invite_url")


def route_sales_action(
    db: Session,
    *,
    telegram_user_id: str,
    action: str,
    username: str | None = None,
    display_name: str | None = None,
    product_id: str | None = None,
    price_plan_id: str | None = None,
) -> SalesRouterView:
    customer, lead = _customer_and_lead(
        db,
        telegram_user_id=telegram_user_id,
        username=username,
        display_name=display_name,
    )
    if action == "CONFIRM_AGE":
        if not customer.age_confirmed_at:
            customer.age_confirmed_at = datetime.now(UTC)
            db.add(customer)
            record_lead_event(db, lead, "AGE_CONFIRMED")
        return _hero_view(db, lead)

    if not customer.age_confirmed_at:
        raise AgeConfirmationRequired("age confirmation required")

    if action == "VIP":
        record_lead_event(db, lead, "INTENT_VIP")
        products = _active_products(db)
        if not products:
            raise ValueError("no active products configured")
        if len(products) == 1:
            product = products[0]
            record_lead_event(db, lead, "PRODUCT_VIEWED", product_id=product.id)
            return _plan_selection(db, lead, product)
        return SalesRouterView(
            stage="PRODUCT_SELECTION",
            lead_id=lead.id,
            copy_text="Escolha seu acesso.",
            products=[
                SalesProductChoice(id=item.id, name=item.name, description=item.description)
                for item in products
            ],
            buttons=[
                SalesButton(label=item.name, action="PRODUCT", product_id=item.id)
                for item in products
            ],
        )

    if action == "FREE":
        record_lead_event(db, lead, "INTENT_FREE")
        return SalesRouterView(
            stage="FREE_ROUTE",
            lead_id=lead.id,
            copy_text=_copy(db, "FREE_CTA", "Acesse o conteúdo FREE."),
            destination_url=_free_destination_url(db),
        )

    if action == "PRODUCT":
        if not product_id:
            raise ValueError("product_id is required")
        product = _get_active_product(db, product_id)
        record_lead_event(db, lead, "PRODUCT_VIEWED", product_id=product.id)
        return _plan_selection(db, lead, product)

    if action == "PLAN":
        if not product_id or not price_plan_id:
            raise ValueError("product_id and price_plan_id are required")
        product = _get_active_product(db, product_id)
        plan = db.scalar(
            select(PricePlan).where(
                PricePlan.id == price_plan_id,
                PricePlan.product_id == product.id,
                PricePlan.active.is_(True),
            )
        )
        if not plan:
            raise ValueError("price plan not found for product")
        record_lead_event(
            db,
            lead,
            "PLAN_SELECTED",
            product_id=product.id,
            payload={"price_plan_id": plan.id},
        )
        return SalesRouterView(
            stage="CHECKOUT_CHOICE",
            lead_id=lead.id,
            product_id=product.id,
            copy_text="Plano selecionado. Continue para o checkout.",
            checkout=SalesCheckoutChoice(
                price_plan_id=plan.id,
                order_endpoint="/api/v1/commerce/orders",
            ),
        )

    raise ValueError("unsupported sales action")
