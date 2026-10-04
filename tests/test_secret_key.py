import os
import subprocess
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.secret_key import validate_secret_key

STRONG = "k8s9Xq2LmZp7Vw4Rt1Yb6Nc3Hd5Jf0GaSe8UiOo2PlKzMxCvBnQwErTyUiOpAsDfGh"


def test_strong_key_is_accepted_and_returned():
    assert validate_secret_key(STRONG) == STRONG


@pytest.mark.parametrize(
    "weak",
    [
        "",
        None,
        "change-me",
        "insecure-dev-key-change-me",  # base.py geliştirme varsayılanı
        "django-insecure-" + "a1b2c3d4e5" * 6,  # uzun ama örnek işaretli
        "ci-only-secret",  # kısa
        STRONG[:49],  # tam sınırın altı
        "a" * 80,  # uzun ama tek karakter
        "ChangeMe" + "x9Q" * 20,  # 'changeme' içeriyor
    ],
)
def test_weak_keys_are_rejected(weak):
    with pytest.raises(ImproperlyConfigured):
        validate_secret_key(weak)


def test_boundary_is_exactly_50_characters():
    assert validate_secret_key(STRONG[:50]) == STRONG[:50]


def test_error_message_never_contains_the_key():
    key = "change-me-super-gizli"
    with pytest.raises(ImproperlyConfigured) as excinfo:
        validate_secret_key(key)
    assert key not in str(excinfo.value)


def _import_prod_settings(secret):
    env = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.prod"}
    env.pop("DATABASE_URL", None)
    env["DJANGO_SECRET_KEY"] = secret
    return subprocess.run(
        [sys.executable, "-c", "import config.settings.prod"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_prod_settings_refuse_to_start_with_weak_key():
    result = _import_prod_settings("change-me")
    assert result.returncode != 0
    assert "ImproperlyConfigured" in result.stderr
    assert "change-me" not in result.stderr.replace("DJANGO_SECRET_KEY güvenli değil", "")


def test_prod_settings_start_with_strong_key():
    result = _import_prod_settings(STRONG)
    assert result.returncode == 0, result.stderr
