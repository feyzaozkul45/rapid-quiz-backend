"""PostgreSQL'e özgü davranışlar (kısmi indeks, eş zamanlılık, kısıtlar).

Yerelde SQLite ile koşarken atlanır; CI'da REQUIRE_POSTGRES=1 olduğu için atlanamaz.
"""

import os
import threading
from datetime import timedelta

import pytest
from django.db import IntegrityError, connection, connections, transaction
from django.utils import timezone

from apps.leaderboard.queries import ranked_sessions
from apps.quiz.models import Choice
from apps.quiz_sessions import workflow
from apps.quiz_sessions.models import QuizSession, SessionAnswer
from config.api_errors import ApiError

from .factories import QuestionFactory, make_category

pytestmark = pytest.mark.usefixtures("postgres_only")


@pytest.mark.django_db
def test_database_is_postgresql_18_in_ci():
    if os.environ.get("REQUIRE_POSTGRES"):
        assert connection.vendor == "postgresql"
        assert connection.pg_version >= 180000


@pytest.mark.django_db
def test_leaderboard_index_is_partial():
    with connection.cursor() as cursor:
        cursor.execute("SELECT indexdef FROM pg_indexes WHERE indexname = 'leaderboard_idx'")
        (indexdef,) = cursor.fetchone()
    assert "WHERE" in indexdef
    assert "player_name IS NOT NULL" in indexdef
    assert "score DESC" in indexdef


@pytest.mark.django_db
def test_leaderboard_query_can_use_partial_index():
    category = make_category(0)
    queryset = ranked_sessions(category)[:10]
    with connection.cursor() as cursor:
        cursor.execute("SET LOCAL enable_seqscan = off")
        cursor.execute("SET LOCAL enable_bitmapscan = off")
        sql, params = queryset.query.sql_with_params()
        cursor.execute("EXPLAIN " + sql, params)
        plan = "\n".join(row[0] for row in cursor.fetchall())
    assert "leaderboard_idx" in plan, plan


@pytest.mark.django_db
def test_one_correct_choice_is_a_partial_unique_index():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'choice_one_correct_per_question'"
        )
        (indexdef,) = cursor.fetchone()
    assert "UNIQUE" in indexdef
    assert "is_correct" in indexdef


@pytest.mark.django_db
def test_second_correct_choice_rejected_by_database():
    question = QuestionFactory()  # factory zaten 1 doğru seçenek oluşturdu
    with pytest.raises(IntegrityError), transaction.atomic():
        Choice.objects.create(question=question, text="ikinci", is_correct=True)


@pytest.mark.django_db
def test_duplicate_session_position_rejected_by_database():
    category = make_category(20)
    session = workflow.start_session(category, "web")
    existing = session.answers.get(position=0)
    with pytest.raises(IntegrityError), transaction.atomic():
        SessionAnswer.objects.create(session=session, question_id=existing.question_id, position=0)


def _run_concurrently(workers):
    """Her işi ayrı thread'de (ayrı DB bağlantısıyla) aynı anda başlatır."""
    barrier = threading.Barrier(len(workers))
    results = [None] * len(workers)

    def run(i, fn):
        try:
            barrier.wait()
            results[i] = ("ok", fn())
        except Exception as exc:
            results[i] = ("error", exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert all(r is not None for r in results), "thread zaman aşımına uğradı"
    return results


@pytest.mark.django_db(transaction=True)
def test_concurrent_answers_to_same_question_only_one_counts():
    category = make_category(20)
    session = workflow.start_session(category, "web")
    question_id = workflow.get_current_question(session.id)["question_id"]
    correct = Choice.objects.get(question_id=question_id, is_correct=True).pk
    # Soru 1 sn önce gönderilmiş gibi yap: 300 ms'den hızlı cevaplar puansızdır (too_fast) ve bu
    # test eş zamanlılığı ölçer, hız kuralını değil.
    SessionAnswer.objects.filter(session=session, position=0).update(
        served_at=timezone.now() - timedelta(seconds=1)
    )

    results = _run_concurrently(
        [lambda: workflow.submit_answer(session.id, question_id, correct) for _ in range(5)]
    )

    ok = [r for r in results if r[0] == "ok"]
    errors = [r[1] for r in results if r[0] == "error"]
    assert len(ok) == 1, results
    assert len(errors) == 4
    assert all(isinstance(e, ApiError) and e.code == "question_mismatch" for e in errors)
    session.refresh_from_db()
    assert session.current_index == 1
    assert session.score == 100
    assert session.correct_count == 1
    assert session.answers.filter(answered_at__isnull=False).count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_current_question_keeps_single_served_at():
    category = make_category(20)
    session = workflow.start_session(category, "web")
    results = _run_concurrently([lambda: workflow.get_current_question(session.id)] * 5)
    assert all(r[0] == "ok" for r in results), results
    assert len({r[1]["served_at"] for r in results}) == 1
    assert len({r[1]["question_id"] for r in results}) == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_player_name_saves_only_one_wins():
    category = make_category(20)
    session = workflow.start_session(category, "web")
    QuizSession.objects.filter(pk=session.pk).update(
        status="completed", finished_at=session.started_at
    )
    names = ["Ali", "Veli", "Ayşe", "Fatma"]
    results = _run_concurrently(
        [
            lambda n=n: workflow.save_player_name(session.id, n, now=session.started_at)
            for n in names
        ]
    )
    ok = [r for r in results if r[0] == "ok"]
    errors = [r[1] for r in results if r[0] == "error"]
    assert len(ok) == 1, results
    assert all(isinstance(e, ApiError) and e.code == "name_already_set" for e in errors)
    session.refresh_from_db()
    assert session.player_name in names
