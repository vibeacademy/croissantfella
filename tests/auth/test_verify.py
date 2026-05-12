"""Tests for GET /auth/verify (magic-link consume + session start).

Covers the Definition of Done items from #13:

* a fresh token logs in and sets a session cookie with the right attributes
* the token row is deleted after a successful verify
* re-using the same token returns 410
* an expired token returns 410
* first-time verify creates a User row and redirects to /onboard
* a returning verify (existing TasteProfile) redirects to /
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.tokens import generate_token, hash_token
from app.models import MagicLinkToken, TasteProfile, User


def _mint_token(
    session: Session,
    email: str,
    *,
    expires_in: timedelta = timedelta(minutes=15),
) -> str:
    raw = generate_token()
    session.add(
        MagicLinkToken(
            email=email,
            token_hash=hash_token(raw),
            expires_at=datetime.now(UTC) + expires_in,
        )
    )
    session.commit()
    return raw


def test_verify_fresh_token_sets_signed_session_cookie(
    client: TestClient, session: Session
) -> None:
    raw = _mint_token(session, "alice@example.com")

    response = client.get(f"/auth/verify?token={raw}", follow_redirects=False)

    assert response.status_code == 302
    set_cookie = response.headers["set-cookie"]
    lowered = set_cookie.lower()
    assert "session=" in set_cookie
    assert "httponly" in lowered
    assert "secure" in lowered
    assert "samesite=lax" in lowered


def test_verify_deletes_token_row(client: TestClient, session: Session) -> None:
    raw = _mint_token(session, "alice@example.com")

    client.get(f"/auth/verify?token={raw}", follow_redirects=False)

    rows = list(
        session.exec(select(MagicLinkToken).where(MagicLinkToken.email == "alice@example.com"))
    )
    assert rows == []


def test_verify_reused_token_returns_410(client: TestClient, session: Session) -> None:
    raw = _mint_token(session, "alice@example.com")

    first = client.get(f"/auth/verify?token={raw}", follow_redirects=False)
    assert first.status_code == 302

    # A fresh TestClient avoids re-sending the session cookie set by the
    # first call — the second verify is a clean replay attempt.
    replay = TestClient(client.app)
    second = replay.get(f"/auth/verify?token={raw}", follow_redirects=False)
    assert second.status_code == 410
    assert "expired" in second.text.lower()


def test_verify_expired_token_returns_410(client: TestClient, session: Session) -> None:
    raw = _mint_token(session, "alice@example.com", expires_in=timedelta(minutes=-1))

    response = client.get(f"/auth/verify?token={raw}", follow_redirects=False)

    assert response.status_code == 410
    # Expired rows are deleted on the spot so a clock-skewed attacker
    # can't distinguish "expired" from "never existed".
    rows = list(
        session.exec(select(MagicLinkToken).where(MagicLinkToken.email == "alice@example.com"))
    )
    assert rows == []


def test_verify_first_time_creates_user_and_redirects_to_onboard(
    client: TestClient, session: Session
) -> None:
    raw = _mint_token(session, "newcomer@example.com")

    response = client.get(f"/auth/verify?token={raw}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/onboard"
    user = session.exec(select(User).where(User.email == "newcomer@example.com")).one()
    assert user.display_name == "newcomer"


def test_verify_returning_user_with_profile_redirects_to_home(
    client: TestClient, session: Session
) -> None:
    user = User(email="returning@example.com", display_name="Returning")
    session.add(user)
    session.commit()
    session.refresh(user)
    session.add(TasteProfile(user_id=user.id, genres=[], tones=[], form_lengths=[]))
    session.commit()

    raw = _mint_token(session, "returning@example.com")

    response = client.get(f"/auth/verify?token={raw}", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/"


def test_verify_unknown_token_returns_410(client: TestClient, session: Session) -> None:
    response = client.get("/auth/verify?token=this-token-was-never-minted", follow_redirects=False)
    assert response.status_code == 410


def test_verify_missing_token_query_returns_410(client: TestClient) -> None:
    response = client.get("/auth/verify", follow_redirects=False)
    assert response.status_code == 410
