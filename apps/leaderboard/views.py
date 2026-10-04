from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.quiz.models import Category
from apps.quiz_sessions.models import QuizSession
from apps.quiz_sessions.serializers import ErrorSerializer
from config.api_errors import ApiError

from . import queries
from .serializers import LeaderboardQuerySerializer, LeaderboardSerializer


class LeaderboardView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "read"

    @extend_schema(
        summary="Kategori skor tablosu (varsayılan top 10)",
        parameters=[
            OpenApiParameter("category", str, required=True, description="Kategori slug'ı"),
            OpenApiParameter("limit", int, description="1-50 arası, varsayılan 10"),
            OpenApiParameter("session_id", str, description="Kendi satırını vurgulamak için"),
        ],
        responses={200: LeaderboardSerializer, 404: ErrorSerializer},
        tags=["leaderboard"],
    )
    def get(self, request):
        query = LeaderboardQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        params = query.validated_data

        try:
            category = Category.objects.get(slug=params["category"], is_active=True)
        except Category.DoesNotExist:
            raise ApiError(
                "category_not_found", "Kategori bulunamadı.", status.HTTP_404_NOT_FOUND
            ) from None

        my_id = params.get("session_id")
        entries = queries.top_entries(category, params["limit"])
        for entry in entries:
            entry["is_me"] = entry["id"] == my_id
            del entry["id"]

        me = None
        if my_id is not None:
            session = QuizSession.objects.filter(pk=my_id, category=category).first()
            rank = queries.rank_of(session) if session else None
            if rank is not None:
                me = {
                    "rank": rank,
                    "player_name": session.player_name,
                    "score": session.score,
                    "correct_count": session.correct_count,
                    "finished_at": session.finished_at,
                    "is_me": True,
                }

        data = dict(
            LeaderboardSerializer({"category": category.slug, "entries": entries, "me": me}).data
        )
        if my_id is None:
            data.pop("me")  # varsayılan yanıt dokümandaki biçimle birebir aynı kalır
        return Response(data)
