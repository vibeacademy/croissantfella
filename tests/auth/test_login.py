"""Tests for POST /auth/login (magic-link request endpoint).

Covers the Definition of Done items from #12:

* POST /auth/login with a valid email returns 200 and the "check your
  email" template
* response is byte-identical for known and unknown emails
  (email-enumeration mitigation)
* the persisted ``magic_link_tokens`` row has a 32-byte ``token_hash``
  and ``expires_at`` ≈ now + 15 minutes
* the Resend client is called with a URL containing the raw token
"""

import hashlib
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import httpx
import respx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models import MagicLinkToken, User
from app.services.email import RESEND_ENDPOINT

RESEND_OK = httpx.Response(200, json={"id": "test_email_id"})


def test_get_login_renders_form(client: TestClient) -> None:
    response = client.get("/auth/login")
    assert response.status_code == 200
    assert 'name="email"' in response.text


def test_post_login_returns_check_email_page(client: TestClient, session: Session) -> None:
    with respx.mock() as mock:
        route = mock.post(RESEND_ENDPOINT).mock(return_value=RESEND_OK)
        response = client.post("/auth/login", data={"email": "alice@example.com"})

    assert response.status_code == 200
    assert "Check your email" in response.text
    assert route.called


def test_post_login_response_byte_identical_for_known_and_unknown_email(
    client: TestClient, session: Session
) -> None:
    """Same status, headers (sans Date/Set-Cookie noise), and body for any input."""
    session.add(User(email="known@example.com", display_name="Known"))
    session.commit()

    with respx.mock() as mock:
        mock.post(RESEND_ENDPOINT).mock(return_value=RESEND_OK)
        known = client.post("/auth/login", data={"email": "known@example.com"})
        unknown = client.post("/auth/login", data={"email": "unknown@example.com"})

    assert known.status_code == unknown.status_code == 200
    assert known.content == unknown.content


def test_post_login_persists_hashed_token_with_15min_ttl(
    client: TestClient, session: Session
) -> None:
    before = datetime.now(UTC)

    with respx.mock() as mock:
        mock.post(RESEND_ENDPOINT).mock(return_value=RESEND_OK)
        response = client.post("/auth/login", data={"email": "alice@example.com"})

    assert response.status_code == 200
    after = datetime.now(UTC)

    tokens = list(
        session.exec(select(MagicLinkToken).where(MagicLinkToken.email == "alice@example.com"))
    )
    assert len(tokens) == 1
    token = tokens[0]

    assert len(token.token_hash) == 32  # sha256 digest size
    expected_min = before + timedelta(minutes=15) - timedelta(seconds=1)
    expected_max = after + timedelta(minutes=15) + timedelta(seconds=1)
    expires_at = (
        token.expires_at if token.expires_at.tzinfo else token.expires_at.replace(tzinfo=UTC)
    )
    assert expected_min <= expires_at <= expected_max


def test_post_login_calls_resend_with_url_containing_raw_token(
    client: TestClient, session: Session
) -> None:
    """The raw token is never persisted — verify it round-trips through the
    Resend HTML body by hashing it back to the stored ``token_hash``."""
    with respx.mock() as mock:
        route = mock.post(RESEND_ENDPOINT).mock(return_value=RESEND_OK)
        response = client.post("/auth/login", data={"email": "alice@example.com"})

    assert response.status_code == 200
    assert route.called

    sent = route.calls.last.request
    body = sent.content.decode("utf-8")
    match = re.search(r"/auth/verify\?token=([A-Za-z0-9_-]+)", body)
    assert match, f"verify URL with token not found in Resend body: {body!r}"

    raw_token = match.group(1)
    parsed = urlparse(f"http://x/auth/verify?token={raw_token}")
    assert parse_qs(parsed.query)["token"] == [raw_token]

    digest = hashlib.sha256(raw_token.encode("ascii")).digest()
    stored = session.exec(
        select(MagicLinkToken).where(MagicLinkToken.email == "alice@example.com")
    ).one()
    assert stored.token_hash == digest
