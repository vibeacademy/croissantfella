"""Health check endpoints.

`/api/health` — fast probe used by Cloud Run readiness checks. Does NOT
touch the database (Neon cold-wake on every probe is expensive).

`/api/health/db` — DB-backed probe used by the preview-deploy smoke test
to verify the deploy actually has a working database connection. Added
in #78 because preview deploys without Neon configured were passing
the no-DB `/api/health` probe and shipping a broken URL.

Why NOT `/healthz`: Google Front End reserves the literal lowercase path
`/healthz` on `*.run.app` URLs (presumably for its own probing of Cloud
Run revisions) and returns its own branded HTML 404 instead of routing
the request to the container. Confirmed empirically against the live
preview URL — `/healthz` 404s with `referrer-policy: no-referrer` and
no `server: Google Frontend` header, while every other path I tested
(`/livez`, `/readyz`, `/_ah/health`, `/health`, `/api/health`, `/status`)
proxies to the container correctly. So the readable-but-conventional
`/healthz` name is unusable on Cloud Run direct domains; stick to
`/api/health` and friends.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel import Session

from app.db import get_session

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/api/health")
async def health() -> JSONResponse:
    """Return 200 with a small JSON body.

    Deliberately does NOT touch the database — health checks must be
    fast and not wake up the Neon compute endpoint on every probe.
    """
    return JSONResponse({"status": "ok"})


@router.get("/api/health/db")
def health_db(session: SessionDep) -> JSONResponse:
    """Single-query DB probe — `SELECT 1`.

    Used by preview-deploy.yml to validate that the deployed revision
    can reach the database. Cheap (single round-trip, no schema), but
    distinct from `/api/health`: a revision with `DATABASE_URL=""` or
    a misconfigured Neon branch fails this and passes `/api/health`.
    Uses SQLAlchemy's `session.execute(text(...))` because SQLModel's
    typed `session.exec()` only accepts SQLModel statements.
    """
    session.execute(text("SELECT 1"))
    return JSONResponse({"status": "ok"})
