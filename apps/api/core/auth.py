"""Unified JWT token management (§55.1).

Single source of truth for token creation and verification.
Replaces the dual implementations that were in routers/auth.py (PyJWT) and
middleware/auth.py (custom HMAC).
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from config import settings


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a signed JWT access token using the single configured secret."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_expire_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_access_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT access token.

    Returns the decoded payload dict, or None if the token is invalid/expired.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return payload
    except jwt.PyJWTError:
        return None
