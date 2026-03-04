from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.config import get_settings

settings = get_settings()

# pool_pre_ping=True — drops stale connections before use (important for PaaS deployments)
engine = create_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,       # Logs SQL only in development
    future=True,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and guarantees closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Create all ORM-mapped tables if they do not already exist.
    Called once at application startup (see app/main.py lifespan).

    Note: For production schema evolution, use Alembic migrations instead.
    """
    # Import here to avoid circular imports at module load time.
    # The import path matches the package structure (app/models/__init__.py).
    from app.models import Base  # noqa: F401 — side-effects register all models

    # Verify the DB connection before attempting DDL
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    Base.metadata.create_all(bind=engine)
