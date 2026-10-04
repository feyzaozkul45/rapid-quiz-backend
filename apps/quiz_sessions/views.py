from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from config.throttles import AnswerSessionThrottle, QuestionSessionThrottle

from . import serializers, services, workflow

ERRORS = {
    404: serializers.ErrorSerializer,
    409: serializers.ErrorSerializer,
    410: serializers.ErrorSerializer,
}
TAG = ["quiz-sessions"]


class QuizSessionCreateView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "quiz_start"

    @extend_schema(
        summary="Yeni quiz oturumu açar",
        request=serializers.StartSessionSerializer,
        responses={201: serializers.SessionCreatedSerializer, 409: serializers.ErrorSerializer},
        tags=TAG,
    )
    def post(self, request):
        body = serializers.StartSessionSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        client_type = (
            body.validated_data.get("client_type")
            or request.headers.get("X-Client-Type", "").lower()
        )
        if client_type not in {"web", "ios", "android"}:
            client_type = "web"
        session = workflow.start_session(
            body.validated_data["category"],
            client_type,
            body.validated_data.get("recent_question_ids", ()),
        )
        data = {
            "session_id": session.id,
            "category": session.category.slug,
            "total_questions": services.TOTAL_QUESTIONS,
            "time_limit_seconds": services.TIME_LIMIT_SECONDS,
        }
        return Response(serializers.SessionCreatedSerializer(data).data, status.HTTP_201_CREATED)


class CurrentQuestionView(APIView):
    throttle_classes = [ScopedRateThrottle, QuestionSessionThrottle]
    throttle_scope = "question"

    @extend_schema(
        summary="Sıradaki soruyu verir (doğru cevap olmadan)",
        responses={200: serializers.CurrentQuestionSerializer, **ERRORS},
        tags=TAG,
    )
    def get(self, request, session_id):
        payload = workflow.get_current_question(session_id)
        return Response(serializers.CurrentQuestionSerializer(payload).data)


class AnswerView(APIView):
    throttle_classes = [ScopedRateThrottle, AnswerSessionThrottle]
    throttle_scope = "answer"

    @extend_schema(
        summary="Mevcut soruya cevap gönderir (süre dolduysa choice_id: null)",
        request=serializers.AnswerRequestSerializer,
        responses={200: serializers.AnswerResultSerializer, **ERRORS},
        tags=TAG,
    )
    def post(self, request, session_id):
        body = serializers.AnswerRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        payload = workflow.submit_answer(
            session_id, body.validated_data["question_id"], body.validated_data["choice_id"]
        )
        return Response(serializers.AnswerResultSerializer(payload).data)


class ResultView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "read"

    @extend_schema(
        summary="Biten quiz'in puan özetini verir",
        responses={200: serializers.ResultSerializer, **ERRORS},
        tags=TAG,
    )
    def get(self, request, session_id):
        session = workflow.get_result(session_id)
        return Response(serializers.ResultSerializer(session).data)


class PlayerNameView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "player_name"

    @extend_schema(
        summary="İsmi kaydeder, skoru tabloya alır (bir kez)",
        request=serializers.PlayerNameRequestSerializer,
        responses={
            200: serializers.PlayerNameResultSerializer,
            400: serializers.ErrorSerializer,
            **ERRORS,
        },
        tags=TAG,
    )
    def patch(self, request, session_id):
        body = serializers.PlayerNameRequestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        session = workflow.save_player_name(session_id, body.validated_data["player_name"])
        return Response(serializers.PlayerNameResultSerializer(session).data)
