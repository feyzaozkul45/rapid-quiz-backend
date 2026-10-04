"""Oturum tabanlı ve okuma uç noktaları için hız sınırları.

Hızlı olsun diye sınırlar test içinde küçültülür (`SimpleRateThrottle.THROTTLE_RATES` paylaşılan
bir sözlüktür); gerçek değerler ayrıca bir testle doğrulanır.
"""

import pytest
from rest_framework.settings import api_settings
from rest_framework.throttling import SimpleRateThrottle

from .conftest import QuizDriver

pytestmark = pytest.mark.django_db


@pytest.fixture
def small_rates(monkeypatch):
    def apply(**rates):
        for scope, rate in rates.items():
            monkeypatch.setitem(SimpleRateThrottle.THROTTLE_RATES, scope, rate)

    return apply


def test_configured_rates_match_documentation():
    rates = api_settings.DEFAULT_THROTTLE_RATES
    assert rates["answer_session"] == "40/min"
    assert rates["question_session"] == "60/min"
    assert rates["question"] == "240/min"
    assert rates["read"] == "300/min"
    # Mevcut IP sınırları değişmedi
    assert (rates["quiz_start"], rates["player_name"], rates["answer"]) == (
        "10/min",
        "10/min",
        "120/min",
    )


def test_answers_are_limited_per_session(api, clock, category, small_rates):
    small_rates(answer_session="3/min")
    first = QuizDriver(api, clock, category)
    other = QuizDriver(api, clock, category)

    statuses = [first.answer(1, None).status_code for _ in range(4)]

    assert 429 not in statuses[:3]
    assert statuses[3] == 429
    limited = first.answer(1, None)
    assert limited.json()["error"]["code"] == "rate_limited"
    # Başka bir oturum aynı IP'den etkilenmez
    assert other.answer(1, None).status_code != 429


def test_current_question_is_limited_per_session(api, clock, category, small_rates):
    small_rates(question_session="3/min")
    first = QuizDriver(api, clock, category)
    other = QuizDriver(api, clock, category)

    statuses = [first.question().status_code for _ in range(4)]

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429
    assert first.question().json()["error"]["code"] == "rate_limited"
    assert other.question().status_code == 200


def test_session_limit_does_not_depend_on_forwarded_ip_header(
    api, clock, category, small_rates, settings
):
    """İstemci X-Forwarded-For'u değiştirerek oturum sınırından kaçamaz."""
    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    small_rates(question_session="3/min")
    driver = QuizDriver(api, clock, category)

    statuses = [
        api.get(
            f"{driver.base}/current-question/", headers={"X-Forwarded-For": f"10.0.0.{i}"}
        ).status_code
        for i in range(5)
    ]

    assert statuses[:3] == [200, 200, 200]
    assert statuses[3:] == [429, 429]


def test_uppercase_uuid_cannot_be_used_to_get_a_fresh_counter(api, clock, category, small_rates):
    """Yol dönüştürücüsü yalnızca küçük harfli UUID kabul eder: varyantlar sayaç sıfırlayamaz."""
    small_rates(question_session="2/min")
    driver = QuizDriver(api, clock, category)
    upper = driver.base.replace(driver.session_id, driver.session_id.upper())

    assert api.get(f"{upper}/current-question/").status_code == 404
    assert [driver.question().status_code for _ in range(3)] == [200, 200, 429]


def test_current_question_has_a_per_ip_limit_across_sessions(api, clock, category, small_rates):
    small_rates(question="4/min")
    drivers = [QuizDriver(api, clock, category) for _ in range(3)]

    statuses = [drivers[i % 3].question().status_code for i in range(5)]

    assert statuses[:4] == [200] * 4
    assert statuses[4] == 429


def test_read_endpoints_share_a_per_ip_limit(api, category, small_rates):
    small_rates(read="3/min")
    missing = "/api/v1/quiz-sessions/8f1c0000-0000-0000-0000-000000000000/result/"

    assert api.get("/api/v1/categories/").status_code == 200
    assert api.get("/api/v1/leaderboard/?category=yapay-zeka").status_code == 200
    assert api.get(missing).status_code == 404  # sonuç da sayılır (oturum yok ama istek geçti)
    for url in ("/api/v1/categories/", "/api/v1/leaderboard/?category=yapay-zeka", missing):
        response = api.get(url)
        assert response.status_code == 429, url
        assert response.json()["error"]["code"] == "rate_limited"


def test_health_check_is_not_throttled(api, db, small_rates):
    small_rates(read="1/min")
    assert all(api.get("/api/v1/health/").status_code == 200 for _ in range(5))


def test_normal_full_quiz_stays_far_below_session_limits(driver):
    """Meşru bir oyuncu (20 soru + yenilemeler) oturum sınırlarına takılmaz."""
    for _ in range(20):
        q = driver.question().json()
        driver.question()  # sayfa yenileme
        driver.clock.advance(1)
        response = driver.answer(q["question_id"], driver.correct_id(q["question_id"]))
        assert response.status_code == 200
    assert driver.question().status_code == 409  # quiz bitti, 429 değil
