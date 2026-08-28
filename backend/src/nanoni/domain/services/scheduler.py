from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta


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
    day: date, windows: list[Window], count: int, seed: int | None = None, tz=UTC
) -> list[datetime]:
    if count <= 0 or not windows:
        return []
    rng = random.Random(seed)
    for window in windows:
        window.validate()
    selected = rng.choices(windows, weights=[w.weight for w in windows], k=count)
    values = [random_time_in_window(day, w, rng=rng, tz=tz) for w in selected]
    # Avoid same-minute duplicates where possible.
    seen: set[datetime] = set()
    result: list[datetime] = []
    for value in sorted(values):
        while value in seen:
            value += timedelta(minutes=1)
        seen.add(value)
        result.append(value)
    return result
