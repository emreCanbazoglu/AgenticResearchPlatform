from __future__ import annotations

import datetime

import run_paper


class _FrozenDateTime(datetime.datetime):
    frozen_now = datetime.datetime(2024, 1, 1, 14, 17, 30, tzinfo=datetime.timezone.utc)

    @classmethod
    def now(cls, tz=None):
        if tz is None:
            return cls.frozen_now.replace(tzinfo=None)
        return cls.frozen_now.astimezone(tz)


def test_sleep_until_next_boundary_calculates_correctly(monkeypatch):
    sleep_calls: list[int] = []

    monkeypatch.setattr(run_paper.datetime, "datetime", _FrozenDateTime)
    monkeypatch.setattr(run_paper.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    run_paper.sleep_until_next_boundary(30)

    assert sleep_calls == [750]


def test_sleep_called_for_exact_boundary(monkeypatch):
    class _BoundaryDateTime(_FrozenDateTime):
        frozen_now = datetime.datetime(2024, 1, 1, 14, 30, 0, tzinfo=datetime.timezone.utc)

    sleep_calls: list[int] = []

    monkeypatch.setattr(run_paper.datetime, "datetime", _BoundaryDateTime)
    monkeypatch.setattr(run_paper.time, "sleep", lambda seconds: sleep_calls.append(seconds))

    run_paper.sleep_until_next_boundary(30)

    assert sleep_calls == [1800]
