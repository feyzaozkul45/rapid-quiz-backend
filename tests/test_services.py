from datetime import UTC, datetime, timedelta

import pytest

from apps.quiz_sessions import services

T0 = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, True),
        (1, True),
        (5, True),
        (5.999, True),
        (6, True),  # 1 sn tolerans dahil, sınır kabul
        (6.001, False),
        (7, False),
        (60, False),
    ],
)
def test_is_within_time_boundaries(seconds, expected):
    assert services.is_within_time(T0, T0 + timedelta(seconds=seconds)) is expected


@pytest.mark.parametrize(("seconds", "expected"), [(0, False), (5, False), (6, False), (6.5, True)])
def test_has_timed_out(seconds, expected):
    assert services.has_timed_out(T0, T0 + timedelta(seconds=seconds)) is expected


@pytest.mark.parametrize(
    ("seconds", "expected"), [(0, 5.0), (2, 3.0), (5, 0.0), (6, 0.0), (-3, 5.0)]
)
def test_remaining_seconds_is_clamped(seconds, expected):
    assert services.remaining_seconds(T0, T0 + timedelta(seconds=seconds)) == expected


def test_points_require_correct_and_in_time():
    assert services.points_for_answer(True, True) == 100
    assert services.points_for_answer(True, False) == 0
    assert services.points_for_answer(False, True) == 0
    assert services.points_for_answer(False, False) == 0


def test_score_is_100_per_correct_and_speed_independent():
    assert services.calculate_score(0) == 0
    assert services.calculate_score(7) == 700
    assert services.calculate_score(20) == services.MAX_SCORE == 2000


def test_inactivity_limit_is_ten_minutes():
    assert services.is_inactive(T0, T0 + timedelta(minutes=10)) is False
    assert services.is_inactive(T0, T0 + timedelta(minutes=10, seconds=1)) is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Ayşe  ", "Ayşe"),
        ("Ali    Veli", "Ali Veli"),
        ("Ali\t\nVeli", "Ali Veli"),
        ("Ali Veli", "Ali Veli"),
        ("Gül", "Gül"),  # NFC: u + birleşik trema -> ü
    ],
)
def test_normalize_player_name(raw, expected):
    assert services.normalize_player_name(raw) == expected


@pytest.mark.parametrize(
    "name", ["Ay", "Ayşe", "Çağlar Öz", "Ali-Veli", "Şebnem 99", "ğüşiöçĞÜŞİÖÇ", "a" * 20, "日本語"]
)
def test_valid_player_names(name):
    assert services.validate_player_name(name) is None


@pytest.mark.parametrize(
    "name",
    ["", "A", "a" * 21, "Ayşe!", "Ali_Veli", "😀😀", "<b>ali</b>", "--", "- -", "a​b", "x@y"],
)
def test_invalid_player_names(name):
    assert services.validate_player_name(name) is not None


def test_name_window_is_thirty_minutes():
    assert services.is_name_window_open(T0, T0 + timedelta(minutes=30)) is True
    assert services.is_name_window_open(T0, T0 + timedelta(minutes=30, seconds=1)) is False
