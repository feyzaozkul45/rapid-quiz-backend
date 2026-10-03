"""Skor tablosu sorguları.

Yalnızca status=completed ve player_name dolu oturumlar listelenir. Sıralama: puan (azalan),
eşitlikte bitiş zamanı (erken bitiren üstte), son çare id. Sorgu, kısmi indeksle
(`category, -score, finished_at` WHERE player_name IS NOT NULL) desteklenir.
"""

from django.db.models import Q

from apps.quiz_sessions.models import QuizSession

ORDERING = ("-score", "finished_at", "id")


def ranked_sessions(category):
    return QuizSession.objects.filter(
        category=category,
        status=QuizSession.Status.COMPLETED,
        player_name__isnull=False,
    ).order_by(*ORDERING)


def top_entries(category, limit):
    return [
        {
            "rank": rank,
            "id": s.id,
            "player_name": s.player_name,
            "score": s.score,
            "correct_count": s.correct_count,
            "finished_at": s.finished_at,
        }
        for rank, s in enumerate(ranked_sessions(category)[:limit], start=1)
    ]


def rank_of(session):
    """Oturumun kategorideki sırası (1'den başlar); tabloda değilse None."""
    if (
        session.status != QuizSession.Status.COMPLETED
        or session.player_name is None
        or session.finished_at is None
    ):
        return None
    ahead = ranked_sessions(session.category_id).filter(
        Q(score__gt=session.score)
        | Q(score=session.score, finished_at__lt=session.finished_at)
        | Q(score=session.score, finished_at=session.finished_at, id__lt=session.id)
    )
    return ahead.count() + 1
