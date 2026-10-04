import re

from django.core.exceptions import ImproperlyConfigured

_VALID = re.compile(r"^[A-Za-z0-9_\-/]+$")


def normalize_admin_url(raw):
    """`ADMIN_URL` ortam değişkenini `path()` için biçimler: baştaki `/` atılır, sonuna `/` eklenir.

    Boş değer varsayılan `admin/` olur. Yalnızca harf, rakam, `_`, `-` ve `/` kabul edilir;
    böylece yanlış yazılmış bir değer sessizce çalışmayan bir adres üretmez.
    """
    value = (raw or "").strip().strip("/")
    if not value:
        return "admin/"
    if not _VALID.match(value) or "//" in value:
        raise ImproperlyConfigured(
            "ADMIN_URL yalnızca harf, rakam, '_', '-' ve '/' içerebilir (ör. 'gizli-yol-9f3a/')."
        )
    return value + "/"
