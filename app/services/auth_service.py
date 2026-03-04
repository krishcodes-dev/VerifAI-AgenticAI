import jwt
import secrets
from datetime import datetime, timedelta
from passlib.context import CryptContext
from typing import Optional, Dict, Tuple
from app.config import get_settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    """JWT + Password authentication service"""
    
    def __init__(self):
        self.settings = get_settings()
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60  # 1 hour
        self.refresh_token_expire_days = 7
    
    # ============ PASSWORD HASHING ============
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify plain password against hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    # ============ JWT TOKENS ============
    
    def create_access_token(self, user_id: str, email: str) -> str:
        """Create JWT access token (short-lived)"""
        payload = {
            "sub": user_id,
            "email": email,
            "type": "access",
            "exp": datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes),
            "iat": datetime.utcnow(),
        }
        token = jwt.encode(
            payload,
            self.settings.SECRET_KEY,
            algorithm=self.algorithm
        )
        return token
    
    def create_refresh_token(self, user_id: str, email: str) -> str:
        """Create JWT refresh token (long-lived)"""
        payload = {
            "sub": user_id,
            "email": email,
            "type": "refresh",
            "exp": datetime.utcnow() + timedelta(days=self.refresh_token_expire_days),
            "iat": datetime.utcnow(),
        }
        token = jwt.encode(
            payload,
            self.settings.SECRET_KEY,
            algorithm=self.algorithm
        )
        return token
    
    def create_token_pair(self, user_id: str, email: str) -> Dict[str, str]:
        """Create both access and refresh tokens"""
        return {
            "access_token": self.create_access_token(user_id, email),
            "refresh_token": self.create_refresh_token(user_id, email),
            "token_type": "Bearer",
            "expires_in": self.access_token_expire_minutes * 60,  # seconds
        }
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(
                token,
                self.settings.SECRET_KEY,
                algorithms=[self.algorithm]
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None  # Token expired
        except jwt.InvalidTokenError:
            return None  # Invalid token
    
    def refresh_access_token(self, refresh_token: str) -> Optional[str]:
        """Create new access token from refresh token"""
        payload = self.verify_token(refresh_token)
        
        if not payload or payload.get("type") != "refresh":
            return None
        
        return self.create_access_token(
            payload["sub"],
            payload["email"]
        )
    
    # ============ EMAIL VERIFICATION TOKENS ============
    
    def generate_verification_token(self) -> str:
        """Generate secure random token for email verification"""
        return secrets.token_urlsafe(32)
    
    def create_password_reset_token(self, user_id: str) -> Tuple[str, datetime]:
        """Create time-limited password reset token"""
        token = self.generate_verification_token()
        expires_at = datetime.utcnow() + timedelta(hours=1)  # 1 hour expiry
        return token, expires_at
    
    def create_email_verification_token(self, user_id: str) -> Tuple[str, datetime]:
        """Create email verification token"""
        token = self.generate_verification_token()
        expires_at = datetime.utcnow() + timedelta(days=7)  # 7 days expiry
        return token, expires_at


# ============ REUSABLE FASTAPI DEPENDENCY ============
# Centralised "get current user" dependency for use in protected endpoints.
# Usage:
#   from app.services.auth_service import get_current_user
#   @router.get("/protected")
#   async def protected(user: dict = Depends(get_current_user)):
#       return {"user_id": user["sub"]}

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
    FastAPI dependency — extracts and validates the JWT from the Authorization header.
    Returns the decoded token payload on success.
    Raises HTTP 401 if the token is missing, expired, or invalid.
    """
    token = credentials.credentials
    auth_service = AuthService()

    payload = auth_service.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    return payload