"""Tests for GET/POST /onboard.

Covers the Definition of Done items from #25:

* POST /onboard with valid taxonomy values creates a TasteProfile and
  redirects to /
* a second POST UPSERTs (does not error or duplicate)
* an unknown taxonomy value returns 422
* POST with empty genres returns 422
* an anonymous request returns 302 to /auth/login
"""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.tokens import generate_token, hash_token
from app.models import FormLength, Genre, MagicLinkToken, TasteProfile, Tone


def _sign_in(client: TestClient, session: Session, email: str) -> None:
    """Drive /auth/verify to set a real session cookie on the TestClient."""
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


def test_get_onboard_redirects_anonymous_to_login(client: TestClient) -> None:
    response = client.get("/onboard", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"


def test_post_onboard_redirects_anonymous_to_login(client: TestClient) -> None:
    response = client.post(
        "/onboard",
        data={"genres": [Genre.LITERARY.value]},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/auth/login"


def test_get_onboard_renders_form_for_authenticated_user(
    client: TestClient, session: Session
) -> None:
    _sign_in(client, session, "alice@example.com")
    response = client.get("/onboard")
    assert response.status_code == 200
    # Every enum value should appear as a checkbox.
    for g in Genre:
        assert f'value="{g.value}"' in response.text
    for t in Tone:
        assert f'value="{t.value}"' in response.text
    for fl in FormLength:
        assert f'value="{fl.value}"' in response.text


def test_post_onboard_creates_taste_profile_and_redirects_home(
    client: TestClient, session: Session
) -> None:
    _sign_in(client, session, "alice@example.com")
    response = client.post(
        "/onboard",
        data={
            "genres": [Genre.LITERARY.value, Genre.SCI_FI.value],
            "tones": [Tone.CONTEMPLATIVE.value],
            "form_lengths": [FormLength.SHORT_STORY.value],
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"

    profiles = list(session.exec(select(TasteProfile)))
    assert len(profiles) == 1
    assert sorted(profiles[0].genres) == sorted([Genre.LITERARY.value, Genre.SCI_FI.value])
    assert profiles[0].tones == [Tone.CONTEMPLATIVE.value]
    assert profiles[0].form_lengths == [FormLength.SHORT_STORY.value]


def test_post_onboard_upserts_on_second_submit(client: TestClient, session: Session) -> None:
    _sign_in(client, session, "alice@example.com")
    client.post(
        "/onboard",
        data={"genres": [Genre.LITERARY.value]},
        follow_redirects=False,
    )
    response = client.post(
        "/onboard",
        data={"genres": [Genre.FANTASY.value, Genre.HORROR.value]},
        follow_redirects=False,
    )
    assert response.status_code == 302
    # SQLAlchemy session may have stale cache from the first commit;
    # expire_all() forces the next query to hit the DB.
    session.expire_all()
    profiles = list(session.exec(select(TasteProfile)))
    assert len(profiles) == 1
    assert sorted(profiles[0].genres) == sorted([Genre.FANTASY.value, Genre.HORROR.value])


def test_post_onboard_with_empty_genres_returns_422(client: TestClient, session: Session) -> None:
    _sign_in(client, session, "alice@example.com")
    response = client.post(
        "/onboard",
        data={"genres": []},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_post_onboard_with_unknown_genre_returns_422(client: TestClient, session: Session) -> None:
    _sign_in(client, session, "alice@example.com")
    response = client.post(
        "/onboard",
        data={"genres": ["not-a-real-genre"]},
        follow_redirects=False,
    )
    assert response.status_code == 422


def test_post_onboard_with_unknown_tone_returns_422(client: TestClient, session: Session) -> None:
    _sign_in(client, session, "alice@example.com")
    response = client.post(
        "/onboard",
        data={
            "genres": [Genre.LITERARY.value],
            "tones": ["definitely-not-a-tone"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 422
