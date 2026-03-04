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
    Verify the database connection on application startup.
    Note: Schema evolution is now entirely managed by Alembic.
    Run `alembic upgrade head` to apply migrations before starting the app.
    """
    # Verify the DB connection before serving traffic
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
