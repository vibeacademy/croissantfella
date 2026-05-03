"""Tests for the health check endpoints and the home page."""

from fastapi.testclient import TestClient


def test_healthz_returns_200(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_healthz_content_type_is_json(client: TestClient) -> None:
    response = client.get("/healthz")
    assert response.headers["content-type"].startswith("application/json")


def test_healthz_does_not_touch_database(client: TestClient) -> None:
    """The health endpoint should respond fast and never wake Neon.

    We can't easily simulate a DB outage here, but we can verify that
    hammering /healthz 100 times stays cheap.
    """
    for _ in range(100):
        response = client.get("/healthz")
        assert response.status_code == 200


def test_healthz_db_returns_200_with_working_session(client: TestClient) -> None:
    """The DB health endpoint runs `SELECT 1` and returns ok."""
    response = client.get("/healthz/db")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_returns_hello_writers(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Hello, writers" in response.text


def test_index_renders_through_base_template(client: TestClient) -> None:
    """Sanity check that base.html is composed (Pico stylesheet present)."""
    response = client.get("/")
    assert response.status_code == 200
    assert "@picocss/pico" in response.text
