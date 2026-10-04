"""Eski oturumların temizliği (ücretsiz veritabanı katmanının sınırsız büyümesini önler).

Silinenler (cevapları `SessionAnswer` ile birlikte):
- `in_progress`/`expired` oturumlar: son hareketten bu yana `days` günden uzun süre geçmiş
  (10 dk hareketsizlikten sonra zaten kullanılamaz durumdadır),
- `completed` ama ismi girilmemiş oturumlar: bitişten bu yana `days` günden uzun süre geçmiş
  (isim yalnızca bitişten sonraki 30 dk içinde kaydedilebilir).

İsmi girilmiş tamamlanmış oturumlar (skor tablosu) asla silinmez.
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from .models import QuizSession, SessionAnswer

Status = QuizSession.Status

MIN_DAYS = 1  # isim penceresi (30 dk) ve hareketsizlik (10 dk) çok altında; canlı oturum silinmesin
DEFAULT_DAYS = 7
DEFAULT_LIMIT = 5000
BATCH_SIZE = 500


def stale_sessions(now, days):
    cutoff = now - timedelta(days=days)
    return QuizSession.objects.filter(
        Q(status__in=[Status.IN_PROGRESS, Status.EXPIRED], last_activity_at__lt=cutoff)
        | Q(status=Status.COMPLETED, player_name__isnull=True, finished_at__lt=cutoff)
    )


def purge_stale_sessions(days=DEFAULT_DAYS, limit=DEFAULT_LIMIT, dry_run=False, now=None):
    """(silinen_oturum, silinen_cevap) döndürür; `dry_run`ta silmeden sayar."""
    if days < MIN_DAYS:
        raise ValueError(f"days en az {MIN_DAYS} olmalı.")
    if limit < 1:
        raise ValueError("limit en az 1 olmalı.")
    now = now or timezone.now()
    queryset = stale_sessions(now, days)

    if dry_run:
        ids = list(queryset.values_list("pk", flat=True)[:limit])
        answers = SessionAnswer.objects.filter(session_id__in=ids).count()
        return len(ids), answers

    sessions_deleted = answers_deleted = 0
    while sessions_deleted < limit:
        batch = min(BATCH_SIZE, limit - sessions_deleted)
        ids = list(queryset.order_by("last_activity_at").values_list("pk", flat=True)[:batch])
        if not ids:
            break
        _, per_model = QuizSession.objects.filter(pk__in=ids).delete()
        sessions_deleted += per_model.get(QuizSession._meta.label, 0)
        answers_deleted += per_model.get(SessionAnswer._meta.label, 0)
    return sessions_deleted, answers_deleted
