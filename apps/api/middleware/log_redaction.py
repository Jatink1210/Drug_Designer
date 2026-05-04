"""
Log Secret Redaction Utility.
Satisfies Section 16.4 (Logging safety).
Ensures API keys, tokens, and secrets are never written to log files in cleartext.
"""
import re
import logging
from typing import List, Tuple

# Patterns that match common secret formats + PII (§67.3)
SECRET_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r'(bearer\s+)([a-zA-Z0-9._\-]{10,})', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(api[_-]?key["\s:=]+)(["\']?)([a-zA-Z0-9_\-]{10,})', re.IGNORECASE), r'\1\2[REDACTED]'),
    (re.compile(r'(token["\s:=]+)(["\']?)([a-zA-Z0-9._\-]{10,})', re.IGNORECASE), r'\1\2[REDACTED]'),
    (re.compile(r'(secret["\s:=]+)(["\']?)([a-zA-Z0-9._\-]{10,})', re.IGNORECASE), r'\1\2[REDACTED]'),
    (re.compile(r'(password["\s:=]+)(["\']?)([^\s"\']{4,})', re.IGNORECASE), r'\1\2[REDACTED]'),
    (re.compile(r'(Authorization:\s*)(.{10,})', re.IGNORECASE), r'\1[REDACTED]'),
]

# §67.3: PII redaction — email addresses redacted as u***@domain.com
_EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')


def _redact_email(match: re.Match) -> str:
    email = match.group(0)
    local, domain = email.split("@", 1)
    return f"{local[0]}***@{domain}"


def redact_secrets(text: str) -> str:
    """Remove all secret patterns and PII from a log line (§67.3)."""
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    # §67.3: Redact email addresses as u***@domain.com
    text = _EMAIL_PATTERN.sub(_redact_email, text)
    return text


class RedactingFilter(logging.Filter):
    """Logging filter that redacts secrets from all log records."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_secrets(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(redact_secrets(str(a)) if isinstance(a, str) else a for a in record.args)
        return True


def install_redaction():
    """Install the secret redaction filter on the root logger."""
    root = logging.getLogger()
    root.addFilter(RedactingFilter())
    logging.getLogger(__name__).info("Log secret redaction filter installed.")
