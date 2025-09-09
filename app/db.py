import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Load .env when running outside Docker (safe if missing)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# IMPORTANT:
# - In Docker Compose, host should be "db" (matches service name).
# - Running locally (outside Docker), override with:
#   export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/notes
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@db:5432/postgres",  # fallback default
)

# Engine with pre_ping to auto-recover stale connections
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

# Session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

# Base for ORM models
Base = declarative_base()


def get_db() -> Generator:
    """
    FastAPI dependency that yields a SQLAlchemy session.
    Ensures the session is always closed after the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
