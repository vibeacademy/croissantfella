"""GET /u/{display_name} — public profile page."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import desc, func
from sqlmodel import Session, select

from app.db import get_session
from app.models.post import Post
from app.models.taxonomy import ContentStatus
from app.models.user import User
from app.templates import templates

PROFILE_POST_LIMIT = 50

router = APIRouter(tags=["users"])

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/u/{display_name}", response_class=HTMLResponse)
def profile(
    request: Request,
    session: SessionDep,
    display_name: str,
) -> Response:
    """Render the public profile page for ``display_name``.

    Reachable anonymously. 404 if no user matches (case-insensitively).
    302 redirect to the canonical-case URL if the URL's case differs
    from the stored value. Only ``status='published'`` posts are listed.
    """
    user = session.exec(
        select(User).where(func.lower(User.display_name) == display_name.lower())
    ).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if user.display_name != display_name:
        return RedirectResponse(f"/u/{user.display_name}", status_code=302)

    # Use a string column name for order_by so mypy doesn't trip on
    # SQLModel's Python-typed column attribute (see PATTERN-LIBRARY.md #16).
    posts = list(
        session.exec(
            select(Post)
            .where(Post.author_id == user.id)
            .where(Post.status == ContentStatus.PUBLISHED.value)
            .order_by(desc("published_at"))
            .limit(PROFILE_POST_LIMIT)
        )
    )

    return templates.TemplateResponse(
        request,
        "users/profile.html",
        {"profile_user": user, "posts": posts},
    )
