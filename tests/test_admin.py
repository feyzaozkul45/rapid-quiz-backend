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


# ---- ADMIN_URL ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("admin/", "admin/"),
        ("admin", "admin/"),
        ("/admin/", "admin/"),
        ("  gizli-yol-9f3a  ", "gizli-yol-9f3a/"),
        ("yonetim/panel/", "yonetim/panel/"),
        ("", "admin/"),
        (None, "admin/"),
        ("/", "admin/"),
    ],
)
def test_normalize_admin_url(raw, expected):
    from config.admin_url import normalize_admin_url

    assert normalize_admin_url(raw) == expected


@pytest.mark.parametrize("bad", ["ad min/", "admin?x=1", "ad//min", "yönetim/", "a#b", "admin%2F"])
def test_normalize_admin_url_rejects_unsafe_values(bad):
    from django.core.exceptions import ImproperlyConfigured

    from config.admin_url import normalize_admin_url

    with pytest.raises(ImproperlyConfigured):
        normalize_admin_url(bad)


def test_default_admin_url_is_admin(client, db):
    from django.conf import settings

    assert settings.ADMIN_URL == "admin/"
    assert client.get("/admin/login/").status_code == 200
    assert reverse("admin:index") == "/admin/"


@pytest.fixture
def custom_admin_url(settings):
    """URLconf'u verilen ADMIN_URL ile yeniden yükler; test sonunda varsayılana döndürür."""
    import importlib

    from django.urls import clear_url_caches

    import config.urls

    original = settings.ADMIN_URL

    def apply(value):
        settings.ADMIN_URL = value
        importlib.reload(config.urls)
        clear_url_caches()

    yield apply
    settings.ADMIN_URL = original
    importlib.reload(config.urls)
    clear_url_caches()


def test_custom_admin_url_moves_the_admin_and_hides_the_default(client, db, custom_admin_url):
    custom_admin_url("gizli-yol-9f3a/")

    assert client.get("/gizli-yol-9f3a/login/").status_code == 200
    assert client.get("/admin/login/").status_code == 404
    assert client.get("/admin/").status_code == 404
    assert reverse("admin:index") == "/gizli-yol-9f3a/"


def test_custom_admin_url_still_requires_login(client, db, custom_admin_url):
    custom_admin_url("gizli-yol-9f3a/")
    response = client.get("/gizli-yol-9f3a/")
    assert response.status_code == 302
    assert response["Location"].startswith("/gizli-yol-9f3a/login/")
