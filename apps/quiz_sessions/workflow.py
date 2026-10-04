"""Quiz oturumu akışı (veritabanı işlemleri). Kurallar services.py'dedir."""

from django.db import transaction
from django.utils import timezone
from rest_framework import status

from apps.quiz.models import Question
from config.api_errors import ApiError

from . import services
from .models import QuizSession, SessionAnswer

Status = QuizSession.Status


def _error_session_expired():
    return ApiError("session_expired", "Quiz oturumunun süresi doldu.", status.HTTP_410_GONE)


def _error_session_completed():
    return ApiError("session_completed", "Bu quiz tamamlandı.", status.HTTP_409_CONFLICT)


def _error_session_not_completed():
    return ApiError("session_not_completed", "Quiz henüz bitmedi.", status.HTTP_409_CONFLICT)


def _error_session_not_found():
    return ApiError("session_not_found", "Quiz oturumu bulunamadı.", status.HTTP_404_NOT_FOUND)


def _lock_session(session_id):
    try:
        return (
            QuizSession.objects.select_for_update(of=("self",))
            .select_related("category")
            .get(pk=session_id)
        )
    except QuizSession.DoesNotExist:
        raise _error_session_not_found() from None


def _check_in_progress(session, now):
    """Oturum devam etmiyorsa (veya hareketsizlikten sona erdiyse) hata nesnesi döndürür.

    Hata burada fırlatılmaz: çağıran transaction'dan çıktıktan sonra fırlatır; böylece
    `expired` durum değişikliği geri alınmaz.
    """
    if session.status == Status.IN_PROGRESS and services.is_inactive(session.last_activity_at, now):
        session.status = Status.EXPIRED
        session.save(update_fields=["status"])
    if session.status == Status.EXPIRED:
        return _error_session_expired()
    if session.status == Status.COMPLETED:
        return _error_session_completed()
    return None


def _current_row(session):
    return session.answers.select_related("question").get(position=session.current_index)


def _finish(session, now):
    session.status = Status.COMPLETED
    session.finished_at = now
    session.score = services.calculate_score(session.correct_count)


def _apply_answer(session, row, choice, now):
    """Mevcut soruyu cevaplar (choice=None: cevapsız/süre doldu) ve oturumu ilerletir."""
    choices = list(row.question.choices.all())
    correct = next(c for c in choices if c.is_correct)
    within_time = services.is_within_time(row.served_at, now)
    too_fast = choice is not None and services.is_too_fast(row.served_at, now)
    is_correct = choice is not None and choice.pk == correct.pk
    points = services.points_for_answer(is_correct, within_time, too_fast)
    counted_correct = points > 0

    row.answered_at = now
    # Süre aşıldıysa cevap yok sayılır: seçilen seçenek kaydedilmez (null = süre doldu).
    row.selected_choice = choice if within_time else None
    row.is_correct = counted_correct
    row.points = points
    row.save(update_fields=["answered_at", "selected_choice", "is_correct", "points"])

    session.current_index += 1
    session.last_activity_at = now
    if counted_correct:
        session.correct_count += 1
        session.score += points
    is_last = session.current_index >= services.TOTAL_QUESTIONS
    if is_last:
        _finish(session, now)
    session.save()
    return counted_correct, correct.pk, points, is_last, too_fast


def start_session(category, client_type, recent_question_ids=()):
    ids = list(
        Question.objects.filter(category=category, is_active=True).values_list("id", flat=True)
    )
    if len(ids) < services.TOTAL_QUESTIONS:
        raise ApiError(
            "category_unavailable", "Bu kategoride yeterli soru yok.", status.HTTP_409_CONFLICT
        )
    # Son oynananlar en sona bırakılır; sıra da karışık gelir.
    selected = services.choose_questions(ids, recent_question_ids)
    with transaction.atomic():
        session = QuizSession.objects.create(category=category, client_type=client_type)
        SessionAnswer.objects.bulk_create(
            SessionAnswer(session=session, question_id=qid, position=pos)
            for pos, qid in enumerate(selected)
        )
    return session


def get_current_question(session_id, now=None):
    now = now or timezone.now()
    error = None
    with transaction.atomic():
        session = _lock_session(session_id)
        error = _check_in_progress(session, now)
        if error is None:
            row = _current_row(session)
            # İstemci kaybolduysa süresi geçen soru cevapsız işaretlenir.
            if row.served_at and services.has_timed_out(row.served_at, now):
                _apply_answer(session, row, None, now)
                if session.status == Status.COMPLETED:
                    error = _error_session_completed()
                else:
                    row = _current_row(session)
        if error is None:
            if row.served_at is None:
                row.served_at = now  # aynı soru tekrar istenirse süre yeniden başlamaz
                row.save(update_fields=["served_at"])
            session.last_activity_at = now
            session.save(update_fields=["last_activity_at"])
            payload = {
                "position": row.position,
                "total": services.TOTAL_QUESTIONS,
                "question_id": row.question_id,
                "text": row.question.text,
                "choices": [
                    {"id": c.pk, "text": c.text}
                    for c in services.shuffled_choices(
                        session.pk, row.question_id, row.question.choices.all()
                    )
                ],
                "time_limit_seconds": services.TIME_LIMIT_SECONDS,
                "served_at": row.served_at,
                "remaining_seconds": round(services.remaining_seconds(row.served_at, now), 3),
            }
    if error:
        raise error
    return payload


def submit_answer(session_id, question_id, choice_id, now=None):
    now = now or timezone.now()
    error = None
    with transaction.atomic():
        session = _lock_session(session_id)
        error = _check_in_progress(session, now)
        if error is None:
            row = _current_row(session)
            if row.question_id != question_id:
                raise ApiError(
                    "question_mismatch",
                    "Cevap, sıradaki soruyla eşleşmiyor.",
                    status.HTTP_409_CONFLICT,
                )
            if row.served_at is None:
                raise ApiError(
                    "question_not_served",
                    "Bu soru henüz istemciye gönderilmedi.",
                    status.HTTP_409_CONFLICT,
                )
            choice = None
            if choice_id is not None:
                choice = next((c for c in row.question.choices.all() if c.pk == choice_id), None)
                if choice is None:
                    raise ApiError(
                        "invalid_choice", "Geçersiz seçenek.", status.HTTP_400_BAD_REQUEST
                    )
            is_correct, correct_id, points, is_last, too_fast = _apply_answer(
                session, row, choice, now
            )
            payload = {
                "is_correct": is_correct,
                "correct_choice_id": correct_id,
                "points": points,
                "too_fast": too_fast,
                "is_last": is_last,
                "score_so_far": session.score,
            }
    if error:
        raise error
    return payload


def get_result(session_id):
    try:
        session = QuizSession.objects.select_related("category").get(pk=session_id)
    except QuizSession.DoesNotExist:
        raise _error_session_not_found() from None
    if session.status == Status.EXPIRED:
        raise _error_session_expired()
    if session.status != Status.COMPLETED:
        raise _error_session_not_completed()
    return session


def save_player_name(session_id, raw_name, now=None):
    now = now or timezone.now()
    name = services.normalize_player_name(raw_name)
    message = services.validate_player_name(name)
    if message:
        raise ApiError("name_invalid", message, status.HTTP_400_BAD_REQUEST)
    error = None
    with transaction.atomic():
        session = _lock_session(session_id)
        if session.status == Status.EXPIRED:
            error = _error_session_expired()
        elif session.status != Status.COMPLETED:
            error = _error_session_not_completed()
        elif not services.is_name_window_open(session.finished_at, now):
            error = ApiError(
                "name_window_closed",
                "İsim kaydı için tanınan süre doldu.",
                status.HTTP_410_GONE,
            )
        elif session.player_name is not None:
            error = ApiError(
                "name_already_set",
                "Bu oturum için isim zaten kaydedildi.",
                status.HTTP_409_CONFLICT,
            )
        else:
            session.player_name = name
            session.save(update_fields=["player_name"])
    if error:
        raise error
    return session
