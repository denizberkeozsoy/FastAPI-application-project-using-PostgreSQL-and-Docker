# app/tests/conftest.py
import os
import pytest
from fastapi.testclient import TestClient

# Ensure we always hit the container DB by default.
# When running locally without Docker, put your own DATABASE_URL
# in a .env or export it before running pytest.
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@db:5432/notes")

from app.main import app  # noqa: E402
from app.db import Base, engine, SessionLocal  # noqa: E402
from app.models import Note, User  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def create_schema():
    """Create tables once for the test session (idempotent)."""
    Base.metadata.create_all(bind=engine)
    yield
    # Optional: drop at the end of the session if you prefer a clean DB
    # Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables():
    """Clean rows before each test to avoid test interaction."""
    with engine.begin() as conn:
        # Fast TRUNCATE (works in Postgres); CASCADE clears children too.
        conn.exec_driver_sql("TRUNCATE TABLE notes RESTART IDENTITY CASCADE;")
        conn.exec_driver_sql("TRUNCATE TABLE users RESTART IDENTITY CASCADE;")
    yield


@pytest.fixture()
def client():
    """FastAPI test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_session():
    """A real DB session if a test needs direct access."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
