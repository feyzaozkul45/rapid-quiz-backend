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


# ---- hızlı cevap, soru seçimi, seçenek karıştırma ------------------------------------


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, True), (0.1, True), (0.299, True), (0.3, False), (0.301, False), (1, False), (5, False)],
)
def test_is_too_fast_boundaries(seconds, expected):
    assert services.is_too_fast(T0, T0 + timedelta(seconds=seconds)) is expected


def test_too_fast_answer_gets_no_points():
    assert services.points_for_answer(True, True, too_fast=True) == 0
    assert services.points_for_answer(True, True, too_fast=False) == 100


def test_choose_questions_prefers_questions_not_recently_played():
    available = list(range(1, 41))
    recent = list(range(1, 21))
    for _ in range(20):
        chosen = services.choose_questions(available, recent)
        assert len(chosen) == len(set(chosen)) == 20
        assert set(chosen) == set(range(21, 41))  # tam 20 taze soru var: hepsi seçilir


def test_choose_questions_fills_remainder_from_oldest_played():
    available = list(range(1, 41))
    recent = list(range(1, 36))  # 35 oynanmış (1 en eski), taze: 36-40 (5 soru)
    chosen = services.choose_questions(available, recent)
    assert len(chosen) == 20
    assert set(range(36, 41)) <= set(chosen)  # taze olanların hepsi var
    assert set(chosen) - set(range(36, 41)) == set(range(1, 16))  # kalan 15: en eski 15


def test_choose_questions_uses_all_when_everything_was_played():
    available = list(range(1, 41))
    chosen = services.choose_questions(available, list(range(1, 41)))
    assert set(chosen) == set(range(1, 21))  # en eski 20


def test_choose_questions_ignores_unknown_and_duplicate_ids():
    available = list(range(1, 31))
    recent = [999, 5, 5, 6, -1, 5]
    chosen = services.choose_questions(available, recent)
    assert len(chosen) == 20
    assert not {5, 6} & set(chosen)  # 10+ taze soru var: oynananlar dışarıda kalır
    assert set(chosen) <= set(available)


def test_choose_questions_with_exact_pool_returns_all_shuffled():
    chosen = services.choose_questions(range(1, 21), [])
    assert sorted(chosen) == list(range(1, 21))


class _Choice:
    def __init__(self, pk):
        self.pk = pk


def test_shuffled_choices_is_stable_per_session_and_question():
    choices = [_Choice(pk) for pk in (11, 12, 13, 14)]
    first = [c.pk for c in services.shuffled_choices("s1", 7, choices)]
    again = [c.pk for c in services.shuffled_choices("s1", 7, list(reversed(choices)))]
    assert first == again
    assert sorted(first) == [11, 12, 13, 14]


def test_shuffled_choices_differs_between_sessions():
    choices = [_Choice(pk) for pk in (11, 12, 13, 14)]
    orders = {
        tuple(c.pk for c in services.shuffled_choices(f"oturum-{i}", 7, choices)) for i in range(30)
    }
    assert len(orders) > 5  # 24 olası sıradan çoğu görülür
