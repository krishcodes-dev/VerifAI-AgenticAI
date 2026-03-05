from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.config import get_settings
from app.database import engine  # still needed for health checks

# Import routers
from app.api import transactions, users, auth, demo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    # ── Startup ──────────────────────────────────────────────────
    logger.info("🚀 VerifAI starting up (env=%s)", settings.ENVIRONMENT)
    try:
        # Run Alembic migrations programmatically — applies any pending
        # schema changes before the app accepts traffic.
        from alembic.config import Config
        from alembic import command as alembic_command
        alembic_cfg = Config("alembic.ini")
        alembic_command.upgrade(alembic_cfg, "head")
        logger.info("✅ Database migrations applied (alembic upgrade head)")
    except Exception as exc:
        logger.critical("💥 Database migration failed: %s", exc)
        raise

    yield  # Application runs here

    # ── Shutdown ─────────────────────────────────────────────────
    logger.info("👋 VerifAI shutting down")


# Disable interactive API docs in production to avoid information leakage
_docs_url = "/docs" if settings.DEBUG else None
_redoc_url = "/redoc" if settings.DEBUG else None

app = FastAPI(
    title="VerifAI - Fraud Detection API",
    description="Real-time ML-based fraud detection and prevention",
    version="1.0.0",
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────
# Using explicit allowed origins — wildcard with credentials is rejected
# by browsers and is a security vulnerability. Origins are derived from
# settings so they can be overridden per environment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ── Routers ──────────────────────────────────────────────────────────
app.include_router(transactions.router)
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(demo.router)


# ── Health / Root ─────────────────────────────────────────────────────
@app.get("/")
async def root():
    return {
        "service": "VerifAI Fraud Detection API",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "status": "online",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "VerifAI"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )
