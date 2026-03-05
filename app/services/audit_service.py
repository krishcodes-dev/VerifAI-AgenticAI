"""
app/services/audit_service.py

Lightweight audit logging service for security-critical events.

Writes to the AuditLog table (already defined in app/models/__init__.py).
Designed to be called fire-and-forget inside endpoints — failures are
logged but never propagate to the caller (audit shouldn't break auth).

Usage:
    from app.services.audit_service import audit_log

    audit_log(db, "user_login_success", "info", user_id=user.id,
              description=f"User {user.email} logged in",
              ip_address=request.client.host,
              meta={"email": user.email})
"""

import logging
from datetime import datetime
from typing import Optional, Any
from sqlalchemy.orm import Session

from app.models import AuditLog

logger = logging.getLogger(__name__)

# Event type constants — use these strings consistently across the codebase
EVENT_LOGIN_SUCCESS = "user_login_success"
EVENT_LOGIN_FAILURE = "user_login_failure"
EVENT_LOGOUT = "user_logout"
EVENT_SIGNUP = "user_signup"
EVENT_TOKEN_REFRESH = "token_refresh"
EVENT_PASSWORD_RESET_REQUEST = "password_reset_request"
EVENT_PASSWORD_RESET_COMPLETE = "password_reset_complete"
EVENT_EMAIL_VERIFIED = "email_verified"
EVENT_GOOGLE_LOGIN = "google_oauth_login"
EVENT_ACCOUNT_LOCKED = "account_locked"

# Severity levels
SEVERITY_INFO = "info"
SEVERITY_WARNING = "warning"
SEVERITY_CRITICAL = "critical"


def audit_log(
    db: Session,
    event_type: str,
    severity: str,
    description: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    meta: Optional[dict[str, Any]] = None,
) -> None:
    """
    Write a single audit log entry to the database.

    This function is intentionally fire-and-forget — any database error is
    caught and logged (but not re-raised) so an audit failure never breaks an
    authentication flow.

    Args:
        db:          Open SQLAlchemy session from the calling endpoint.
        event_type:  One of the EVENT_* constants above (or any string).
        severity:    "info" | "warning" | "critical"
        description: Human-readable description of the event.
        user_id:     UUID of the acting user, or None for pre-auth failures.
        ip_address:  Client IP from request.client.host (may be None in tests).
        user_agent:  HTTP User-Agent header value.
        meta:        Arbitrary JSON-serialisable dict for extra context.
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            event_type=event_type,
            event_severity=severity,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            meta_data=meta or {},
            created_at=datetime.utcnow(),
        )
        db.add(entry)
        db.flush()   # Write inside the current transaction; caller commits.
        logger.debug(
            "[audit] %s | user=%s | ip=%s | %s",
            event_type, user_id, ip_address, description,
        )
    except Exception as exc:
        # Never let audit failures break the caller's flow.
        logger.error(
            "[audit] Failed to write audit log event=%s user=%s: %s",
            event_type, user_id, exc,
        )
