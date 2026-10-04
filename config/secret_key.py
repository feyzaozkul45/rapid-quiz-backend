from django.core.exceptions import ImproperlyConfigured

MIN_LENGTH = 50
MIN_UNIQUE_CHARS = 5
# .env.example / geliştirme varsayılanı gibi örnek değerlerin production'a sızmasını engeller.
WEAK_MARKERS = ("insecure", "change-me", "changeme")


def validate_secret_key(key):
    """Production SECRET_KEY'ini doğrular; zayıfsa ImproperlyConfigured fırlatır, anahtarı döndürür.

    Kurallar Django'nun `check --deploy` (W009) denetimiyle uyumludur: en az 50 karakter ve en az
    5 farklı karakter. Ek olarak bilinen örnek/varsayılan değerler reddedilir. Anahtarın kendisi
    hata mesajına yazılmaz.
    """
    key = key or ""
    problems = []
    if len(key) < MIN_LENGTH:
        problems.append(f"en az {MIN_LENGTH} karakter olmalı (şu an {len(key)})")
    if len(set(key)) < MIN_UNIQUE_CHARS:
        problems.append(f"en az {MIN_UNIQUE_CHARS} farklı karakter içermeli")
    lowered = key.lower()
    if any(marker in lowered for marker in WEAK_MARKERS):
        problems.append("örnek/varsayılan bir değer içeriyor")
    if problems:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY güvenli değil: "
            + "; ".join(problems)
            + '. Üretmek için: python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )
    return key
