import os
from datetime import datetime, timedelta

import pytest
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.quiz.models import Choice

from .factories import make_category


@pytest.fixture(scope="session")
def django_db_setup(django_db_setup, django_db_blocker):
    """Throttle için kullanılan DatabaseCache tablosu migrate ile oluşmaz.

    Testler transaction içinde koştuğundan sayaçlar testler arasında sızmaz (rollback).
    """
    with django_db_blocker.unblock():
        call_command("createcachetable", verbosity=0)


@pytest.fixture
def postgres_only():
    """PostgreSQL'e özgü testler. CI'da (REQUIRE_POSTGRES=1) atlanmaz, hata verir."""
    if connection.vendor != "postgresql":
        if os.environ.get("REQUIRE_POSTGRES"):
            pytest.fail(f"REQUIRE_POSTGRES=1 ama veritabanı {connection.vendor}")
        pytest.skip("PostgreSQL gerektirir")


class Clock:
    """Testlerde sunucu saatini kontrol eder (timezone.now yerine geçer)."""

    def __init__(self):
        self.current = timezone.now()

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current += timedelta(seconds=seconds)

    @property
    def now(self) -> datetime:
        return self.current


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(timezone, "now", c)
    return c


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def category(db):
    return make_category(20, slug="yapay-zeka", name="Yapay Zeka")


class QuizDriver:
    """API üzerinden bir quiz oturumunu yürüten test yardımcısı."""

    def __init__(self, api, clock, category):
        self.api, self.clock, self.category = api, clock, category
        response = api.post("/api/v1/quiz-sessions/", {"category": category.slug}, format="json")
        assert response.status_code == 201, response.content
        self.session_id = response.json()["session_id"]
        self.base = f"/api/v1/quiz-sessions/{self.session_id}"

    def question(self):
        return self.api.get(f"{self.base}/current-question/")

    def answer(self, question_id, choice_id):
        return self.api.post(
            f"{self.base}/answers/",
            {"question_id": question_id, "choice_id": choice_id},
            format="json",
        )

    @staticmethod
    def correct_id(question_id):
        return Choice.objects.get(question_id=question_id, is_correct=True).pk

    @staticmethod
    def wrong_id(question_id):
        return Choice.objects.filter(question_id=question_id, is_correct=False).first().pk

    def play(self, correct_flags, seconds_per_question=1):
        """correct_flags[i] True ise i. soruyu doğru, değilse yanlış cevaplar."""
        last = None
        for flag in correct_flags:
            q = self.question().json()
            self.clock.advance(seconds_per_question)
            choice = self.correct_id(q["question_id"]) if flag else self.wrong_id(q["question_id"])
            last = self.answer(q["question_id"], choice)
            assert last.status_code == 200, last.content
        return last


@pytest.fixture
def driver(api, clock, category):
    return QuizDriver(api, clock, category)
