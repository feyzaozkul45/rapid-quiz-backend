"""CORS, gzip ve OpenAPI şeması."""

import pytest

from .factories import make_category

ORIGIN = "http://localhost:5173"


@pytest.mark.django_db
def test_cors_preflight_allows_client_headers(client, settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    response = client.options(
        "/api/v1/quiz-sessions/",
        headers={
            "Origin": ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-client-type,x-client-version",
        },
    )
    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == ORIGIN
    allowed = response["Access-Control-Allow-Headers"].lower()
    assert "x-client-type" in allowed
    assert "x-client-version" in allowed


@pytest.mark.django_db
def test_cors_blocks_unknown_origin(client, settings):
    settings.CORS_ALLOWED_ORIGINS = [ORIGIN]
    response = client.get("/api/v1/categories/", headers={"Origin": "https://evil.example"})
    assert "Access-Control-Allow-Origin" not in response


@pytest.mark.django_db
def test_responses_are_gzipped_when_large(client):
    for _ in range(30):
        make_category(0, description="uzun açıklama " * 20)
    response = client.get("/api/v1/categories/", headers={"Accept-Encoding": "gzip"})
    assert response["Content-Encoding"] == "gzip"


@pytest.mark.django_db
def test_openapi_schema_lists_all_endpoints(client):
    response = client.get("/api/schema/", headers={"Accept": "application/vnd.oai.openapi+json"})
    assert response.status_code == 200
    paths = response.json()["paths"]
    expected = {
        "/api/v1/categories/",
        "/api/v1/quiz-sessions/",
        "/api/v1/quiz-sessions/{session_id}/current-question/",
        "/api/v1/quiz-sessions/{session_id}/answers/",
        "/api/v1/quiz-sessions/{session_id}/result/",
        "/api/v1/quiz-sessions/{session_id}/player-name/",
        "/api/v1/leaderboard/",
    }
    assert expected <= set(paths)


@pytest.mark.django_db
def test_swagger_docs_page(client):
    assert client.get("/api/docs/").status_code == 200
