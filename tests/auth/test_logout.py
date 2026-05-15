"""Tests for POST /auth/logout.

Covers the Definition of Done items from #14:

* POST /auth/logout for an authenticated session returns 302 to /
* the session cookie no longer authenticates a follow-up request
* GET /auth/logout returns 405 (Method Not Allowed)
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth.tokens import generate_token, hash_token
from app.models import MagicLinkToken


def _sign_in(client: TestClient, session: Session, email: str) -> None:
    """Drive the verify endpoint to set a real signed session cookie on
    the TestClient. After this returns, ``client.cookies['session']`` is
    the Starlette-signed cookie value."""
    raw = generate_token()
    session.add(
        MagicLinkToken(
            email=email,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
    )
    session.commit()
    response = client.get(f"/auth/verify?token={raw}", follow_redirects=False)
    assert response.status_code == 302
    assert client.cookies.get("session"), "verify did not set a session cookie"


def test_logout_redirects_home_for_authenticated_session(
    client: TestClient, session: Session
) -> None:
    _sign_in(client, session, "alice@example.com")

    response = client.post("/auth/logout", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_logout_clears_session_so_followup_is_unauthenticated(
    client: TestClient, session: Session
) -> None:
    """After logout, the index page must NOT render the logout button —
    which is the proxy for 'the session cookie no longer authenticates'."""
    _sign_in(client, session, "alice@example.com")

    # While authenticated, the home page renders the Log out button.
    pre_logout = client.get("/")
    assert "Log out" in pre_logout.text

    client.post("/auth/logout", follow_redirects=False)

    post_logout = client.get("/")
    assert "Log out" not in post_logout.text


def test_get_logout_returns_405(client: TestClient) -> None:
    response = client.get("/auth/logout")
    assert response.status_code == 405


def test_logout_when_anonymous_still_returns_302(client: TestClient) -> None:
    """No active session is a no-op clear; the user lands on / either way.
    A 302 (not 401) avoids leaking auth state via the response code."""
    response = client.post("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"
