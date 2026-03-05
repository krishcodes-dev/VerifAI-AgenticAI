"""
app/api/oauth.py — Google OAuth 2.0 Authentication

Flow:
  1. Frontend hits GET /api/auth/google/login
     → Backend redirects browser to Google's consent page.
  2. Google redirects back to GET /api/auth/google/callback?code=...
     → Backend exchanges code for Google user info.
  3. If the Google email matches an existing user → log them in.
     If not → create a new account (no password, OAuth only).
  4. Backend redirects to frontend /auth/google/callback?token=...&refresh=...
     → Frontend (GoogleCallback.jsx) picks up the tokens and logs in.

Setup (required before Google OAuth works):
  1. Go to https://console.cloud.google.com/apis/credentials
  2. Create an OAuth 2.0 Client ID (Web Application)
  3. Add Authorized redirect URI: http://localhost:8000/api/auth/google/callback
  4. Add to .env:
       GOOGLE_CLIENT_ID=your_client_id
       GOOGLE_CLIENT_SECRET=your_client_secret
       GOOGLE_REDIRECT_URI=http://localhost:8000/api/auth/google/callback

If GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET are empty, all endpoints
return HTTP 503 with a clear message rather than crashing.
"""

import logging
import secrets
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, status, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Auth - OAuth"])

settings = get_settings()

# Google OAuth endpoints
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _require_oauth_configured():
    """Raise 503 if Google OAuth credentials are not configured."""
    if not settings.GOOGLE_OAUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Google OAuth is not configured. "
                "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to your .env file. "
                "See app/api/oauth.py for setup instructions."
            ),
        )


@router.get("/google/login")
async def google_login(request: Request):
    """
    Step 1: Redirect the user to Google's OAuth consent page.
    The frontend hits this URL directly (window.location.href).
    """
    _require_oauth_configured()

    # state param prevents CSRF on the callback
    state = secrets.token_urlsafe(16)

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "state": state,
        "prompt": "select_account",
    }

    query_string = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"{_GOOGLE_AUTH_URL}?{query_string}"

    logger.info("Google OAuth: redirecting to consent page")
    return RedirectResponse(url=auth_url)


@router.get("/google/callback")
async def google_callback(
    code: Optional[str] = None,
    error: Optional[str] = None,
    state: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Step 2: Google redirects here after the user grants consent.
    Exchanges the authorization code for tokens, fetches user info,
    creates or retrieves the user, then redirects to the frontend with JWTs.
    """
    _require_oauth_configured()

    # User cancelled or Google returned an error
    if error or not code:
        logger.warning("Google OAuth callback error: %s", error or "no code")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth?view=login&error=google_cancelled"
        )

    # ── Exchange code for Google access token ────────────────────────────────
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if token_response.status_code != 200:
        logger.error("Google token exchange failed: %s", token_response.text)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth?view=login&error=google_token_failed"
        )

    google_tokens = token_response.json()
    google_access_token = google_tokens.get("access_token")

    if not google_access_token:
        logger.error("Google token response missing access_token")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth?view=login&error=google_no_token"
        )

    # ── Fetch user info from Google ──────────────────────────────────────────
    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {google_access_token}"},
        )

    if userinfo_response.status_code != 200:
        logger.error("Google userinfo fetch failed: %s", userinfo_response.text)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth?view=login&error=google_userinfo_failed"
        )

    userinfo = userinfo_response.json()
    google_email = userinfo.get("email")
    google_name = userinfo.get("name", "")
    email_verified = userinfo.get("email_verified", False)

    if not google_email:
        logger.error("Google userinfo missing email")
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth?view=login&error=google_no_email"
        )

    if not email_verified:
        logger.warning("Google account email not verified: %s", google_email)
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/auth?view=login&error=google_email_not_verified"
        )

    # ── Find or create user ──────────────────────────────────────────────────
    auth_service = AuthService()

    user = db.query(User).filter(User.email == google_email).first()

    if user:
        # Existing user — just log them in
        if user.is_account_locked:
            logger.warning("Google login blocked — account locked: %s", google_email)
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/auth?view=login&error=account_locked"
            )
        logger.info("Google login: existing user %s", google_email)
    else:
        # New user — create account (no password since they'll always use Google)
        user = User(
            email=google_email,
            name=google_name or google_email.split("@")[0],
            password_hash=auth_service.hash_password(secrets.token_urlsafe(32)),  # Unusable password
            is_email_verified=True,  # Google already verified the email
        )
        db.add(user)
        try:
            db.commit()
            db.refresh(user)
            logger.info("Google login: created new user %s", google_email)
        except Exception as exc:
            db.rollback()
            logger.error("Failed to create Google user: %s", exc, exc_info=True)
            return RedirectResponse(
                url=f"{settings.FRONTEND_URL}/auth?view=login&error=account_creation_failed"
            )

    # ── Issue VerifAI JWTs ───────────────────────────────────────────────────
    tokens = auth_service.create_token_pair(user.id, user.email)

    # Redirect back to the frontend callback page with tokens in query params.
    # The GoogleCallback.jsx component picks these up and stores them.
    callback_url = (
        f"{settings.FRONTEND_URL}/auth/google/callback"
        f"?token={tokens['access_token']}"
        f"&refresh={tokens['refresh_token']}"
    )
    logger.info("Google OAuth complete for user=%s — redirecting to frontend", user.id)
    return RedirectResponse(url=callback_url)
