import pytest
from django.urls import reverse

from apps.quiz.models import Category, Question


def _payload(category, correct_flags, count=4):
    data = {
        "category": category.pk,
        "text": "Yeni soru",
        "difficulty": 1,
        "is_active": "on",
        "choices-TOTAL_FORMS": count,
        "choices-INITIAL_FORMS": 0,
        "choices-MIN_NUM_FORMS": 0,
        "choices-MAX_NUM_FORMS": 4,
    }
    for i in range(count):
        data[f"choices-{i}-text"] = f"Seçenek {i}"
        data[f"choices-{i}-order"] = i
        if correct_flags[i]:
            data[f"choices-{i}-is_correct"] = "on"
    return data


@pytest.fixture
def admin_client_(admin_client):
    return admin_client


@pytest.mark.django_db
def test_admin_requires_exactly_one_correct(admin_client_):
    category = Category.objects.create(name="C", slug="c")
    url = reverse("admin:quiz_question_add")
    for flags in ([False] * 4, [True, True, False, False]):
        response = admin_client_.post(url, _payload(category, flags))
        assert response.status_code == 200  # form hata ile geri döner
    assert Question.objects.count() == 0


@pytest.mark.django_db
def test_admin_requires_four_choices(admin_client_):
    category = Category.objects.create(name="C", slug="c")
    url = reverse("admin:quiz_question_add")
    response = admin_client_.post(url, _payload(category, [True, False, False], count=3))
    assert response.status_code == 200
    assert Question.objects.count() == 0


@pytest.mark.django_db
def test_admin_accepts_valid_question(admin_client_):
    category = Category.objects.create(name="C", slug="c")
    url = reverse("admin:quiz_question_add")
    response = admin_client_.post(url, _payload(category, [False, True, False, False]))
    assert response.status_code == 302
    assert Question.objects.get().choices.filter(is_correct=True).count() == 1
