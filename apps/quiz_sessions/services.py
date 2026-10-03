"""Puanlama, süre ve isim kuralları: saf fonksiyonlar (veritabanına dokunmaz).

Puan ve süre hesabı yalnızca bu modülde yapılır (docs/PROJECT.md Bölüm 7).
"""

import unicodedata
from datetime import timedelta

TOTAL_QUESTIONS = 20
TIME_LIMIT_SECONDS = 5
TOLERANCE_SECONDS = 1
POINTS_PER_CORRECT = 100
MAX_SCORE = TOTAL_QUESTIONS * POINTS_PER_CORRECT
INACTIVITY_LIMIT = timedelta(minutes=10)

PLAYER_NAME_MIN = 2
PLAYER_NAME_MAX = 20

_ANSWER_DEADLINE = timedelta(seconds=TIME_LIMIT_SECONDS + TOLERANCE_SECONDS)


def is_within_time(served_at, answered_at):
    """Cevap, sunucunun soruyu gönderdiği andan itibaren 6 sn (5 + 1 tolerans) içinde mi geldi?"""
    return answered_at - served_at <= _ANSWER_DEADLINE


def has_timed_out(served_at, now):
    """Bu soru için cevap hakkı (tolerans dahil) bitti mi?"""
    return now - served_at > _ANSWER_DEADLINE


def remaining_seconds(served_at, now):
    """İstemcinin gösterebileceği kalan süre (0 ile 5 sn arası); yalnızca bilgilendirme amaçlı."""
    left = TIME_LIMIT_SECONDS - (now - served_at).total_seconds()
    return max(0.0, min(float(TIME_LIMIT_SECONDS), left))


def is_inactive(last_activity_at, now):
    return now - last_activity_at > INACTIVITY_LIMIT


def points_for_answer(is_correct, within_time):
    return POINTS_PER_CORRECT if is_correct and within_time else 0


def calculate_score(correct_count):
    return POINTS_PER_CORRECT * correct_count


def normalize_player_name(raw):
    """NFC, baştaki/sondaki boşlukları kırp, art arda boşlukları teke indir."""
    return " ".join(unicodedata.normalize("NFC", raw).split())


def validate_player_name(name):
    """Normalize edilmiş isim için hata mesajı döndürür; geçerliyse None."""
    if not PLAYER_NAME_MIN <= len(name) <= PLAYER_NAME_MAX:
        return f"İsim {PLAYER_NAME_MIN}-{PLAYER_NAME_MAX} karakter olmalıdır."
    if not all(ch.isalnum() or ch in " -" for ch in name):
        return "İsim yalnızca harf, rakam, boşluk ve tire içerebilir."
    if not any(ch.isalnum() for ch in name):
        return "İsim en az bir harf veya rakam içermelidir."
    return None
