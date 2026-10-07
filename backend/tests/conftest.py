"""Shared pytest fixtures.

Tests run against an isolated in-memory SQLite database so they never touch
the developer's MySQL data. The ORM layer is dialect agnostic; queries that
genuinely require MySQL are marked and skipped accordingly.
"""

from __future__ import annotations

import os
from typing import Generator

import pytest

os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-in-production")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.database import Base, get_db  # noqa: E402
from app.main import create_app  # noqa: E402
import app.models  # noqa: E402,F401  (registers tables)

TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"


@pytest.fixture(scope="session")
def engine():
    test_engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(test_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _record):  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(test_engine)
    yield test_engine
    Base.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture()
def db_session(engine) -> Generator[Session, None, None]:
    """Provide a clean database for each test."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """FastAPI test client bound to the test database session."""
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def owner_credentials() -> dict:
    return {
        "email": "owner@smedemo.com",
        "full_name": "Platform Owner",
        "password": "OwnerPass123",
        "role": "owner",
    }


@pytest.fixture()
def auth_headers(client: TestClient, owner_credentials: dict) -> dict:
    """Register the first (owner) account and return its bearer header."""
    client.post("/api/v1/auth/register", json=owner_credentials)
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": owner_credentials["email"],
            "password": owner_credentials["password"],
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
