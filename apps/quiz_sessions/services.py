"""Puanlama, süre ve isim kuralları: saf fonksiyonlar (veritabanına dokunmaz).

Puan ve süre hesabı yalnızca bu modülde yapılır (docs/PROJECT.md Bölüm 7).
"""

import random
import unicodedata
from datetime import timedelta

TOTAL_QUESTIONS = 20
TIME_LIMIT_SECONDS = 5
TOLERANCE_SECONDS = 1
MIN_ANSWER_SECONDS = 0.3  # bundan hızlı cevap insan tepkisi değildir: puansız sayılır
MAX_RECENT_QUESTION_IDS = 40
POINTS_PER_CORRECT = 100
MAX_SCORE = TOTAL_QUESTIONS * POINTS_PER_CORRECT
INACTIVITY_LIMIT = timedelta(minutes=10)
NAME_WINDOW = timedelta(minutes=30)  # quiz bitiminden sonra isim kaydı için tanınan süre

PLAYER_NAME_MIN = 2
PLAYER_NAME_MAX = 20

_ANSWER_DEADLINE = timedelta(seconds=TIME_LIMIT_SECONDS + TOLERANCE_SECONDS)
_MIN_ANSWER_TIME = timedelta(seconds=MIN_ANSWER_SECONDS)


def is_within_time(served_at, answered_at):
    """Cevap, sunucunun soruyu gönderdiği andan itibaren 6 sn (5 + 1 tolerans) içinde mi geldi?"""
    return answered_at - served_at <= _ANSWER_DEADLINE


def is_too_fast(served_at, answered_at):
    """Cevap, soru gönderildikten sonra 300 ms dolmadan mı geldi? (bot/otomasyon işareti)"""
    return answered_at - served_at < _MIN_ANSWER_TIME


def has_timed_out(served_at, now):
    """Bu soru için cevap hakkı (tolerans dahil) bitti mi?"""
    return now - served_at > _ANSWER_DEADLINE


def remaining_seconds(served_at, now):
    """İstemcinin gösterebileceği kalan süre (0 ile 5 sn arası); yalnızca bilgilendirme amaçlı."""
    left = TIME_LIMIT_SECONDS - (now - served_at).total_seconds()
    return max(0.0, min(float(TIME_LIMIT_SECONDS), left))


def is_inactive(last_activity_at, now):
    return now - last_activity_at > INACTIVITY_LIMIT


def is_name_window_open(finished_at, now):
    return now - finished_at <= NAME_WINDOW


def points_for_answer(is_correct, within_time, too_fast=False):
    return POINTS_PER_CORRECT if is_correct and within_time and not too_fast else 0


def choose_questions(available_ids, recent_ids, count=TOTAL_QUESTIONS, rng=random):
    """Quiz için soru seçer; son oynananlar (recent_ids) en sona bırakılır.

    Önce `recent_ids` içinde olmayan sorulardan rastgele seçilir. Bunlar yetmezse kalan yer, son
    oynananlardan en eskiden başlayarak tamamlanır (recent_ids eskiden yeniye sıralıdır). Havuzda
    bulunmayan ID'ler ve tekrarlar yok sayılır. Dönen liste karışıktır.
    """
    available = list(available_ids)
    in_pool = set(available)
    recent = list(dict.fromkeys(i for i in recent_ids if i in in_pool))
    recent_set = set(recent)
    fresh = [i for i in available if i not in recent_set]
    if len(fresh) >= count:
        chosen = rng.sample(fresh, count)
    else:
        chosen = fresh + recent[: count - len(fresh)]
    rng.shuffle(chosen)
    return chosen


def shuffled_choices(session_id, question_id, choices):
    """Seçenekleri oturum ve soruya özgü, yeniden istendiğinde değişmeyen bir sıraya sokar."""
    ordered = sorted(choices, key=lambda c: c.pk)
    random.Random(f"{session_id}:{question_id}").shuffle(ordered)
    return ordered


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
