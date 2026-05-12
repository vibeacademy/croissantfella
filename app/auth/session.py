"""Authenticated-user dependency.

Reads ``user_id`` from the signed session cookie (set by GET /auth/verify),
loads the ``User`` row, and raises 401 if either step fails. Routes that
require an authenticated user depend on ``current_user`` directly; routes
that merely *prefer* one should depend on ``optional_current_user``.
"""

import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session

from app.db import get_session
from app.models.user import User


def optional_current_user(
    request: Request, session: Annotated[Session, Depends(get_session)]
) -> User | None:
    """Return the authenticated user, or None if no valid session."""
    raw = request.session.get("user_id")
    if not raw:
        return None
    try:
        user_id = uuid.UUID(raw)
    except (ValueError, TypeError):
        return None
    return session.get(User, user_id)


def current_user(
    user: Annotated[User | None, Depends(optional_current_user)],
) -> User:
    """Return the authenticated user, or raise 401."""
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return user
