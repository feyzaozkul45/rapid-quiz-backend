from datetime import UTC, datetime, timedelta

import pytest

from apps.quiz_sessions.models import QuizSession

from .factories import CategoryFactory

pytestmark = pytest.mark.django_db

T0 = datetime(2026, 10, 1, 10, 0, 0, tzinfo=UTC)
URL = "/api/v1/leaderboard/"


def make_session(category, score, minute=0, name="Oyuncu", status="completed", **kwargs):
    return QuizSession.objects.create(
        category=category,
        status=status,
        score=score,
        correct_count=score // 100,
        player_name=name,
        finished_at=T0 + timedelta(minutes=minute),
        **kwargs,
    )


@pytest.fixture
def cat():
    return CategoryFactory(slug="fizik")


def test_orders_by_score_then_earlier_finish(api, cat):
    make_session(cat, 1000, minute=5, name="C")
    make_session(cat, 1900, minute=9, name="A")
    make_session(cat, 1000, minute=1, name="B")  # eşit puan, daha erken bitirdi
    body = api.get(URL, {"category": "fizik"}).json()
    assert body["category"] == "fizik"
    assert [(e["rank"], e["player_name"]) for e in body["entries"]] == [
        (1, "A"),
        (2, "B"),
        (3, "C"),
    ]
    assert set(body["entries"][0]) == {
        "rank",
        "player_name",
        "score",
        "correct_count",
        "finished_at",
        "is_me",
    }
    assert "me" not in body


def test_excludes_unnamed_incomplete_expired_and_other_categories(api, cat):
    other = CategoryFactory(slug="baska")
    make_session(cat, 500, name="Görünür")
    make_session(cat, 2000, name=None)  # isim girilmemiş
    make_session(cat, 2000, name="Bitmemiş", status="in_progress")
    make_session(cat, 2000, name="Süresi doldu", status="expired")
    make_session(other, 2000, name="Başka kategori")
    entries = api.get(URL, {"category": "fizik"}).json()["entries"]
    assert [e["player_name"] for e in entries] == ["Görünür"]


def test_default_limit_is_10_and_limit_param(api, cat):
    for i in range(15):
        make_session(cat, 100 * i, minute=i, name=f"P{i}")
    assert len(api.get(URL, {"category": "fizik"}).json()["entries"]) == 10
    assert len(api.get(URL, {"category": "fizik", "limit": 3}).json()["entries"]) == 3
    top = api.get(URL, {"category": "fizik", "limit": 3}).json()["entries"]
    assert [e["score"] for e in top] == [1400, 1300, 1200]


@pytest.mark.parametrize("limit", ["0", "-1", "abc", "51"])
def test_invalid_limit(api, cat, limit):
    response = api.get(URL, {"category": "fizik", "limit": limit})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_category_required_and_unknown_is_404(api, cat):
    assert api.get(URL).status_code == 400
    response = api.get(URL, {"category": "yok"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "category_not_found"
    CategoryFactory(slug="kapali", is_active=False)
    assert api.get(URL, {"category": "kapali"}).status_code == 404


def test_empty_leaderboard(api, cat):
    assert api.get(URL, {"category": "fizik"}).json()["entries"] == []


def test_is_me_highlights_own_row(api, cat):
    make_session(cat, 1900, name="A")
    mine = make_session(cat, 1500, minute=2, name="Ben")
    body = api.get(URL, {"category": "fizik", "session_id": str(mine.id)}).json()
    assert [e["is_me"] for e in body["entries"]] == [False, True]
    assert body["me"]["rank"] == 2
    assert body["me"]["player_name"] == "Ben"


def test_me_is_returned_even_when_outside_top_limit(api, cat):
    for i in range(12):
        make_session(cat, 1000 + 10 * i, minute=i, name=f"P{i}")
    mine = make_session(cat, 100, minute=20, name="Son")
    body = api.get(URL, {"category": "fizik", "session_id": str(mine.id)}).json()
    assert len(body["entries"]) == 10
    assert not any(e["is_me"] for e in body["entries"])
    assert body["me"]["rank"] == 13


def test_me_rank_matches_tie_break(api, cat):
    first = make_session(cat, 1000, minute=1, name="Önce")
    second = make_session(cat, 1000, minute=2, name="Sonra")
    first_rank = api.get(URL, {"category": "fizik", "session_id": str(first.id)}).json()["me"]
    second_rank = api.get(URL, {"category": "fizik", "session_id": str(second.id)}).json()["me"]
    assert (first_rank["rank"], second_rank["rank"]) == (1, 2)


def test_me_is_null_for_unnamed_or_unknown_session(api, cat):
    unnamed = make_session(cat, 1000, name=None)
    for sid in (unnamed.id, "8f1c0000-0000-0000-0000-000000000000"):
        body = api.get(URL, {"category": "fizik", "session_id": str(sid)}).json()
        assert body["me"] is None


def test_full_flow_name_then_leaderboard(driver):
    driver.play([True] * 20)
    driver.api.patch(f"{driver.base}/player-name/", {"player_name": "Ayşe"}, format="json")
    body = driver.api.get(URL, {"category": "yapay-zeka", "session_id": driver.session_id}).json()
    assert body["entries"][0]["player_name"] == "Ayşe"
    assert body["entries"][0]["score"] == 2000
    assert body["entries"][0]["is_me"] is True
