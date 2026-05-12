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
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
