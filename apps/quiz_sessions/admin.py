from django.contrib import admin

from .models import QuizSession


@admin.register(QuizSession)
class QuizSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "category", "status", "score", "player_name", "started_at")
    list_filter = ("category", "status", "client_type")
    readonly_fields = [f.name for f in QuizSession._meta.fields]
