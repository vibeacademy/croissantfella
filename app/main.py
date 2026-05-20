"""FastAPI application entrypoint.

Run locally:
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

Production (Cloud Run) runs the same command — see Dockerfile.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api import health
from app.auth import routes as auth_routes
from app.config import get_settings
from app.db import engine
from app.onboard import routes as onboard_routes
from app.onboard.middleware import RequireTasteProfileMiddleware
from app.templates import templates
from app.users import routes as users_routes

_settings = get_settings()

app = FastAPI(title="Croissantfella")
# app.state.engine is read by RequireTasteProfileMiddleware so tests can
# substitute an in-memory engine; production reads the module-level
# Neon-bound engine. Storing it here makes the override testable via
# app.state without globally monkeypatching app.db.
app.state.engine = engine
# Cloud Run terminates TLS at the proxy and forwards via X-Forwarded-Proto
# and X-Forwarded-Host. Without this middleware, request.url returns the
# internal Cloud Run origin (http://localhost:8080) and absolute URLs
# constructed from it (magic links, OAuth redirects) silently break in
# preview and production. See docs/PATTERN-LIBRARY.md pitfall #3.
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")
# RequireTasteProfileMiddleware reads request.session, so it MUST be
# added BEFORE SessionMiddleware in code order (Starlette wraps in stack
# order; last-added is outermost and runs first on the way in). After
# this layout: incoming request → SessionMiddleware (populates session)
# → RequireTasteProfile (reads session, conditionally redirects) →
# ProxyHeaders → route handler.
app.add_middleware(RequireTasteProfileMiddleware)
# Signed session cookie used by the magic-link verify flow. https_only=True
# adds the `Secure` attribute so the cookie only travels over TLS;
# same_site="lax" defends against CSRF on top-level GET while still letting
# the verify link redirect from the user's email client.
app.add_middleware(
    SessionMiddleware,
    secret_key=_settings.session_secret,
    https_only=True,
    same_site="lax",
)

STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(health.router)
app.include_router(auth_routes.router)
app.include_router(onboard_routes.router)
app.include_router(users_routes.router)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")
