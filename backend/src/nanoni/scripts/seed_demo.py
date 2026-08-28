from decimal import Decimal

from sqlalchemy import inspect, select

from nanoni.core.db import SessionLocal, engine
from nanoni.domain.models import (
    Community,
    CommunityVersion,
    CommunityVersionMicroNiche,
    CopySlot,
    CopyVariant,
    MicroNiche,
    Niche,
    PricePlan,
    Product,
    Source,
    TelegramDestination,
    Topic,
)


def run() -> None:
    inspector = inspect(engine)
    required_tables = {"alembic_version", "niches"}
    missing_tables = sorted(required_tables.difference(inspector.get_table_names()))
    if missing_tables:
        missing = ", ".join(missing_tables)
        raise RuntimeError(
            f"database schema is not initialized (missing: {missing}); "
            "run 'alembic upgrade head' before seeding"
        )
    db = SessionLocal()
    try:
        existing = db.scalar(select(Niche).where(Niche.slug == "demo"))
        if existing:
            print("Demo data already exists.")
            return
        niche = Niche(name="Demo Community", slug="demo", description="Local development fixture")
        db.add(niche)
        db.flush()
        micros = []
        for index, name in enumerate(
            ["Micro A", "Micro B", "Micro C", "Micro D", "Micro E", "Micro F"], 1
        ):
            micro = MicroNiche(
                niche_id=niche.id, name=name, slug=f"micro-{index}", sort_order=index
            )
            db.add(micro)
            db.flush()
            micros.append(micro)
        community = Community(niche_id=niche.id, name="Demo VIP", slug="demo-vip")
        db.add(community)
        db.flush()
        version = CommunityVersion(
            community_id=community.id,
            version=1,
            name="Demo VIP V1",
            promise_snapshot={
                "microniches": [m.name for m in micros],
                "lifetime_scope": "this-version",
            },
        )
        db.add(version)
        db.flush()
        for micro in micros:
            db.add(
                CommunityVersionMicroNiche(community_version_id=version.id, microniche_id=micro.id)
            )
        product = Product(community_version_id=version.id, name="Demo VIP", slug="demo-vip-v1")
        db.add(product)
        db.flush()
        db.add_all(
            [
                PricePlan(
                    product_id=product.id,
                    kind="WEEKLY",
                    amount=Decimal("14.90"),
                    duration_days=7,
                    sort_order=10,
                ),
                PricePlan(
                    product_id=product.id,
                    kind="MONTHLY",
                    amount=Decimal("29.90"),
                    duration_days=30,
                    sort_order=20,
                ),
                PricePlan(
                    product_id=product.id,
                    kind="LIFETIME",
                    amount=Decimal("37.90"),
                    lifetime=True,
                    featured=True,
                    sort_order=30,
                ),
            ]
        )
        free = TelegramDestination(
            community_id=community.id,
            name="Demo FREE",
            destination_type="FREE_CHANNEL",
            telegram_chat_id="demo-free",
        )
        vip = TelegramDestination(
            community_id=community.id,
            name="Demo VIP Forum",
            destination_type="VIP_FORUM",
            telegram_chat_id="demo-vip",
        )
        db.add_all([free, vip])
        db.flush()
        db.add(
            Topic(
                destination_id=vip.id, name="Pedidos/Papo", role="REQUESTS", message_thread_id=100
            )
        )
        for index, micro in enumerate(micros, 1):
            db.add(
                Topic(
                    destination_id=vip.id,
                    microniche_id=micro.id,
                    name=micro.name,
                    role="CONTENT",
                    message_thread_id=100 + index,
                )
            )
        db.add_all(
            [
                Source(name="Erome Public Albums", adapter="erome"),
                Source(name="Telegram Helper", adapter="telegram-helper"),
                Source(name="Manual Inbox", adapter="manual"),
            ]
        )
        defaults = {
            "BOT_HERO": "🔞 Acesso fechado. Escolha como quer entrar.",
            "FREE_CTA": "👀 Prévia aqui. O completo fica no VIP.",
            "VIP_CTA": "🔥 Libere o acesso completo.",
            "CHECKOUT_RECOVERY": "⚠️ Seu acesso ainda está pendente.",
            "POST_PURCHASE_UPSELL": "😈 Quer liberar também a próxima comunidade?",
        }
        for key, text in defaults.items():
            slot = CopySlot(key=key, description=f"Default {key}")
            db.add(slot)
            db.flush()
            db.add(CopyVariant(slot_id=slot.id, text=text, weight=10))
        db.commit()
        print("Demo catalog created.")
        print(f"Product: {product.id}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
