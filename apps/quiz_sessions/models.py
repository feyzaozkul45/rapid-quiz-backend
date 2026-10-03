import uuid

from django.db import models
from django.db.models import Q

from apps.quiz.models import Category, Choice, Question


class QuizSession(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "Devam ediyor"
        COMPLETED = "completed", "Tamamlandı"
        EXPIRED = "expired", "Süresi doldu"

    class ClientType(models.TextChoices):
        WEB = "web", "Web"
        IOS = "ios", "iOS"
        ANDROID = "android", "Android"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="sessions")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.IN_PROGRESS)
    current_index = models.PositiveSmallIntegerField(default=0)
    score = models.IntegerField(default=0)
    correct_count = models.PositiveSmallIntegerField(default=0)
    player_name = models.CharField(max_length=20, blank=True, null=True)
    client_type = models.CharField(max_length=10, choices=ClientType.choices, default="web")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    # Hareketsizlik (10 dk) kontrolü için son istek zamanı.
    last_activity_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "quiz_sessions"
        indexes = [
            # Skor tablosu: (category_id, score DESC, finished_at), yalnız isim girilenler.
            models.Index(
                fields=["category", "-score", "finished_at"],
                name="leaderboard_idx",
                condition=Q(player_name__isnull=False),
            ),
        ]

    def __str__(self):
        return f"{self.id} ({self.status})"


class SessionAnswer(models.Model):
    session = models.ForeignKey(QuizSession, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    position = models.PositiveSmallIntegerField()
    served_at = models.DateTimeField(blank=True, null=True)
    answered_at = models.DateTimeField(blank=True, null=True)
    selected_choice = models.ForeignKey(
        Choice, on_delete=models.PROTECT, blank=True, null=True, related_name="+"
    )
    is_correct = models.BooleanField(default=False)
    points = models.IntegerField(default=0)

    class Meta:
        db_table = "session_answers"
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(fields=["session", "position"], name="uniq_session_position"),
        ]

    def __str__(self):
        return f"{self.session_id}#{self.position}"
