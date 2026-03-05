from fastapi import APIRouter, HTTPException, status, Depends, Request
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, VerificationToken, VerificationTokenType
from app.services.auth_service import AuthService
from app.services.email_service import EmailService
from datetime import datetime, timedelta
import logging
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth"])

# Rate limiter — same instance as app.state.limiter (keyed by client IP)
limiter = Limiter(key_func=get_remote_address)

# ============ DEPENDENCY ============

security = HTTPBearer()

async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Dependency to get user_id from JWT"""
    auth_service = AuthService()
    token = credentials.credentials
    payload = auth_service.verify_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    
    return payload.get("sub")

# ============ SCHEMAS ============

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    phone: str = None
    
    @validator('password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        return v
    
    @validator('name')
    def name_length(cls, v):
        if len(v) < 2 or len(v) > 50:
            raise ValueError('Name must be 2-50 characters')
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    phone: str = None
    is_email_verified: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str
    
    @validator('new_password')
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class RefreshRequest(BaseModel):
    """Body schema for token refresh — keeps the refresh token out of URL / logs."""
    refresh_token: str


# ============ ENDPOINTS ============

@router.post("/signup", response_model=TokenResponse)
@limiter.limit("10/minute")  # Brute-force / spam protection
async def signup(
    request: Request,
    body: SignupRequest,
    db: Session = Depends(get_db)
):
    """
    Register new user.
    Returns access + refresh tokens.
    """
    auth_service = AuthService()
    email_service = EmailService()

    # Check if user exists
    existing_user = db.query(User).filter(User.email == body.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    try:
        # Create user
        user = User(
            email=body.email,
            password_hash=auth_service.hash_password(body.password),
            name=body.name,
            phone=body.phone,
        )
        db.add(user)
        db.flush()  # Get user ID
        
        # Create email verification token
        token, expires_at = auth_service.create_email_verification_token(user.id)
        verification_token = VerificationToken(
            user_id=user.id,
            token=token,
            token_type=VerificationTokenType.EMAIL_VERIFY,
            expires_at=expires_at,
        )
        db.add(verification_token)
        db.commit()
        
        # Send verification email
        verify_link = f"https://verifai.app/verify-email?token={token}"
        await email_service.send_verification_email(
            recipient_email=user.email,
            user_name=user.name,
            verify_link=verify_link,
        )
        
        logger.info(f"✅ User registered: {user.email}")
        
        # Return tokens
        tokens = auth_service.create_token_pair(user.id, user.email)
        return TokenResponse(**tokens)
    
    except Exception as e:
        db.rollback()
        logger.error(f"Signup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signup failed"
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")  # Brute-force protection
async def login(
    request: Request,
    body: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login user with email & password.
    Returns access + refresh tokens.
    """
    auth_service = AuthService()
    
    # Find user
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not auth_service.verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if account is locked
    if user.is_account_locked:
        if user.locked_until and datetime.utcnow() < user.locked_until:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Account locked until {user.locked_until}"
            )
        else:
            # Unlock expired lock
            user.is_account_locked = False
            user.locked_until = None
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    logger.info(f"✅ User logged in: {user.email}")
    
    # Return tokens
    tokens = auth_service.create_token_pair(user.id, user.email)
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange a valid refresh token for a new access token.
    The refresh token must be sent in the JSON request body (not a URL parameter)
    to prevent it from appearing in server access logs or browser history.
    """
    auth_service = AuthService()

    new_access_token = auth_service.refresh_access_token(body.refresh_token)
    if not new_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=body.refresh_token,
        token_type="Bearer",
        expires_in=3600,
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Get current user profile (protected route).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user


@router.post("/verify-email")
async def verify_email(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Verify email with token from signup.
    """
    # Find verification token
    verification_token = db.query(VerificationToken).filter(
        VerificationToken.token == token,
        VerificationToken.token_type == VerificationTokenType.EMAIL_VERIFY,
    ).first()
    
    if not verification_token or verification_token.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification token"
        )
    
    # Mark token as used and user as verified
    verification_token.is_used = True
    verification_token.used_at = datetime.utcnow()
    
    user = verification_token.user
    user.is_email_verified = True
    
    db.commit()
    
    logger.info(f"✅ Email verified: {user.email}")
    
    return {"message": "Email verified successfully"}


@router.post("/forgot-password")
@limiter.limit("5/minute")  # Prevents email flooding
async def forgot_password(
    request: Request,
    body: PasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Request password reset (sends email with reset link).
    """
    auth_service = AuthService()
    email_service = EmailService()

    # Find user
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        # Don't reveal if email exists (security)
        return {"message": "If email exists, reset link will be sent"}
    
    try:
        # Create reset token
        token, expires_at = auth_service.create_password_reset_token(user.id)
        reset_token = VerificationToken(
            user_id=user.id,
            token=token,
            token_type=VerificationTokenType.PASSWORD_RESET,
            expires_at=expires_at,
        )
        db.add(reset_token)
        db.commit()

        # Send reset email
        reset_link = f"https://verifai.app/reset-password?token={token}"
        await email_service.send_password_reset_email(
            recipient_email=user.email,
            user_name=user.name,
            reset_link=reset_link,
        )
        
        logger.info(f"✅ Password reset email sent: {user.email}")
        
        return {"message": "If email exists, reset link will be sent"}
    
    except Exception as e:
        logger.error(f"Password reset error: {e}")
        return {"message": "If email exists, reset link will be sent"}


@router.post("/reset-password")
async def reset_password(
    request: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Reset password using token.
    """
    auth_service = AuthService()
    
    # Find token
    reset_token = db.query(VerificationToken).filter(
        VerificationToken.token == request.token,
        VerificationToken.token_type == VerificationTokenType.PASSWORD_RESET,
    ).first()
    
    if not reset_token or reset_token.is_expired:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )
    
    # Update password
    reset_token.is_used = True
    reset_token.used_at = datetime.utcnow()
    
    user = reset_token.user
    user.password_hash = auth_service.hash_password(request.new_password)
    
    db.commit()
    
    logger.info(f"✅ Password reset: {user.email}")
    
    return {"message": "Password reset successfully"}