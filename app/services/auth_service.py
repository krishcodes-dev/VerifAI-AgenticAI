"""
app/services/auth_service.py

JWT authentication service with Redis-backed token revocation.

TOKEN REVOCATION (logout):
  JWTs are stateless by design, but we need to support immediate revocation
  on logout. The approach:
  1. Every issued token includes a unique `jti` (JWT ID) claim.
  2. On logout, the token's jti is added to a Redis blocklist with a TTL equal
     to the token's remaining lifetime.
  3. `verify_token()` now checks the blocklist before returning the payload.
  4. If Redis is unavailable, verify_token falls back to signature-only
     validation (tokens cannot be revoked — documented limitation, still safe).
"""

import uuid
import secrets
from datetime import datetime, timedelta
from passlib.context import CryptContext
from typing import Optional, Dict, Tuple

from app.config import get_settings
from app.services.redis_client import redis_set, redis_exists

import jwt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_BLOCKLIST_PREFIX = "verifai:token_blocklist:"


class AuthService:
    """JWT + Password authentication service with jti-based revocation."""

    def __init__(self):
        self.settings = get_settings()
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60   # 1 hour
        self.refresh_token_expire_days = 7

    # ── Password Hashing ─────────────────────────────────────────────────────

    def hash_password(self, password: str) -> str:
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return pwd_context.verify(plain_password, hashed_password)

    # ── Token Creation ────────────────────────────────────────────────────────

    def create_access_token(self, user_id: str, email: str) -> str:
        """Create a short-lived JWT access token with a unique jti for revocation."""
        payload = {
            "sub": user_id,
            "email": email,
            "type": "access",
            "jti": str(uuid.uuid4()),   # Unique token ID — stored in blocklist on logout
            "exp": datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, self.settings.SECRET_KEY, algorithm=self.algorithm)

    def create_refresh_token(self, user_id: str, email: str) -> str:
        """Create a long-lived JWT refresh token with a unique jti."""
        payload = {
            "sub": user_id,
            "email": email,
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "exp": datetime.utcnow() + timedelta(days=self.refresh_token_expire_days),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, self.settings.SECRET_KEY, algorithm=self.algorithm)

    def create_token_pair(self, user_id: str, email: str) -> Dict[str, str]:
        """Create both access and refresh tokens."""
        return {
            "access_token": self.create_access_token(user_id, email),
            "refresh_token": self.create_refresh_token(user_id, email),
            "token_type": "Bearer",
            "expires_in": self.access_token_expire_minutes * 60,  # seconds
        }

    # ── Token Verification ────────────────────────────────────────────────────

    def verify_token(self, token: str) -> Optional[Dict]:
        """
        Verify a JWT token and return its payload.

        Steps:
        1. Decode and validate signature + expiry.
        2. Check if the token's jti is in the Redis blocklist (logged-out tokens).
        3. Return payload only if both checks pass.

        Returns None if the token is invalid, expired, or revoked.
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.SECRET_KEY,
                algorithms=[self.algorithm],
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

        # Check token revocation blocklist
        jti = payload.get("jti")
        if jti and redis_exists(f"{_BLOCKLIST_PREFIX}{jti}"):
            return None  # Token has been revoked (user logged out)

        return payload

    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Create a new access token from a valid refresh token."""
        payload = self.verify_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            return None
        return self.create_access_token(payload["sub"], payload["email"])

    # ── Token Revocation ──────────────────────────────────────────────────────

    def revoke_token(self, token: str) -> bool:
        """
        Add a token's jti to the Redis blocklist with a TTL matching its expiry.

        This is called on logout to immediately invalidate the token.
        If Redis is unavailable, logs a warning but does not raise an error.

        Returns True if successfully revoked, False if Redis unavailable.
        """
        try:
            payload = jwt.decode(
                token,
                self.settings.SECRET_KEY,
                algorithms=[self.algorithm],
                options={"verify_exp": False},  # Decode even if already expired
            )
        except jwt.InvalidTokenError:
            return False  # Malformed token — nothing to revoke

        jti = payload.get("jti")
        if not jti:
            return False  # Old token without jti — cannot revoke specifically

        # TTL: seconds remaining until expiry (min 1 second to avoid immediate eviction)
        exp = payload.get("exp")
        if exp:
            ttl = max(1, int(exp - datetime.utcnow().timestamp()))
        else:
            ttl = self.access_token_expire_minutes * 60

        success = redis_set(f"{_BLOCKLIST_PREFIX}{jti}", "revoked", ex=ttl)
        if success:
            import logging
            logging.getLogger(__name__).info("Token jti=%s revoked (TTL=%ds)", jti, ttl)
        else:
            import logging
            logging.getLogger(__name__).warning(
                "Could not revoke token jti=%s — Redis unavailable. "
                "Token will expire naturally at %s.", jti,
                datetime.utcfromtimestamp(exp) if exp else "unknown",
            )
        return success

    # ── Email / Password Reset Tokens ─────────────────────────────────────────

    def generate_verification_token(self) -> str:
        return secrets.token_urlsafe(32)

    def create_password_reset_token(self, user_id: str) -> Tuple[str, datetime]:
        token = self.generate_verification_token()
        expires_at = datetime.utcnow() + timedelta(hours=1)
        return token, expires_at

    def create_email_verification_token(self, user_id: str) -> Tuple[str, datetime]:
        token = self.generate_verification_token()
        expires_at = datetime.utcnow() + timedelta(days=7)
        return token, expires_at


# ── FastAPI Dependency ────────────────────────────────────────────────────────

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_db
from sqlalchemy.orm import Session

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """
    FastAPI dependency — validates JWT (including revocation check) and
    returns the decoded token payload.
    """
    token = credentials.credentials
    auth_service = AuthService()

    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    return payload