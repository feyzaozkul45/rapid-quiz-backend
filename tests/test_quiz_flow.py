import json

import pytest

from apps.quiz.models import Choice
from apps.quiz_sessions.models import QuizSession, SessionAnswer

from .conftest import QuizDriver
from .factories import CategoryFactory, make_category

pytestmark = pytest.mark.django_db


def error_code(response):
    return response.json()["error"]["code"]


# ---- kategoriler / oturum başlatma -------------------------------------------------


def test_categories_lists_only_active_ordered(api):
    CategoryFactory(name="B", slug="b", order=2)
    CategoryFactory(name="A", slug="a", order=1)
    CategoryFactory(name="Gizli", slug="gizli", is_active=False)
    response = api.get("/api/v1/categories/")
    assert response.status_code == 200
    assert [c["slug"] for c in response.json()] == ["a", "b"]


def test_start_session_creates_20_distinct_questions(api, category):
    response = api.post("/api/v1/quiz-sessions/", {"category": "yapay-zeka"}, format="json")
    assert response.status_code == 201
    body = response.json()
    assert body["total_questions"] == 20
    assert body["time_limit_seconds"] == 5
    assert body["category"] == "yapay-zeka"
    session = QuizSession.objects.get(pk=body["session_id"])
    rows = list(session.answers.all())
    assert [r.position for r in rows] == list(range(20))
    assert len({r.question_id for r in rows}) == 20
    assert all(r.served_at is None for r in rows)


def test_start_session_picks_20_of_larger_pool(api):
    make_category(35, slug="buyuk")
    response = api.post("/api/v1/quiz-sessions/", {"category": "buyuk"}, format="json")
    session = QuizSession.objects.get(pk=response.json()["session_id"])
    assert session.answers.count() == 20


def test_start_session_ignores_inactive_questions(api):
    category = make_category(20, slug="k")
    category.questions.first().delete()
    category.questions.update(is_active=True)
    first = category.questions.first()
    first.is_active = False
    first.save()
    response = api.post("/api/v1/quiz-sessions/", {"category": "k"}, format="json")
    assert response.status_code == 409
    assert error_code(response) == "category_unavailable"


def test_start_session_unknown_or_inactive_category(api):
    CategoryFactory(slug="kapali", is_active=False)
    for slug in ("yok", "kapali"):
        response = api.post("/api/v1/quiz-sessions/", {"category": slug}, format="json")
        assert response.status_code == 400
        assert error_code(response) == "validation_error"


def test_client_type_from_body_header_and_default(api, category):
    def start(**kwargs):
        response = api.post("/api/v1/quiz-sessions/", {"category": "yapay-zeka"}, **kwargs)
        return QuizSession.objects.get(pk=response.json()["session_id"]).client_type

    assert start(format="json") == "web"
    assert start(format="json", headers={"X-Client-Type": "ios"}) == "ios"
    assert start(format="json", headers={"X-Client-Type": "bogus"}) == "web"
    body = {"category": "yapay-zeka", "client_type": "android"}
    response = api.post("/api/v1/quiz-sessions/", body, format="json")
    assert QuizSession.objects.get(pk=response.json()["session_id"]).client_type == "android"


# ---- sıradaki soru -----------------------------------------------------------------


def test_current_question_never_leaks_correct_answer(driver):
    response = driver.question()
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "position",
        "total",
        "question_id",
        "text",
        "choices",
        "time_limit_seconds",
        "served_at",
        "remaining_seconds",
    }
    assert len(body["choices"]) == 4
    assert all(set(c) == {"id", "text"} for c in body["choices"])
    raw = json.dumps(body).lower()
    assert "correct" not in raw


def test_repeated_current_question_keeps_served_at(driver):
    first = driver.question().json()
    driver.clock.advance(2)
    second = driver.question().json()
    assert second["question_id"] == first["question_id"]
    assert second["served_at"] == first["served_at"]
    assert first["remaining_seconds"] == 5.0
    assert second["remaining_seconds"] == 3.0


def test_questions_advance_only_after_answer(driver):
    q1 = driver.question().json()
    assert q1["position"] == 0
    driver.answer(q1["question_id"], driver.correct_id(q1["question_id"]))
    q2 = driver.question().json()
    assert q2["position"] == 1
    assert q2["question_id"] != q1["question_id"]


# ---- cevap gönderme ----------------------------------------------------------------


def test_correct_answer_gives_100_points(driver):
    q = driver.question().json()
    driver.clock.advance(3)
    correct = driver.correct_id(q["question_id"])
    response = driver.answer(q["question_id"], correct)
    assert response.status_code == 200
    assert response.json() == {
        "is_correct": True,
        "correct_choice_id": correct,
        "points": 100,
        "too_fast": False,
        "is_last": False,
        "score_so_far": 100,
    }


def test_wrong_answer_and_null_answer_give_zero(driver):
    q = driver.question().json()
    wrong = driver.wrong_id(q["question_id"])
    response = driver.answer(q["question_id"], wrong).json()
    assert response["is_correct"] is False
    assert response["points"] == 0
    assert response["correct_choice_id"] == driver.correct_id(q["question_id"])
    q = driver.question().json()
    driver.clock.advance(5)
    response = driver.answer(q["question_id"], None).json()
    assert response["is_correct"] is False
    assert response["points"] == 0
    assert response["score_so_far"] == 0
    row = SessionAnswer.objects.get(session_id=driver.session_id, position=1)
    assert row.selected_choice is None


@pytest.mark.parametrize(
    ("delay", "counted"), [(0.3, True), (0.5, True), (5, True), (6, True), (6.5, False)]
)
def test_time_boundaries_via_api(driver, delay, counted):
    q = driver.question().json()
    driver.clock.advance(delay)
    response = driver.answer(q["question_id"], driver.correct_id(q["question_id"])).json()
    assert response["is_correct"] is counted
    assert response["points"] == (100 if counted else 0)


def test_late_answer_does_not_store_choice(driver):
    q = driver.question().json()
    driver.clock.advance(8)
    driver.answer(q["question_id"], driver.correct_id(q["question_id"]))
    row = SessionAnswer.objects.get(session_id=driver.session_id, position=0)
    assert row.selected_choice is None
    assert row.is_correct is False


def test_question_mismatch_returns_409(driver):
    q = driver.question().json()
    other = (
        SessionAnswer.objects.filter(session_id=driver.session_id, position=5).first().question_id
    )
    response = driver.answer(other, None)
    assert response.status_code == 409
    assert error_code(response) == "question_mismatch"
    # oturum ilerlemedi
    assert driver.question().json()["question_id"] == q["question_id"]


def test_second_answer_to_same_question_rejected(driver):
    q = driver.question().json()
    driver.clock.advance(1)
    assert driver.answer(q["question_id"], driver.correct_id(q["question_id"])).status_code == 200
    again = driver.answer(q["question_id"], driver.correct_id(q["question_id"]))
    assert again.status_code == 409
    assert error_code(again) == "question_mismatch"
    session = QuizSession.objects.get(pk=driver.session_id)
    assert session.score == 100
    assert session.current_index == 1


def test_answer_before_question_served_rejected(driver):
    first = SessionAnswer.objects.get(session_id=driver.session_id, position=0)
    response = driver.answer(first.question_id, None)
    assert response.status_code == 409
    assert error_code(response) == "question_not_served"


def test_choice_from_another_question_is_invalid(driver):
    q = driver.question().json()
    foreign = Choice.objects.exclude(question_id=q["question_id"]).first().pk
    response = driver.answer(q["question_id"], foreign)
    assert response.status_code == 400
    assert error_code(response) == "invalid_choice"
    assert QuizSession.objects.get(pk=driver.session_id).current_index == 0


def test_answer_body_validation(driver):
    response = driver.api.post(f"{driver.base}/answers/", {"choice_id": 1}, format="json")
    assert response.status_code == 400
    assert error_code(response) == "validation_error"


# ---- quiz'in tamamlanması ----------------------------------------------------------


def test_full_quiz_scores_100_per_correct(driver):
    flags = [True] * 13 + [False] * 7
    last = driver.play(flags).json()
    assert last["is_last"] is True
    assert last["score_so_far"] == 1300
    session = QuizSession.objects.get(pk=driver.session_id)
    assert session.status == "completed"
    assert session.correct_count == 13
    assert session.score == 1300
    assert session.finished_at is not None
    assert session.answers.filter(answered_at__isnull=False).count() == 20

    result = driver.api.get(f"{driver.base}/result/")
    assert result.status_code == 200
    assert result.json() == {
        "session_id": driver.session_id,
        "category": "yapay-zeka",
        "status": "completed",
        "score": 1300,
        "correct_count": 13,
        "total_questions": 20,
        "max_score": 2000,
        "player_name": None,
        "finished_at": result.json()["finished_at"],
    }


def test_perfect_quiz_is_2000(driver):
    assert driver.play([True] * 20).json()["score_so_far"] == 2000


def test_completed_session_rejects_further_calls(driver):
    driver.play([True] * 20)
    for response in (driver.question(), driver.answer(1, None)):
        assert response.status_code == 409
        assert error_code(response) == "session_completed"


def test_result_before_completion_is_409(driver):
    response = driver.api.get(f"{driver.base}/result/")
    assert response.status_code == 409
    assert error_code(response) == "session_not_completed"


# ---- süre aşımı / hareketsizlik ----------------------------------------------------


def test_stale_question_is_auto_marked_unanswered(driver):
    q1 = driver.question().json()
    driver.clock.advance(7)  # istemci kayboldu, cevap göndermedi
    q2 = driver.question().json()
    assert q2["position"] == 1
    assert q2["question_id"] != q1["question_id"]
    assert q2["remaining_seconds"] == 5.0
    row = SessionAnswer.objects.get(session_id=driver.session_id, position=0)
    assert row.selected_choice is None
    assert row.is_correct is False
    assert row.answered_at is not None
    # artık eski soruya cevap kabul edilmez
    assert driver.answer(q1["question_id"], None).status_code == 409


def test_stale_within_tolerance_keeps_same_question(driver):
    q1 = driver.question().json()
    driver.clock.advance(5.5)
    assert driver.question().json()["question_id"] == q1["question_id"]


def test_stale_last_question_completes_session(driver):
    driver.play([True] * 19)
    driver.question()
    driver.clock.advance(10)
    response = driver.question()
    assert response.status_code == 409
    assert error_code(response) == "session_completed"
    session = QuizSession.objects.get(pk=driver.session_id)
    assert session.status == "completed"
    assert session.correct_count == 19
    assert session.score == 1900


def test_inactive_session_expires_and_persists(driver):
    driver.question()
    driver.clock.advance(11 * 60)
    response = driver.question()
    assert response.status_code == 410
    assert error_code(response) == "session_expired"
    assert QuizSession.objects.get(pk=driver.session_id).status == "expired"
    assert driver.answer(1, None).status_code == 410
    assert driver.api.get(f"{driver.base}/result/").status_code == 410


def test_activity_resets_inactivity_timer(driver):
    for _ in range(3):
        q = driver.question().json()
        driver.clock.advance(1)
        driver.answer(q["question_id"], driver.correct_id(q["question_id"]))
        driver.clock.advance(9 * 60)  # her adım arası 9 dk: süre aşılmaz
    assert driver.question().status_code == 200


# ---- isim kaydı --------------------------------------------------------------------


def test_player_name_saved_and_normalized(driver):
    driver.play([True] * 20)
    response = driver.api.patch(
        f"{driver.base}/player-name/", {"player_name": "  Ayşe   Nur "}, format="json"
    )
    assert response.status_code == 200
    assert response.json()["player_name"] == "Ayşe Nur"
    assert response.json()["score"] == 2000
    assert QuizSession.objects.get(pk=driver.session_id).player_name == "Ayşe Nur"


@pytest.mark.parametrize("name", ["", "A", "x" * 21, "Ayşe!", "😀😀", "<script>"])
def test_player_name_invalid(driver, name):
    driver.play([True] * 20)
    response = driver.api.patch(f"{driver.base}/player-name/", {"player_name": name}, format="json")
    assert response.status_code == 400
    assert error_code(response) == "name_invalid"
    assert QuizSession.objects.get(pk=driver.session_id).player_name is None


def test_player_name_only_once(driver):
    driver.play([True] * 20)
    url = f"{driver.base}/player-name/"
    assert driver.api.patch(url, {"player_name": "Ali"}, format="json").status_code == 200
    second = driver.api.patch(url, {"player_name": "Veli"}, format="json")
    assert second.status_code == 409
    assert error_code(second) == "name_already_set"
    assert QuizSession.objects.get(pk=driver.session_id).player_name == "Ali"


def test_player_name_requires_completed_session(driver):
    response = driver.api.patch(
        f"{driver.base}/player-name/", {"player_name": "Ali"}, format="json"
    )
    assert response.status_code == 409
    assert error_code(response) == "session_not_completed"


def test_player_name_rejected_for_expired_session(driver):
    driver.question()
    driver.clock.advance(11 * 60)
    driver.question()  # oturumu expired yapar
    response = driver.api.patch(
        f"{driver.base}/player-name/", {"player_name": "Ali"}, format="json"
    )
    assert response.status_code == 410
    assert error_code(response) == "session_expired"


# ---- hata biçimi ve throttle -------------------------------------------------------


def test_unknown_session_is_404_with_error_format(api, db):
    response = api.get(
        "/api/v1/quiz-sessions/8f1c0000-0000-0000-0000-000000000000/current-question/"
    )
    assert response.status_code == 404
    assert error_code(response) == "session_not_found"
    assert "message" in response.json()["error"]


def test_malformed_session_id_is_404(api, db):
    response = api.get("/api/v1/quiz-sessions/abc/current-question/")
    assert response.status_code == 404


def test_malformed_json_error_format(api, category):
    response = api.post("/api/v1/quiz-sessions/", data="{not json", content_type="application/json")
    assert response.status_code == 400
    assert error_code(response) == "invalid_json"


def test_wrong_method_error_format(api, category):
    response = api.delete("/api/v1/quiz-sessions/")
    assert response.status_code == 405
    assert error_code(response) == "method_not_allowed"


def test_quiz_start_is_rate_limited(api, category):
    for _ in range(10):
        assert (
            api.post(
                "/api/v1/quiz-sessions/", {"category": "yapay-zeka"}, format="json"
            ).status_code
            == 201
        )
    response = api.post("/api/v1/quiz-sessions/", {"category": "yapay-zeka"}, format="json")
    assert response.status_code == 429
    assert error_code(response) == "rate_limited"


def test_throttle_uses_forwarded_ip_when_proxies_configured(api, category, settings):
    from rest_framework.settings import api_settings

    settings.REST_FRAMEWORK = {**settings.REST_FRAMEWORK, "NUM_PROXIES": 1}
    assert api_settings.NUM_PROXIES == 1
    for ip in ("1.1.1.1", "2.2.2.2"):
        for _ in range(10):
            response = api.post(
                "/api/v1/quiz-sessions/",
                {"category": "yapay-zeka"},
                format="json",
                headers={"X-Forwarded-For": ip},
            )
            assert response.status_code == 201
    # 1.1.1.1 limitine takıldı, 2.2.2.2 ayrı sayaçla devam etmişti
    limited = api.post(
        "/api/v1/quiz-sessions/",
        {"category": "yapay-zeka"},
        format="json",
        headers={"X-Forwarded-For": "1.1.1.1"},
    )
    assert limited.status_code == 429


def test_player_name_window_closed_after_30_minutes(driver):
    driver.play([True] * 20)
    driver.clock.advance(30 * 60 + 1)
    response = driver.api.patch(
        f"{driver.base}/player-name/", {"player_name": "Ali"}, format="json"
    )
    assert response.status_code == 410
    assert error_code(response) == "name_window_closed"
    assert QuizSession.objects.get(pk=driver.session_id).player_name is None


def test_player_name_accepted_inside_window(driver):
    driver.play([True] * 20)
    driver.clock.advance(29 * 60)
    response = driver.api.patch(
        f"{driver.base}/player-name/", {"player_name": "Ali"}, format="json"
    )
    assert response.status_code == 200


# ---- tekrar önleme (recent_question_ids) -------------------------------------------


def _start(api, **body):
    return api.post("/api/v1/quiz-sessions/", {"category": "havuz", **body}, format="json")


def _question_ids(response):
    session = QuizSession.objects.get(pk=response.json()["session_id"])
    return {r.question_id for r in session.answers.all()}


@pytest.fixture
def pool40(db):
    return make_category(40, slug="havuz")


def test_recent_question_ids_are_avoided_when_enough_fresh_questions(api, pool40):
    ids = sorted(pool40.questions.values_list("id", flat=True))
    recent = ids[:20]
    for _ in range(3):
        response = _start(api, recent_question_ids=recent)
        assert response.status_code == 201
        assert _question_ids(response) == set(ids[20:])


def test_recent_question_ids_fill_up_with_oldest_when_not_enough(api, pool40):
    ids = sorted(pool40.questions.values_list("id", flat=True))
    recent = ids[:35]  # eskiden yeniye
    chosen = _question_ids(_start(api, recent_question_ids=recent))
    assert set(ids[35:]) <= chosen
    assert chosen - set(ids[35:]) == set(ids[:15])


def test_recent_question_ids_optional_and_empty_allowed(api, pool40):
    assert _start(api).status_code == 201
    assert _start(api, recent_question_ids=[]).status_code == 201


def test_recent_question_ids_unknown_ids_are_ignored(api, pool40):
    response = _start(api, recent_question_ids=[10**9, 2_147_483_647])
    assert response.status_code == 201
    assert len(_question_ids(response)) == 20


@pytest.mark.parametrize(
    "bad",
    [
        list(range(1, 42)),  # 41 ID: sınır aşımı
        ["1", "2"],  # sayı değil, metin
        [1.5],
        [True],
        [None],
        [0],
        [-3],
        [2_147_483_648],
        [[1]],
        "1,2,3",
        {"a": 1},
        123,
    ],
)
def test_recent_question_ids_validation(api, pool40, bad):
    response = _start(api, recent_question_ids=bad)
    assert response.status_code == 400, response.content
    assert error_code(response) == "validation_error"
    assert "recent_question_ids" in response.json()["error"]["details"]


def test_recent_question_ids_exactly_40_is_accepted(api, pool40):
    ids = list(pool40.questions.values_list("id", flat=True))
    assert len(ids) == 40
    assert _start(api, recent_question_ids=ids).status_code == 201


# ---- seçenek sırası ------------------------------------------------------------------


def test_choice_order_is_stable_within_session_and_not_the_stored_order(api, clock, category):
    shuffled_somewhere = False
    for _ in range(8):  # başlatma limiti 10/dk
        session_driver = QuizDriver(api, clock, category)
        a = session_driver.question().json()
        b = session_driver.question().json()
        ids = [c["id"] for c in a["choices"]]
        assert ids == [c["id"] for c in b["choices"]]  # aynı oturumda yenilemede değişmez
        shuffled_somewhere |= ids != sorted(ids)  # veritabanı sırasından farklı olabilir
    # Hepsinin sıralı gelme olasılığı (1/24)^8: pratikte sıfır
    assert shuffled_somewhere


def test_every_session_question_keeps_all_four_choices_after_shuffle(driver):
    q = driver.question().json()
    stored = set(Choice.objects.filter(question_id=q["question_id"]).values_list("id", flat=True))
    assert {c["id"] for c in q["choices"]} == stored
    assert len(q["choices"]) == 4


# ---- 300 ms'den hızlı cevap ----------------------------------------------------------


def test_answer_faster_than_300ms_gets_no_points_and_is_flagged(driver):
    q = driver.question().json()
    driver.clock.advance(0.1)
    correct = driver.correct_id(q["question_id"])
    body = driver.answer(q["question_id"], correct).json()
    assert body["too_fast"] is True
    assert body["is_correct"] is False
    assert body["points"] == 0
    assert body["score_so_far"] == 0
    session = QuizSession.objects.get(pk=driver.session_id)
    assert session.correct_count == 0
    assert session.current_index == 1  # soru yine de kapanır


def test_answer_at_or_after_300ms_is_scored_normally(driver):
    q = driver.question().json()
    driver.clock.advance(0.3)
    body = driver.answer(q["question_id"], driver.correct_id(q["question_id"])).json()
    assert body["too_fast"] is False
    assert body["points"] == 100


def test_timeout_null_answer_is_never_flagged_too_fast(driver):
    q = driver.question().json()
    body = driver.answer(q["question_id"], None).json()
    assert body["too_fast"] is False
    assert body["points"] == 0
