"""
app/api/users.py — Real user profile & preferences endpoints.

These endpoints operate on the same User model used by /api/auth/*.
They require a valid JWT (get_current_user_id dependency) so callers
can only read/update their own profile.

Replaced the original dead stubs:
  - POST /api/v1/users/register  (no DB write, fake timestamp) → disabled;
    registration is handled exclusively by POST /api/auth/signup.
  - GET  /api/v1/users/{user_id}  (hardcoded mock values) →
    GET  /api/v1/users/me         (returns real DB row for authenticated user).

New endpoints:
  GET  /api/v1/users/me          — return authenticated user's profile
  PATCH /api/v1/users/me         — update name, phone, notification prefs
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.api.auth import get_current_user_id

import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["users"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class UserProfileResponse(BaseModel):
    """Public-safe user profile response — never includes password_hash."""
    id: str
    email: str
    name: str
    phone: Optional[str]
    is_email_verified: bool
    theme: Optional[str]
    notifications_enabled: bool
    email_alerts: bool
    created_at: Optional[datetime]
    last_login: Optional[datetime]

    class Config:
        from_attributes = True


class UpdateProfileRequest(BaseModel):
    """Fields a user may update on their own profile."""
    name: Optional[str] = None
    phone: Optional[str] = None
    theme: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    email_alerts: Optional[bool] = None

    @validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError("name cannot be an empty string")
        return v

    @validator("theme")
    @classmethod
    def theme_valid(cls, v):
        if v is not None and v not in ("light", "dark", "system"):
            raise ValueError("theme must be 'light', 'dark', or 'system'")
        return v


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/users/me", response_model=UserProfileResponse)
async def get_my_profile(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Return the authenticated user's profile.

    Previously: GET /api/v1/users/{user_id} returned hardcoded mock data
    regardless of the actual user_id.  This endpoint returns real DB data
    for the authenticated user only.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return user


@router.patch("/users/me", response_model=UserProfileResponse)
async def update_my_profile(
    body: UpdateProfileRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Update the authenticated user's own profile fields.
    Only fields provided in the request body are changed (partial update).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    changed = False
    update_data = body.model_dump(exclude_none=True)

    for field, value in update_data.items():
        if hasattr(user, field) and getattr(user, field) != value:
            setattr(user, field, value)
            changed = True

    if changed:
        user.updated_at = datetime.utcnow()
        try:
            db.commit()
            db.refresh(user)
            logger.info("Profile updated for user=%s fields=%s", user_id, list(update_data.keys()))
        except Exception as exc:
            db.rollback()
            logger.error("Profile update failed for user=%s: %s", user_id, exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Profile update failed",
            )

    return user
