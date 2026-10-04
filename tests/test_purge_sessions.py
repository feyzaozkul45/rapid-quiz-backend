from datetime import timedelta
from io import StringIO

import pytest
from django.core.cache import caches
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.quiz_sessions import purge
from apps.quiz_sessions.models import QuizSession, SessionAnswer

from .factories import QuestionFactory

pytestmark = pytest.mark.django_db

Status = QuizSession.Status


def make_session(category, status, *, age_days, name=None, answers=2):
    """`age_days` gün önce son hareket görmüş (tamamlandıysa o gün bitmiş) oturum."""
    when = timezone.now() - timedelta(days=age_days)
    session = QuizSession.objects.create(category=category, status=status, player_name=name)
    QuizSession.objects.filter(pk=session.pk).update(
        last_activity_at=when,
        started_at=when,
        finished_at=when if status == Status.COMPLETED else None,
    )
    questions = QuestionFactory.create_batch(answers, category=category)
    SessionAnswer.objects.bulk_create(
        SessionAnswer(session=session, question=q, position=i) for i, q in enumerate(questions)
    )
    return session


def run(**options):
    out = StringIO()
    call_command("purge_sessions", stdout=out, **options)
    return out.getvalue()


def exists(session):
    return QuizSession.objects.filter(pk=session.pk).exists()


def test_deletes_old_unfinished_and_expired_sessions_with_their_answers(category):
    old_in_progress = make_session(category, Status.IN_PROGRESS, age_days=8)
    old_expired = make_session(category, Status.EXPIRED, age_days=30)

    sessions, answers = purge.purge_stale_sessions(days=7)

    assert (sessions, answers) == (2, 4)
    assert not exists(old_in_progress) and not exists(old_expired)
    assert SessionAnswer.objects.count() == 0


def test_deletes_old_completed_sessions_without_a_name(category):
    unnamed = make_session(category, Status.COMPLETED, age_days=9)
    purge.purge_stale_sessions(days=7)
    assert not exists(unnamed)


def test_never_deletes_named_completed_sessions(category):
    named = make_session(category, Status.COMPLETED, age_days=365, name="Ayşe")
    purge.purge_stale_sessions(days=1)
    assert exists(named)
    assert named.answers.count() == 2


def test_keeps_recent_sessions(category):
    recent_in_progress = make_session(category, Status.IN_PROGRESS, age_days=6)
    recent_unnamed = make_session(category, Status.COMPLETED, age_days=2)
    purge.purge_stale_sessions(days=7)
    assert exists(recent_in_progress) and exists(recent_unnamed)


def test_boundary_is_strictly_older_than_days(category):
    just_inside = make_session(category, Status.IN_PROGRESS, age_days=7)
    QuizSession.objects.filter(pk=just_inside.pk).update(
        last_activity_at=timezone.now() - timedelta(days=7) + timedelta(minutes=1)
    )
    just_outside = make_session(category, Status.IN_PROGRESS, age_days=7)
    QuizSession.objects.filter(pk=just_outside.pk).update(
        last_activity_at=timezone.now() - timedelta(days=7, minutes=1)
    )
    purge.purge_stale_sessions(days=7)
    assert exists(just_inside)
    assert not exists(just_outside)


def test_limit_caps_deletions_across_batches(category, monkeypatch):
    monkeypatch.setattr(purge, "BATCH_SIZE", 2)
    sessions = [make_session(category, Status.EXPIRED, age_days=10 + i) for i in range(5)]

    deleted, _ = purge.purge_stale_sessions(days=7, limit=3)

    assert deleted == 3
    assert sum(exists(s) for s in sessions) == 2
    # en eskiler önce silinir
    assert exists(sessions[0]) and exists(sessions[1])

    deleted, _ = purge.purge_stale_sessions(days=7, limit=100)
    assert deleted == 2


def test_dry_run_changes_nothing(category):
    make_session(category, Status.EXPIRED, age_days=10)
    assert purge.purge_stale_sessions(days=7, dry_run=True) == (1, 2)
    assert QuizSession.objects.count() == 1
    assert SessionAnswer.objects.count() == 2


@pytest.mark.parametrize("days", [0, -1])
def test_rejects_unsafe_days(days):
    with pytest.raises(ValueError, match="days"):
        purge.purge_stale_sessions(days=days)


def test_command_reports_counts_and_validates_arguments(category):
    make_session(category, Status.EXPIRED, age_days=10)
    assert "Silinecek: 1 oturum, 2 cevap" in run(dry_run=True)
    assert "Silinen: 1 oturum, 2 cevap" in run()
    assert "Silinen: 0 oturum, 0 cevap" in run()
    with pytest.raises(CommandError):
        run(days=0)
    with pytest.raises(CommandError):
        run(limit=0)


def test_cache_keeps_up_to_100k_throttle_entries():
    cache = caches["default"]
    assert cache._max_entries == 100_000  # varsayılan 300 sayaçları sessizce silerdi
