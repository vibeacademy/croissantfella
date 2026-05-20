"""Shared pytest fixtures.

Uses an in-memory SQLite database per test so tests don't touch Neon or
pollute each other. The app's get_session dependency is overridden to
yield sessions bound to the test engine.
"""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

import app.models  # noqa: F401  -- register tables on SQLModel.metadata
from app.auth.rate_limit import email_limiter, ip_limiter
from app.db import get_session
from app.main import app


@pytest.fixture(autouse=True)
def _reset_rate_limiters() -> Generator[None, None, None]:
    """Module-level limiter state would otherwise leak between tests."""
    email_limiter._reset()
    ip_limiter._reset()
    yield
    email_limiter._reset()
    ip_limiter._reset()


@pytest.fixture(name="session")
def session_fixture() -> Generator[Session, None, None]:
    """Fresh in-memory SQLite database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _enable_sqlite_fks(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        # SQLite ships with FK enforcement off; turn it on so ON DELETE
        # CASCADE behaves the same way as in Postgres.
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(session: Session) -> Generator[TestClient, None, None]:
    """TestClient with get_session overridden to use the test session."""

    def get_session_override() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_session] = get_session_override
    # RequireTasteProfileMiddleware reads app.state.engine to query
    # TasteProfile outside FastAPI's DI. Point it at the test engine so
    # the middleware exercises real DB lookups against test data
    # rather than the dev-default sqlite or production Neon.
    original_engine = getattr(app.state, "engine", None)
    app.state.engine = session.bind
    # base_url=https so SessionMiddleware's Secure cookie survives the
    # httpx cookie jar — without this, the cookie is set on the response
    # but stripped on the next request because Secure cookies don't ride
    # http://. Tests can still send X-Forwarded-Proto explicitly to
    # exercise ProxyHeadersMiddleware overrides.
    with TestClient(app, base_url="https://testserver") as client:
        yield client
    app.dependency_overrides.clear()
    if original_engine is not None:
        app.state.engine = original_engine
