"""Tests for the magic-link rate limiter.

Covers the Definition of Done items from #15:

* the 6th send to the same email within an hour does NOT call Resend
* the 21st send from the same IP within an hour does NOT call Resend
* the response body and status are identical whether the limit was
  hit or not (enumeration-safety preservation)
"""

import httpx
import respx
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth.rate_limit import (
    EMAIL_LIMIT_PER_HOUR,
    IP_LIMIT_PER_HOUR,
    FixedBucketRateLimiter,
)
from app.models import MagicLinkToken
from app.services.email import RESEND_ENDPOINT

RESEND_OK = httpx.Response(200, json={"id": "test_email_id"})


def test_email_limit_blocks_sixth_send(client: TestClient, session: Session) -> None:
    """5 sends to the same email succeed; the 6th is suppressed."""
    with respx.mock() as mock:
        route = mock.post(RESEND_ENDPOINT).mock(return_value=RESEND_OK)
        for _ in range(EMAIL_LIMIT_PER_HOUR):
            response = client.post("/auth/login", data={"email": "alice@example.com"})
            assert response.status_code == 200
        assert route.call_count == EMAIL_LIMIT_PER_HOUR

        suppressed = client.post("/auth/login", data={"email": "alice@example.com"})

    assert suppressed.status_code == 200
    assert route.call_count == EMAIL_LIMIT_PER_HOUR  # Resend NOT called the 6th time

    tokens = list(
        session.exec(select(MagicLinkToken).where(MagicLinkToken.email == "alice@example.com"))
    )
    # Token rows are only inserted when the email actually sends.
    assert len(tokens) == EMAIL_LIMIT_PER_HOUR


def test_ip_limit_blocks_twentyfirst_send(client: TestClient, session: Session) -> None:
    """20 sends from one IP (across different emails) succeed; the 21st
    is suppressed even though no individual email is over its own limit."""
    with respx.mock() as mock:
        route = mock.post(RESEND_ENDPOINT).mock(return_value=RESEND_OK)
        for i in range(IP_LIMIT_PER_HOUR):
            response = client.post("/auth/login", data={"email": f"user{i}@example.com"})
            assert response.status_code == 200
        assert route.call_count == IP_LIMIT_PER_HOUR

        suppressed = client.post("/auth/login", data={"email": "user-extra@example.com"})

    assert suppressed.status_code == 200
    assert route.call_count == IP_LIMIT_PER_HOUR  # Resend NOT called the 21st time


def test_suppressed_response_is_byte_identical_to_allowed_response(
    client: TestClient, session: Session
) -> None:
    """An attacker probing the endpoint must not be able to distinguish
    a suppressed call from a successful one. Same status, same body."""
    with respx.mock() as mock:
        mock.post(RESEND_ENDPOINT).mock(return_value=RESEND_OK)
        allowed = client.post("/auth/login", data={"email": "alice@example.com"})
        # Burn the remaining four sends so the next call is suppressed.
        for _ in range(EMAIL_LIMIT_PER_HOUR - 1):
            client.post("/auth/login", data={"email": "alice@example.com"})
        suppressed = client.post("/auth/login", data={"email": "alice@example.com"})

    assert allowed.status_code == suppressed.status_code == 200
    assert allowed.content == suppressed.content


def test_fixed_bucket_consume_is_atomic_at_limit() -> None:
    """Unit-level: a fresh limiter at limit=3 allows exactly 3 then refuses."""
    limiter = FixedBucketRateLimiter(max_per_hour=3)
    assert [limiter.consume("k") for _ in range(5)] == [True, True, True, False, False]
    # Different keys have independent buckets.
    assert limiter.consume("other") is True
