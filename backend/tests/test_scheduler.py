from datetime import UTC, date, datetime

from sqlalchemy import func, select

from nanoni.domain.enums import (
    AssetStatus,
    DestinationStatus,
    DestinationType,
    PackStatus,
    PublicationPlanStatus,
    PublicationTarget,
)
from nanoni.domain.models import (
    Alert,
    ContentPack,
    ContentPackMicroNiche,
    Job,
    MediaAsset,
    MicroNiche,
    Niche,
    PackItem,
    PublicationJob,
    PublicationRule,
    ScheduleWindow,
    TelegramDestination,
    Topic,
)
from nanoni.domain.services.scheduler import (
    Window,
    choose_scheduled_times,
    plan_publication_day,
    stock_days_for_rule,
)


def test_random_schedule_respects_weighted_windows():
    windows = [
        Window(600, 720, weight=1, label="day"),
        Window(1320, 120, weight=9, label="night-cross-midnight"),
    ]
    values = choose_scheduled_times(date(2026, 8, 28), windows, 20, seed=42)
    assert len(values) == 20
    assert values == sorted(values)
    assert len(set(values)) == 20
    assert any(v.date() == date(2026, 8, 29) for v in values)


def test_schedule_never_shifts_outside_windows_and_respects_spacing():
    day = date(2026, 9, 7)
    windows = [Window(1200, 1210), Window(1380, 30, weight=3)]
    values = choose_scheduled_times(
        day,
        windows,
        8,
        seed=7,
        minimum_spacing_minutes=3,
    )
    valid = {
        *[
            datetime(2026, 9, 7, 20, minute, tzinfo=UTC)
            for minute in range(11)
        ],
        *[
            datetime(2026, 9, 7, 23, minute, tzinfo=UTC)
            for minute in range(60)
        ],
        *[
            datetime(2026, 9, 8, 0, minute, tzinfo=UTC)
            for minute in range(31)
        ],
    }
    assert all(value in valid for value in values)
    assert all(
        (right - left).total_seconds() >= 180
        for left, right in zip(values, values[1:], strict=False)
    )


def test_window_validation():
    try:
        Window(100, 100).validate()
    except ValueError as exc:
        assert "zero length" in str(exc)
    else:
        raise AssertionError("expected validation error")


def _scheduler_catalog(db):
    niche = Niche(name="Niche", slug="niche")
    destination = TelegramDestination(
        name="VIP",
        destination_type=DestinationType.VIP_FORUM,
        telegram_chat_id="-100scheduler",
        status=DestinationStatus.ACTIVE,
    )
    db.add_all([niche, destination])
    db.flush()
    microniches = [
        MicroNiche(niche_id=niche.id, name=f"Micro {index}", slug=f"micro-{index}")
        for index in range(2)
    ]
    db.add_all(microniches)
    db.flush()
    rules = []
    for index, microniche in enumerate(microniches):
        topic = Topic(
            destination_id=destination.id,
            microniche_id=microniche.id,
            name=f"Topic {index}",
            message_thread_id=100 + index,
        )
        db.add(topic)
        db.flush()
        rule = PublicationRule(
            destination_id=destination.id,
            topic_id=topic.id,
            microniche_id=microniche.id,
            target=PublicationTarget.VIP,
            posts_per_day=2,
            config={"minimum_spacing_minutes": 10},
        )
        db.add(rule)
        db.flush()
        db.add(
            ScheduleWindow(
                publication_rule_id=rule.id,
                start_minute=1200 + index * 60,
                end_minute=1260 + index * 60,
                weight=10,
            )
        )
        rules.append(rule)
        for pack_index in range(2):
            pack = ContentPack(
                title=f"Pack {index}-{pack_index}",
                approved=True,
                status=PackStatus.READY,
            )
            asset = MediaAsset(
                media_type="IMAGE",
                telegram_file_id=f"file-{index}-{pack_index}",
                status=AssetStatus.VAULTED,
            )
            db.add_all([pack, asset])
            db.flush()
            db.add_all(
                [
                    ContentPackMicroNiche(pack_id=pack.id, microniche_id=microniche.id),
                    PackItem(
                        pack_id=pack.id,
                        asset_id=asset.id,
                        position=1,
                        selected=True,
                    ),
                ]
            )
    db.flush()
    return destination, rules


def test_persisted_24h_plan_has_no_duplicates_or_out_of_window_jobs(db):
    _, rules = _scheduler_catalog(db)
    day = date(2026, 9, 8)
    plans = plan_publication_day(db, day=day, seed=42)
    planned = [plan for plan in plans if plan.status == PublicationPlanStatus.PLANNED]

    assert len(planned) == 4
    assert len({plan.scheduled_for for plan in planned}) == 4
    ordered = sorted(plan.scheduled_for for plan in planned)
    assert all(
        (right - left).total_seconds() >= 600
        for left, right in zip(ordered, ordered[1:], strict=False)
    )
    by_rule = {rule.id: rule for rule in rules}
    for plan in planned:
        rule = by_rule[plan.rule_id]
        window = db.scalar(
            select(ScheduleWindow).where(ScheduleWindow.publication_rule_id == rule.id)
        )
        minute = plan.scheduled_for.hour * 60 + plan.scheduled_for.minute
        assert window.start_minute <= minute <= window.end_minute
        publication_job = db.get(PublicationJob, plan.publication_job_id)
        assert publication_job
        assert publication_job.scheduled_for.replace(tzinfo=UTC) == plan.scheduled_for

    repeated = plan_publication_day(db, day=day, seed=999)
    assert [plan.id for plan in repeated] == [plan.id for plan in plans]
    assert db.scalar(select(func.count(PublicationJob.id))) == 4
    assert db.scalar(select(func.count(Job.id))) == 4
    assert all(stock_days_for_rule(db, rule) == (0, 0.0) for rule in rules)


def test_empty_inventory_is_persisted_as_skipped_and_alerted_once(db):
    destination = TelegramDestination(
        name="FREE",
        destination_type=DestinationType.FREE_CHANNEL,
        telegram_chat_id="-100empty",
        status=DestinationStatus.ACTIVE,
    )
    db.add(destination)
    db.flush()
    rule = PublicationRule(
        destination_id=destination.id,
        target=PublicationTarget.FREE,
        posts_per_day=2,
        config={"minimum_spacing_minutes": 5},
    )
    db.add(rule)
    db.flush()
    db.add(ScheduleWindow(publication_rule_id=rule.id, start_minute=600, end_minute=660))
    db.flush()

    first = plan_publication_day(db, day=date(2026, 9, 8), seed=1)
    second = plan_publication_day(db, day=date(2026, 9, 8), seed=2)
    assert [plan.id for plan in second] == [plan.id for plan in first]
    assert len(first) == 2
    assert all(plan.status == PublicationPlanStatus.SKIPPED_NO_CONTENT for plan in first)
    assert db.scalar(
        select(func.count(Alert.id)).where(Alert.code == "PUBLICATION_QUEUE_EMPTY")
    ) == 1
    assert db.scalar(select(func.count(PublicationJob.id))) == 0


def test_planner_and_stock_endpoints_require_admin(client, db, admin_headers):
    _, rules = _scheduler_catalog(db)
    day = "2026-09-08"
    assert client.post("/api/v1/publication/plan", params={"day": day}).status_code == 401
    planned = client.post(
        "/api/v1/publication/plan",
        params={"day": day, "seed": 42},
        headers=admin_headers,
    )
    assert planned.status_code == 200, planned.text
    assert len(planned.json()["slots"]) == 4
    stock = client.get(
        f"/api/v1/publication/rules/{rules[0].id}/stock",
        headers=admin_headers,
    )
    assert stock.status_code == 200
    assert stock.json()["estimated_days"] == 0.0
