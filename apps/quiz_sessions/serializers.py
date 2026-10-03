from rest_framework import serializers

from apps.quiz.models import Category

from . import services
from .models import QuizSession


class ErrorBodySerializer(serializers.Serializer):
    code = serializers.CharField()
    message = serializers.CharField()


class ErrorSerializer(serializers.Serializer):
    error = ErrorBodySerializer()


class StartSessionSerializer(serializers.Serializer):
    category = serializers.SlugRelatedField(
        slug_field="slug", queryset=Category.objects.filter(is_active=True)
    )
    client_type = serializers.ChoiceField(choices=QuizSession.ClientType.choices, required=False)


class SessionCreatedSerializer(serializers.Serializer):
    session_id = serializers.UUIDField()
    category = serializers.CharField()
    total_questions = serializers.IntegerField()
    time_limit_seconds = serializers.IntegerField()


class ChoiceOutSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    text = serializers.CharField()


class CurrentQuestionSerializer(serializers.Serializer):
    position = serializers.IntegerField()
    total = serializers.IntegerField()
    question_id = serializers.IntegerField()
    text = serializers.CharField()
    choices = ChoiceOutSerializer(many=True)
    time_limit_seconds = serializers.IntegerField()
    served_at = serializers.DateTimeField()
    remaining_seconds = serializers.FloatField()


class AnswerRequestSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    choice_id = serializers.IntegerField(allow_null=True)


class AnswerResultSerializer(serializers.Serializer):
    is_correct = serializers.BooleanField()
    correct_choice_id = serializers.IntegerField()
    points = serializers.IntegerField()
    is_last = serializers.BooleanField()
    score_so_far = serializers.IntegerField()


class ResultSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(source="id")
    category = serializers.CharField(source="category.slug")
    status = serializers.CharField()
    score = serializers.IntegerField()
    correct_count = serializers.IntegerField()
    total_questions = serializers.SerializerMethodField()
    max_score = serializers.SerializerMethodField()
    player_name = serializers.CharField(allow_null=True)
    finished_at = serializers.DateTimeField()

    def get_total_questions(self, obj) -> int:
        return services.TOTAL_QUESTIONS

    def get_max_score(self, obj) -> int:
        return services.MAX_SCORE


class PlayerNameRequestSerializer(serializers.Serializer):
    # Uzunluk/karakter kontrolü services.validate_player_name'de (name_invalid hata kodu için).
    player_name = serializers.CharField(trim_whitespace=False, allow_blank=True, max_length=200)


class PlayerNameResultSerializer(serializers.Serializer):
    session_id = serializers.UUIDField(source="id")
    category = serializers.CharField(source="category.slug")
    player_name = serializers.CharField()
    score = serializers.IntegerField()
    correct_count = serializers.IntegerField()
