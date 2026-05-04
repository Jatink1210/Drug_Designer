"""Field-level PII encryption using Fernet (§N-3).

When ENCRYPTION_KEY is set in settings, EncryptedString encrypts on write
and decrypts on read. Falls back to plaintext when key is absent (dev mode).

Usage in SQLAlchemy models:
    from core.pii_encryption import EncryptedString
    email = Column(EncryptedString(512), nullable=False)
"""
from __future__ import annotations

import base64
import hashlib
import os

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator


def _get_fernet():
    """Return a Fernet instance from ENCRYPTION_KEY, or None if key is absent."""
    try:
        from config import settings
        key = settings.encryption_key
    except Exception:
        key = os.environ.get("ENCRYPTION_KEY", "")

    if not key:
        return None

    try:
        from cryptography.fernet import Fernet  # type: ignore

        # Derive a 32-byte URL-safe base64-encoded key if the raw key isn't already one
        raw = key.encode() if isinstance(key, str) else key
        if len(raw) != 44:  # Fernet keys are 44 base64 chars (32 bytes)
            derived = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
        else:
            derived = raw
        return Fernet(derived)
    except ImportError:
        # cryptography not installed — skip encryption silently
        return None
    except Exception:
        return None


class EncryptedString(TypeDecorator):
    """SQLAlchemy type that transparently encrypts/decrypts string values.

    When ENCRYPTION_KEY is set, values are stored as Fernet ciphertext.
    When key is absent, values are stored as plaintext (backward-compat).
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        """Encrypt on write."""
        if value is None:
            return value
        fernet = _get_fernet()
        if fernet is None:
            return value
        return fernet.encrypt(value.encode()).decode()

    def process_result_value(self, value: str | None, dialect) -> str | None:
        """Decrypt on read."""
        if value is None:
            return value
        fernet = _get_fernet()
        if fernet is None:
            return value
        try:
            return fernet.decrypt(value.encode()).decode()
        except Exception:
            # Value may already be plaintext (pre-encryption migration)
            return value
