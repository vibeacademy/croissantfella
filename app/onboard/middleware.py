"""Force authenticated users without a TasteProfile to /onboard.

A signed-in user who never completed the questionnaire would otherwise
land on an empty home feed. This middleware redirects them to /onboard
on any non-exempt path. Exempt paths bypass the DB query entirely so a
sign-in flow or static asset doesn't trigger a Neon wake.
"""

import uuid
from collections.abc import Awaitable, Callable

from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.db import engine as default_engine
from app.models.user import TasteProfile

# Paths the middleware never redirects. /onboard itself would otherwise
# loop; /auth/* is required to sign in or out; /api/health* is hit by
# Cloud Run probes; /static/* is plain files. We use prefix matching so
# subroutes (e.g., /auth/verify) inherit the exemption.
EXEMPT_PREFIXES: tuple[str, ...] = (
    "/onboard",
    "/auth/",
    "/api/health",
    "/static/",
)


class RequireTasteProfileMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return await call_next(request)

        try:
            raw_user_id = request.session.get("user_id")
        except (AssertionError, AttributeError):
            # SessionMiddleware isn't installed or the scope doesn't
            # have a session — treat as anonymous and let the route
            # handle auth itself.
            return await call_next(request)

        if not raw_user_id:
            return await call_next(request)

        try:
            user_id = uuid.UUID(raw_user_id)
        except (ValueError, TypeError):
            return await call_next(request)

        # Tests override app.state.engine to point at their in-memory
        # SQLite; production uses the module-level Neon-bound engine.
        active_engine = getattr(request.app.state, "engine", default_engine)
        with Session(active_engine) as db:
            profile = db.get(TasteProfile, user_id)

        if profile is None:
            return RedirectResponse("/onboard", status_code=302)
        return await call_next(request)
