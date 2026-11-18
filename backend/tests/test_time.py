from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.shared import time as vn_time


def _patch_demo_now(monkeypatch: pytest.MonkeyPatch, value: datetime | None) -> None:
    monkeypatch.setattr(vn_time, "get_settings", lambda: SimpleNamespace(demo_now=value))


def test_now_uses_demo_now(monkeypatch: pytest.MonkeyPatch) -> None:
    demo = datetime(2026, 11, 20, 9, 0, tzinfo=timezone(timedelta(hours=7)))
    _patch_demo_now(monkeypatch, demo)
    result = vn_time.now()
    assert result == demo
    assert result.utcoffset() == timedelta(hours=7)


def test_now_converts_demo_now_from_other_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_demo_now(monkeypatch, datetime(2026, 11, 20, 2, 0, tzinfo=UTC))
    result = vn_time.now()
    assert (result.hour, result.utcoffset()) == (9, timedelta(hours=7))


def test_now_without_demo_now_is_system_time(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_demo_now(monkeypatch, None)
    result = vn_time.now()
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(hours=7)
    assert abs(result - datetime.now(UTC)) < timedelta(seconds=5)


def test_db_round_trip() -> None:
    aware = datetime(2026, 11, 20, 2, 0, tzinfo=UTC)
    naive = vn_time.to_db(aware)
    assert naive.tzinfo is None and naive.hour == 9
    assert vn_time.from_db(naive) == aware
    assert vn_time.from_db(None) is None


def test_to_db_rejects_naive() -> None:
    with pytest.raises(ValueError):
        vn_time.to_db(datetime(2026, 1, 1))
