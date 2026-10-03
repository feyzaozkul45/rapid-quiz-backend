import pytest


@pytest.mark.django_db
def test_health_ok(client):
    response = client.get("/api/v1/health/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "up"}


def test_health_db_down(client, monkeypatch):
    class BrokenCursor:
        def __enter__(self):
            raise RuntimeError("db down")

        def __exit__(self, *args):
            return False

    monkeypatch.setattr("config.views.connection.cursor", lambda: BrokenCursor())
    response = client.get("/api/v1/health/")
    assert response.status_code == 503
    assert response.json()["status"] == "error"
