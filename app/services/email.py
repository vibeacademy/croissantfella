"""Resend transactional email client.

A thin wrapper around the Resend HTTP API
(https://resend.com/docs/api-reference/emails/send-email) using
``httpx.AsyncClient``. The wrapper exists so tests can mock at the
HTTP layer via ``respx`` rather than reaching into the route handlers.

Subject lines are deliberately PII-free per the security guardrail in
ticket #12 — no email addresses or token values appear in the subject.
"""

import httpx

from app.config import get_settings

RESEND_ENDPOINT = "https://api.resend.com/emails"
MAGIC_LINK_SUBJECT = "Sign in"


async def send_magic_link(*, to: str, verify_url: str) -> None:
    """Send a magic-link email via Resend.

    Raises ``httpx.HTTPStatusError`` on non-2xx responses; the caller
    decides whether to surface that to the user or fail closed.
    """
    settings = get_settings()
    html_body = (
        f"<p>Click the link below to sign in. This link is valid for "
        f"{settings.magic_link_ttl_minutes} minutes and can be used once."
        f'</p><p><a href="{verify_url}">Sign in to Croissantfella</a></p>'
        f"<p>If you didn't request this, you can ignore this email.</p>"
    )
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            RESEND_ENDPOINT,
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.resend_from_email,
                "to": [to],
                "subject": MAGIC_LINK_SUBJECT,
                "html": html_body,
            },
        )
        response.raise_for_status()
