from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from nanoni.core.db import get_db
from nanoni.core.security import require_admin
from nanoni.domain.models import (
    ContentPack,
    PublicationJob,
    PublicationRule,
    ScheduleWindow,
    TelegramDestination,
    Topic,
)
from nanoni.domain.services.scheduler import Window, choose_scheduled_times

router = APIRouter(
    prefix="/publication", tags=["publication"], dependencies=[Depends(require_admin)]
)


@router.post("/rules")
def create_rule(
    destination_id: str,
    target: str,
    posts_per_day: int = 1,
    topic_id: str | None = None,
    microniche_id: str | None = None,
    db: Session = Depends(get_db),
):
    if not db.get(TelegramDestination, destination_id):
        raise HTTPException(404, "destination not found")
    if topic_id and not db.get(Topic, topic_id):
        raise HTTPException(404, "topic not found")
    if posts_per_day < 1:
        raise HTTPException(422, "posts_per_day must be >= 1")
    rule = PublicationRule(
        destination_id=destination_id,
        target=target,
        posts_per_day=posts_per_day,
        topic_id=topic_id,
        microniche_id=microniche_id,
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {"id": rule.id, "target": rule.target, "posts_per_day": rule.posts_per_day}


@router.post("/rules/{rule_id}/windows")
def create_window(
    rule_id: str,
    start_minute: int,
    end_minute: int,
    weight: int = 10,
    label: str | None = None,
    db: Session = Depends(get_db),
):
    if not db.get(PublicationRule, rule_id):
        raise HTTPException(404, "rule not found")
    try:
        Window(
            start_minute=start_minute, end_minute=end_minute, weight=weight, label=label
        ).validate()
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    item = ScheduleWindow(
        publication_rule_id=rule_id,
        start_minute=start_minute,
        end_minute=end_minute,
        weight=weight,
        label=label,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id}


@router.get("/rules/{rule_id}/preview")
def preview_schedule(
    rule_id: str, day: date, seed: int | None = None, db: Session = Depends(get_db)
):
    rule = db.get(PublicationRule, rule_id)
    if not rule:
        raise HTTPException(404, "rule not found")
    rows = list(
        db.scalars(select(ScheduleWindow).where(ScheduleWindow.publication_rule_id == rule_id))
    )
    windows = [Window(r.start_minute, r.end_minute, r.weight, r.label) for r in rows]
    values = choose_scheduled_times(day, windows, rule.posts_per_day, seed=seed)
    return {"rule_id": rule_id, "times": values}


@router.post("/queue")
def queue_pack(
    pack_id: str,
    destination_id: str,
    scheduled_for: datetime | None = None,
    topic_id: str | None = None,
    rule_id: str | None = None,
    db: Session = Depends(get_db),
):
    if not db.get(ContentPack, pack_id):
        raise HTTPException(404, "pack not found")
    if not db.get(TelegramDestination, destination_id):
        raise HTTPException(404, "destination not found")
    if topic_id and not db.get(Topic, topic_id):
        raise HTTPException(404, "topic not found")
    job = PublicationJob(
        pack_id=pack_id,
        destination_id=destination_id,
        topic_id=topic_id,
        rule_id=rule_id,
        scheduled_for=scheduled_for or datetime.now(UTC),
        status="SCHEDULED",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return {"id": job.id, "status": job.status, "scheduled_for": job.scheduled_for}
