"""Auth routes — magic-link sign-in request.

POST /auth/login is enumeration-safe by construction: every email
follows the same code path (token mint, DB insert, Resend call, success
response). The handler never reads ``users`` to branch on existence, so
the response is identical for known and unknown addresses.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from app.auth.tokens import generate_token, hash_token
from app.config import get_settings
from app.db import get_session
from app.models.auth import MagicLinkToken
from app.services.email import send_magic_link
from app.templates import templates

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request) -> HTMLResponse:
    """Render the empty sign-in form."""
    return templates.TemplateResponse(request, "auth/login.html")


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    session: SessionDep,
    email: Annotated[str, Form()],
) -> HTMLResponse:
    """Mint a token, store its hash, send the magic link, return the
    same "check your email" page for every input."""
    settings = get_settings()
    raw_token = generate_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.magic_link_ttl_minutes)

    session.add(
        MagicLinkToken(
            email=email,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
        )
    )
    session.commit()

    verify_url = f"{settings.app_url.rstrip('/')}/auth/verify?token={raw_token}"
    await send_magic_link(to=email, verify_url=verify_url)

    return templates.TemplateResponse(request, "auth/check_email.html")
