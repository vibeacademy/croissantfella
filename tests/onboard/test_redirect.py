"""Tests for RequireTasteProfileMiddleware.

Covers the Definition of Done items from #26:

* an authenticated user without a TasteProfile is redirected from / to
  /onboard
* the same user is NOT redirected from /onboard, /auth/login, the
  health endpoints, or /static/foo
* an anonymous user is NOT redirected (route handles auth itself)
* an authenticated user WITH a TasteProfile is NOT redirected
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.auth.tokens import generate_token, hash_token
from app.models import FormLength, Genre, MagicLinkToken, TasteProfile, Tone, User


def _sign_in(client: TestClient, session: Session, email: str) -> User:
    """Drive /auth/verify to set a session cookie. Returns the User row
    so the test can decide whether to give it a TasteProfile."""
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
    user = session.exec(
        User.__table__.select().where(User.__table__.c.email == email)  # type: ignore[attr-defined]
    ).first()
    assert user is not None
    return User(**user._asdict()) if not isinstance(user, User) else user


def _attach_taste_profile(session: Session, user_id) -> None:
    session.add(
        TasteProfile(
            user_id=user_id,
            genres=[Genre.LITERARY.value],
            tones=[Tone.CONTEMPLATIVE.value],
            form_lengths=[FormLength.FLASH.value],
        )
    )
    session.commit()


def test_authenticated_user_without_profile_redirected_from_home(
    client: TestClient, session: Session
) -> None:
    _sign_in(client, session, "newcomer@example.com")
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/onboard"


def test_authenticated_user_with_profile_not_redirected(
    client: TestClient, session: Session
) -> None:
    _sign_in(client, session, "returner@example.com")
    user = session.exec(
        User.__table__.select().where(User.__table__.c.email == "returner@example.com")  # type: ignore[attr-defined]
    ).one()
    _attach_taste_profile(session, user.id)

    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200


def test_anonymous_user_not_redirected(client: TestClient) -> None:
    """No session cookie → middleware passes through. The home route
    is the public landing page, so anonymous gets 200."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200


def test_no_redirect_on_onboard_path(client: TestClient, session: Session) -> None:
    _sign_in(client, session, "newcomer@example.com")
    response = client.get("/onboard", follow_redirects=False)
    # Without the exemption this would be 302 → /onboard (loop). With
    # the exemption, the /onboard route runs and returns 200.
    assert response.status_code == 200


def test_no_redirect_on_auth_paths(client: TestClient, session: Session) -> None:
    _sign_in(client, session, "newcomer@example.com")
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 200


def test_no_redirect_on_health_paths(client: TestClient, session: Session) -> None:
    _sign_in(client, session, "newcomer@example.com")
    response = client.get("/api/health", follow_redirects=False)
    assert response.status_code == 200


def test_no_redirect_on_static_paths(client: TestClient, session: Session) -> None:
    _sign_in(client, session, "newcomer@example.com")
    # A non-existent static file still goes through the StaticFiles
    # mount; the middleware exempts the prefix so the StaticFiles 404
    # is the response (not the /onboard redirect).
    response = client.get("/static/no-such-file.css", follow_redirects=False)
    assert response.status_code == 404
    # Critically, it's NOT a redirect to /onboard.
    assert response.headers.get("location") != "/onboard"


def test_no_redirect_on_logout_endpoint(client: TestClient, session: Session) -> None:
    """Authenticated user without profile clicks Log out. Middleware
    must NOT intercept (/auth/* is exempt); the logout handler does its
    own session.clear() then redirects to /."""
    _sign_in(client, session, "newcomer@example.com")
    response = client.post("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_anonymous_on_static_is_not_redirected(client: TestClient) -> None:
    """Defensive: anonymous + exempt path should pass through cleanly."""
    response = client.get("/api/health", follow_redirects=False)
    assert response.status_code == 200
