from rest_framework import serializers

MAX_LIMIT = 50
DEFAULT_LIMIT = 10


class LeaderboardQuerySerializer(serializers.Serializer):
    category = serializers.SlugField()
    limit = serializers.IntegerField(
        required=False, min_value=1, max_value=MAX_LIMIT, default=DEFAULT_LIMIT
    )
    # Kullanıcının kendi satırını vurgulamak için (isteğe bağlı).
    session_id = serializers.UUIDField(required=False)


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    player_name = serializers.CharField()
    score = serializers.IntegerField()
    correct_count = serializers.IntegerField()
    finished_at = serializers.DateTimeField()
    is_me = serializers.BooleanField(required=False)


class LeaderboardSerializer(serializers.Serializer):
    category = serializers.CharField()
    entries = LeaderboardEntrySerializer(many=True)
    me = LeaderboardEntrySerializer(
        allow_null=True,
        required=False,
        help_text="Yalnızca session_id verildiyse ve oturum tabloda yer alıyorsa dolu gelir.",
    )
