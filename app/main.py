from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import logging

from app.config import get_settings
from app.database import engine  # kept for any direct engine-level queries

# Import routers
from app.api import transactions, users, auth, demo, oauth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()

# ── Rate Limiter ──────────────────────────────────────────────────────────────
# Uses the client's real IP as the rate-limit key.
# The limiter instance is created here and shared via app.state.limiter
# so individual endpoint decorators can reference it.
limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])


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


# ── FastAPI App ───────────────────────────────────────────────────────────────
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

# ── Attach rate limiter to app state ─────────────────────────────────────────
# Endpoints import `limiter` directly from this module for their decorators.
app.state.limiter = limiter

# ── Security Headers Middleware ───────────────────────────────────────────────

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Attach standard security headers to every response.

    Headers applied:
      X-Content-Type-Options: nosniff
        Prevents MIME-type sniffing attacks.
      X-Frame-Options: DENY
        Prevents clickjacking by disallowing framing.
      Content-Security-Policy: default-src 'self'
        Restricts resource loading to the same origin by default.
        Tighten further (add CDN domains, etc.) once frontend is on a fixed domain.
      Strict-Transport-Security
        Tells browsers to always use HTTPS for this origin.
        Omitted in development to avoid breaking localhost HTTP.
      X-XSS-Protection: 0
        Disables the broken legacy XSS auditor (modern best-practice is to disable
        it and rely on CSP instead — see OWASP recommendation).
      Referrer-Policy: strict-origin-when-cross-origin
        Limits referrer leakage to same-origin requests only.
      Permissions-Policy: geolocation=(), microphone=(), camera=()
        Disables browser APIs that this API server never needs.
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        # HSTS: only send on non-dev to avoid browser caching localhost as HTTPS-only
        if settings.ENVIRONMENT != "development":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )
        return response


# ── Middleware (order matters: first registered = outermost wrapper) ──────────
# SecurityHeaders → SlowAPI → CORS → App
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)

# ── Exception handlers ────────────────────────────────────────────────────────
@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Return a clean 429 JSON response instead of the default HTML error page."""
    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "detail": "Too many requests. Please slow down and try again shortly.",
            "retry_after": str(exc.retry_after) if hasattr(exc, "retry_after") else "60",
        },
    )

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(transactions.router)
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(oauth.router)
app.include_router(demo.router)


# ── Health / Root ─────────────────────────────────────────────────────────────
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
