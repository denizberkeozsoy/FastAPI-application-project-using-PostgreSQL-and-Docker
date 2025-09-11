# app/tests/conftest.py
import os
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine.url import make_url, URL

# --- Choose the TEST database URL ---
# Prefer DATABASE_URL_TEST; else derive ".../notes_test" from DATABASE_URL;
# fallback matches your compose default host.
BASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@db:5432/postgres")
TEST_URL = os.getenv("DATABASE_URL_TEST")

def _derive_test_url() -> URL:
    if TEST_URL:
        return make_url(TEST_URL)
    u = make_url(BASE_URL)
    # If base had no db, start with 'postgres', then switch to notes_test
    if not u.database:
        u = u.set(database="postgres")
    return u.set(database="notes_test")

def _admin_url_from(url: URL) -> URL:
    # same server/creds, but connect to 'postgres' to manage DBs
    return url.set(database="postgres")

def _ensure_test_db_exists(test_url: URL):
    admin_engine = create_engine(_admin_url_from(test_url), isolation_level="AUTOCOMMIT")
    dbname = test_url.database
    assert dbname, "Test URL must include a database name"
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname=:n"),
            {"n": dbname},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    admin_engine.dispose()

# Build the dedicated test engine BEFORE importing app, and
# export DATABASE_URL so app/db picks it up if anything inspects env.
TEST_DB_URL = _derive_test_url()
_ensure_test_db_exists(TEST_DB_URL)
os.environ["DATABASE_URL"] = str(TEST_DB_URL)

# Now import the app and models
from app.main import app, get_db  # noqa: E402
from app.db import Base  # noqa: E402

# Create a SQLAlchemy engine/sessionmaker for the test DB
test_engine = create_engine(TEST_DB_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def create_schema():
    """
    Create a fresh schema for the whole test session,
    then drop it at the end.
    """
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()

@pytest.fixture(scope="function")
def db_session():
    """
    Per-test DB session. If you want stricter isolation,
    you can wrap this in a transaction and roll back instead.
    """
    session = TestingSessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()

@pytest.fixture(scope="function", autouse=True)
def override_get_db(db_session):
    """
    Make FastAPI use the Postgres TEST DB session for every request.
    """
    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()

@pytest.fixture()
def client():
    """
    FastAPI TestClient bound to our overridden DB.
    """
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c
