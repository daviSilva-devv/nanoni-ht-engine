from datetime import date

from nanoni.domain.services.scheduler import Window, choose_scheduled_times


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


def test_window_validation():
    try:
        Window(100, 100).validate()
    except ValueError as exc:
        assert "zero length" in str(exc)
    else:
        raise AssertionError("expected validation error")
