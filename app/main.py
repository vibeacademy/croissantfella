"""FastAPI application entrypoint.

Run locally:
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8080

Production (Cloud Run) runs the same command — see Dockerfile.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api import health
from app.auth import routes as auth_routes
from app.templates import templates

app = FastAPI(title="Croissantfella")

STATIC_DIR = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(health.router)
app.include_router(auth_routes.router)


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")
