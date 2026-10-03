from django.urls import path

from . import views

urlpatterns = [
    path("quiz-sessions/", views.QuizSessionCreateView.as_view(), name="session-create"),
    path(
        "quiz-sessions/<uuid:session_id>/current-question/",
        views.CurrentQuestionView.as_view(),
        name="session-current-question",
    ),
    path(
        "quiz-sessions/<uuid:session_id>/answers/",
        views.AnswerView.as_view(),
        name="session-answer",
    ),
    path(
        "quiz-sessions/<uuid:session_id>/result/",
        views.ResultView.as_view(),
        name="session-result",
    ),
    path(
        "quiz-sessions/<uuid:session_id>/player-name/",
        views.PlayerNameView.as_view(),
        name="session-player-name",
    ),
]
