from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import exists, or_, select
from sqlalchemy.orm import Session

from nanoni.domain.enums import (
    ApprovalDecision,
    PackStatus,
    PublicationPlanStatus,
    PublicationStatus,
    Severity,
)
from nanoni.domain.models import (
    Alert,
    Approval,
    ContentPack,
    ContentPackMicroNiche,
    MediaAsset,
    PackItem,
    PublicationJob,
    PublicationPlan,
    PublicationRule,
    ScheduleWindow,
)
from nanoni.domain.services.publishing import enqueue_publication


@dataclass(frozen=True)
class Window:
    start_minute: int
    end_minute: int
    weight: int = 10
    label: str | None = None

    def validate(self) -> None:
        for value in (self.start_minute, self.end_minute):
            if not 0 <= value <= 1439:
                raise ValueError("schedule window minute must be 0..1439")
        if self.start_minute == self.end_minute:
            raise ValueError("schedule window cannot have zero length")
        if self.weight < 1:
            raise ValueError("schedule window weight must be positive")


def _minute_to_datetime(day: date, minute: int, tz=UTC) -> datetime:
    return datetime.combine(day, time(hour=minute // 60, minute=minute % 60), tzinfo=tz)


def random_time_in_window(
    day: date, window: Window, rng: random.Random | None = None, tz=UTC
) -> datetime:
    window.validate()
    chooser = rng or random.Random()
    if window.end_minute > window.start_minute:
        minute = chooser.randrange(window.start_minute, window.end_minute + 1)
        return _minute_to_datetime(day, minute, tz)
    # crosses midnight, e.g. 22:00-02:30. Treat as one continuous range.
    span = (1440 - window.start_minute) + window.end_minute
    offset = chooser.randrange(0, span + 1)
    absolute = window.start_minute + offset
    if absolute < 1440:
        return _minute_to_datetime(day, absolute, tz)
    return _minute_to_datetime(day + timedelta(days=1), absolute - 1440, tz)


def choose_scheduled_times(
    day: date,
    windows: list[Window],
    count: int,
    seed: int | None = None,
    tz=UTC,
    *,
    minimum_spacing_minutes: int = 1,
    occupied: list[datetime] | None = None,
) -> list[datetime]:
    if count <= 0 or not windows:
        return []
    if minimum_spacing_minutes < 1:
        raise ValueError("minimum spacing must be positive")
    rng = random.Random(seed)
    for window in windows:
        window.validate()
    used = [
        value.replace(tzinfo=tz) if value.tzinfo is None else value.astimezone(tz)
        for value in (occupied or [])
    ]
    result: list[datetime] = []
    for _ in range(count):
        eligible: list[tuple[Window, list[datetime]]] = []
        for window in windows:
            candidates = [
                value
                for value in _window_candidates(day, window, tz)
                if all(
                    abs((value - prior).total_seconds()) >= minimum_spacing_minutes * 60
                    for prior in used
                )
            ]
            if candidates:
                eligible.append((window, candidates))
        if not eligible:
            raise ValueError("schedule windows cannot satisfy requested spacing")
        _, candidates = rng.choices(
            eligible, weights=[window.weight for window, _ in eligible], k=1
        )[0]
        value = rng.choice(candidates)
        used.append(value)
        result.append(value)
    return sorted(result)


def _window_candidates(day: date, window: Window, tz=UTC) -> list[datetime]:
    window.validate()
    if window.end_minute > window.start_minute:
        return [
            _minute_to_datetime(day, minute, tz)
            for minute in range(window.start_minute, window.end_minute + 1)
        ]
    return [
        *[
            _minute_to_datetime(day, minute, tz)
            for minute in range(window.start_minute, 1440)
        ],
        *[
            _minute_to_datetime(day + timedelta(days=1), minute, tz)
            for minute in range(0, window.end_minute + 1)
        ],
    ]


def available_packs_for_rule(db: Session, rule: PublicationRule) -> list[ContentPack]:
    has_selected = exists(
        select(PackItem.id).where(
            PackItem.pack_id == ContentPack.id,
            PackItem.selected.is_(True),
        )
    )
    missing_telegram_reference = exists(
        select(PackItem.id)
        .join(MediaAsset, MediaAsset.id == PackItem.asset_id)
        .where(
            PackItem.pack_id == ContentPack.id,
            PackItem.selected.is_(True),
            MediaAsset.telegram_file_id.is_(None),
        )
    )
    already_used_conditions = [
        PublicationJob.pack_id == ContentPack.id,
        PublicationJob.destination_id == rule.destination_id,
        PublicationJob.status != PublicationStatus.CANCELLED,
    ]
    if rule.topic_id:
        already_used_conditions.append(PublicationJob.topic_id == rule.topic_id)
    else:
        already_used_conditions.append(PublicationJob.topic_id.is_(None))
    already_used = exists(select(PublicationJob.id).where(*already_used_conditions))
    matching_target = exists(
        select(Approval.id).where(
            Approval.candidate_id == ContentPack.candidate_id,
            Approval.decision == ApprovalDecision.APPROVED,
            Approval.target == rule.target,
        )
    )
    stmt = select(ContentPack).where(
        ContentPack.approved.is_(True),
        ContentPack.status == PackStatus.READY,
        ContentPack.archived.is_(False),
        has_selected,
        ~missing_telegram_reference,
        ~already_used,
        or_(ContentPack.candidate_id.is_(None), matching_target),
    )
    if rule.microniche_id:
        stmt = stmt.join(
            ContentPackMicroNiche,
            ContentPackMicroNiche.pack_id == ContentPack.id,
        ).where(ContentPackMicroNiche.microniche_id == rule.microniche_id)
    return list(db.scalars(stmt.order_by(ContentPack.created_at, ContentPack.id)))


def stock_days_for_rule(db: Session, rule: PublicationRule) -> tuple[int, float]:
    available = len(available_packs_for_rule(db, rule))
    return available, available / max(1, rule.posts_per_day)


def _open_alert(
    db: Session,
    *,
    rule: PublicationRule,
    code: str,
    title: str,
    message: str,
) -> Alert:
    alert = db.scalar(
        select(Alert).where(
            Alert.code == code,
            Alert.entity_type == "PublicationRule",
            Alert.entity_id == rule.id,
            Alert.resolved_at.is_(None),
        )
    )
    if alert is None:
        alert = Alert(
            severity=Severity.WARNING,
            code=code,
            title=title,
            message=message,
            entity_type="PublicationRule",
            entity_id=rule.id,
        )
        db.add(alert)
        db.flush()
    return alert


def _rule_seed(seed: int | None, rule_id: str, day: date) -> int:
    digest = hashlib.sha256(f"{seed}:{rule_id}:{day.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def plan_publication_day(
    db: Session,
    *,
    day: date,
    seed: int | None = None,
    tz=UTC,
) -> list[PublicationPlan]:
    rules = list(
        db.scalars(
            select(PublicationRule)
            .where(PublicationRule.active.is_(True))
            .order_by(PublicationRule.id)
        )
    )
    all_plans = list(
        db.scalars(
            select(PublicationPlan)
            .where(PublicationPlan.planning_date == day)
            .order_by(PublicationPlan.rule_id, PublicationPlan.slot_index)
        )
    )
    occupied = [
        plan.scheduled_for
        for plan in all_plans
        if plan.scheduled_for and plan.status == PublicationPlanStatus.PLANNED
    ]
    plans_by_rule = {
        rule.id: [plan for plan in all_plans if plan.rule_id == rule.id] for rule in rules
    }

    for rule in rules:
        existing = plans_by_rule[rule.id]
        missing_count = max(0, rule.posts_per_day - len(existing))
        if not missing_count:
            continue
        rows = list(
            db.scalars(
                select(ScheduleWindow)
                .where(ScheduleWindow.publication_rule_id == rule.id)
                .order_by(ScheduleWindow.id)
            )
        )
        windows = [Window(row.start_minute, row.end_minute, row.weight, row.label) for row in rows]
        raw_spacing = (rule.config or {}).get("minimum_spacing_minutes", 15)
        try:
            if not windows:
                raise ValueError("publication rule has no schedule windows")
            spacing = int(raw_spacing)
            times = choose_scheduled_times(
                day,
                windows,
                missing_count,
                seed=_rule_seed(seed, rule.id, day),
                tz=tz,
                minimum_spacing_minutes=spacing,
                occupied=occupied,
            )
        except (TypeError, ValueError) as exc:
            _open_alert(
                db,
                rule=rule,
                code="PUBLICATION_RULE_INVALID_SCHEDULE",
                title="Publication rule cannot be scheduled",
                message=str(exc),
            )
            for offset in range(missing_count):
                plan = PublicationPlan(
                    rule_id=rule.id,
                    planning_date=day,
                    slot_index=len(existing) + offset,
                    status=PublicationPlanStatus.SKIPPED_CONFIGURATION,
                    reason=str(exc),
                )
                db.add(plan)
                all_plans.append(plan)
            db.flush()
            continue

        packs = available_packs_for_rule(db, rule)
        for offset, scheduled_for in enumerate(times):
            slot_index = len(existing) + offset
            if packs:
                pack = packs.pop(0)
                publication_job, _ = enqueue_publication(
                    db,
                    pack_id=pack.id,
                    destination_id=rule.destination_id,
                    scheduled_for=scheduled_for,
                    topic_id=rule.topic_id,
                    rule_id=rule.id,
                )
                plan = PublicationPlan(
                    rule_id=rule.id,
                    planning_date=day,
                    slot_index=slot_index,
                    scheduled_for=scheduled_for,
                    status=PublicationPlanStatus.PLANNED,
                    publication_job_id=publication_job.id,
                )
            else:
                plan = PublicationPlan(
                    rule_id=rule.id,
                    planning_date=day,
                    slot_index=slot_index,
                    scheduled_for=scheduled_for,
                    status=PublicationPlanStatus.SKIPPED_NO_CONTENT,
                    reason="no unpublished approved pack is available",
                )
                _open_alert(
                    db,
                    rule=rule,
                    code="PUBLICATION_QUEUE_EMPTY",
                    title="Publication queue is empty",
                    message="No unpublished approved pack is available for this rule.",
                )
            db.add(plan)
            all_plans.append(plan)
            occupied.append(scheduled_for)
        db.flush()
    return sorted(all_plans, key=lambda plan: (plan.rule_id, plan.slot_index))
