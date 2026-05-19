"""Tests for GET /u/{display_name} — public profile page.

Covers the Definition of Done items from #16:

* GET /u/{name} returns 200 for an existing user with posts, and the
  response HTML contains each published post's title
* ``pending_moderation`` and ``blocked`` posts are NOT in the response
* GET /u/UNKNOWN returns 404
* the response does not contain the user's email
* case-insensitive lookup redirects to the canonical case
"""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.models import ContentStatus, FormLength, Genre, Post, Tone, User


def _make_post(
    session: Session,
    *,
    author: User,
    title: str,
    status: str,
    published_at: datetime | None = None,
    body: str = "Some text.",
) -> Post:
    post = Post(
        author_id=author.id,
        title=title,
        body=body,
        genres=[Genre.LITERARY.value],
        tones=[Tone.CONTEMPLATIVE.value],
        form_length=FormLength.FLASH.value,
        status=status,
        published_at=published_at,
    )
    session.add(post)
    session.commit()
    session.refresh(post)
    return post


def _make_user(session: Session, *, email: str, display_name: str) -> User:
    user = User(email=email, display_name=display_name)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def test_profile_returns_200_with_published_post_titles(
    client: TestClient, session: Session
) -> None:
    alice = _make_user(session, email="alice@example.com", display_name="Alice")
    _make_post(
        session,
        author=alice,
        title="First Story",
        status=ContentStatus.PUBLISHED.value,
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    _make_post(
        session,
        author=alice,
        title="Second Story",
        status=ContentStatus.PUBLISHED.value,
        published_at=datetime(2026, 5, 2, tzinfo=UTC),
    )

    response = client.get("/u/Alice")
    assert response.status_code == 200
    assert "First Story" in response.text
    assert "Second Story" in response.text


def test_profile_omits_pending_and_blocked_posts(client: TestClient, session: Session) -> None:
    alice = _make_user(session, email="alice@example.com", display_name="Alice")
    _make_post(
        session,
        author=alice,
        title="Published Story",
        status=ContentStatus.PUBLISHED.value,
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    _make_post(
        session,
        author=alice,
        title="Pending Story",
        status=ContentStatus.PENDING_MODERATION.value,
    )
    _make_post(
        session,
        author=alice,
        title="Blocked Story",
        status=ContentStatus.BLOCKED.value,
    )

    response = client.get("/u/Alice")
    assert response.status_code == 200
    assert "Published Story" in response.text
    assert "Pending Story" not in response.text
    assert "Blocked Story" not in response.text


def test_unknown_user_returns_404(client: TestClient, session: Session) -> None:
    response = client.get("/u/nobody-here")
    assert response.status_code == 404


def test_profile_does_not_leak_email(client: TestClient, session: Session) -> None:
    _make_user(session, email="alice@example.com", display_name="Alice")
    response = client.get("/u/Alice")
    assert response.status_code == 200
    assert "alice@example.com" not in response.text


def test_profile_does_not_leak_user_uuid(client: TestClient, session: Session) -> None:
    """Internal IDs are an architecture guardrail: profile HTML must
    not include the user's UUID even though Post links use post.id."""
    alice = _make_user(session, email="alice@example.com", display_name="Alice")
    response = client.get("/u/Alice")
    assert str(alice.id) not in response.text


def test_case_insensitive_lookup_redirects_to_canonical(
    client: TestClient, session: Session
) -> None:
    _make_user(session, email="alice@example.com", display_name="Alice")

    response = client.get("/u/alice", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/u/Alice"


def test_anonymous_can_view_profile(client: TestClient, session: Session) -> None:
    """No sign-in required; auth-less browsers reach the page."""
    _make_user(session, email="alice@example.com", display_name="Alice")
    response = client.get("/u/Alice")
    assert response.status_code == 200
    # The session-conditional Log out button in base.html must NOT appear
    # for an anonymous visitor.
    assert "Log out" not in response.text


def test_profile_post_link_uses_post_uuid(client: TestClient, session: Session) -> None:
    alice = _make_user(session, email="alice@example.com", display_name="Alice")
    post = _make_post(
        session,
        author=alice,
        title="A Story",
        status=ContentStatus.PUBLISHED.value,
        published_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    response = client.get("/u/Alice")
    assert f"/posts/{post.id}" in response.text
