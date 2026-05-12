"""Auth routes — magic-link sign-in request.

POST /auth/login is enumeration-safe by construction: every email
follows the same code path (token mint, DB insert, Resend call, success
response). The handler never reads ``users`` to branch on existence, so
the response is identical for known and unknown addresses.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlmodel import Session, select

from app.auth.tokens import generate_token, hash_token
from app.config import get_settings
from app.db import get_session
from app.models.auth import MagicLinkToken
from app.models.user import TasteProfile, User
from app.services.email import send_magic_link
from app.templates import templates

VERIFY_PATH = "/auth/verify"

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

    # Build the verify URL from the incoming request so previews, prod,
    # and local dev all produce a link that points back to their own
    # origin. ProxyHeadersMiddleware (registered in app.main) rewrites
    # request.url.scheme from X-Forwarded-Proto; request.url.hostname
    # comes from the Host header, which Cloud Run already sets to the
    # external hostname before forwarding to the container.
    verify_url = str(request.url.replace(path=VERIFY_PATH, query=f"token={raw_token}"))
    await send_magic_link(to=email, verify_url=verify_url)

    return templates.TemplateResponse(request, "auth/check_email.html")


def _expired_response(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "auth/expired.html", status_code=410)


@router.get("/verify", name="verify_login")
def verify(
    request: Request,
    session: SessionDep,
    token: str = "",
) -> Response:
    """Consume the magic-link token, log the user in, and redirect.

    Single-use: the row is deleted before the session cookie is set so a
    replayed link returns 410 even if the first call's redirect was missed.
    """
    if not token:
        return _expired_response(request)

    row = session.exec(
        select(MagicLinkToken).where(MagicLinkToken.token_hash == hash_token(token))
    ).first()
    if row is None:
        return _expired_response(request)

    expires_at = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        # Expired tokens get deleted on the spot to keep the table small;
        # the response shape is identical to "row not found" so a clock-
        # skewed attacker can't distinguish the two cases.
        session.delete(row)
        session.commit()
        return _expired_response(request)

    email = row.email
    session.delete(row)
    session.commit()

    user = session.exec(select(User).where(User.email == email)).first()
    if user is None:
        # First sign-in for this email — mint a User row. display_name
        # defaults to the email local-part; #16 / #17 will let the user
        # change it. No unique constraint on display_name at the DB layer.
        local_part = email.split("@", 1)[0][:100]
        user = User(email=email, display_name=local_part)
        session.add(user)
        session.commit()
        session.refresh(user)

    request.session["user_id"] = str(user.id)

    profile = session.get(TasteProfile, user.id)
    target = "/" if profile is not None else "/onboard"
    return RedirectResponse(target, status_code=302)
