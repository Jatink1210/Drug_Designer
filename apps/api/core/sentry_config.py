"""Sentry Error Tracking Configuration.

Task 15.3: Set up Sentry error tracking
NFR-MAIN-002: Monitoring & Observability

This module configures Sentry for error tracking, performance monitoring,
and alerting across the Drug Designer platform.

Features:
- Automatic error capture and grouping
- Performance transaction tracking
- User context and breadcrumbs
- Release tracking
- Environment-specific configuration
- PII scrubbing for HIPAA compliance
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional
import structlog

log = structlog.get_logger(__name__)

# Sentry configuration
SENTRY_DSN = os.getenv("SENTRY_DSN")
SENTRY_ENVIRONMENT = os.getenv("DSS_ENV", "development")
SENTRY_RELEASE = os.getenv("SENTRY_RELEASE", "drug-designer@1.0.0")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
SENTRY_PROFILES_SAMPLE_RATE = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1"))


def before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Filter and scrub events before sending to Sentry.
    
    This function:
    - Scrubs PII/PHI data for HIPAA compliance
    - Filters out known non-critical errors
    - Adds custom context
    
    Args:
        event: Sentry event dictionary
        hint: Additional context about the event
    
    Returns:
        Modified event or None to drop the event
    """
    # Scrub PII/PHI from event data
    event = scrub_pii(event)
    
    # Filter out known non-critical errors
    if should_ignore_error(event, hint):
        return None
    
    # Add custom tags
    event.setdefault("tags", {})
    event["tags"]["component"] = "api"
    
    return event


def scrub_pii(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Scrub PII/PHI data from Sentry events for HIPAA compliance.
    
    Removes:
    - Patient IDs
    - Email addresses
    - IP addresses (already hashed in audit logs)
    - Sensitive query parameters
    - Authorization headers
    
    Args:
        event: Sentry event dictionary
    
    Returns:
        Scrubbed event dictionary
    """
    # Scrub request data
    if "request" in event:
        request = event["request"]
        
        # Scrub headers
        if "headers" in request:
            headers = request["headers"]
            sensitive_headers = ["Authorization", "Cookie", "X-API-Key"]
            for header in sensitive_headers:
                if header in headers:
                    headers[header] = "[Filtered]"
        
        # Scrub query parameters
        if "query_string" in request:
            # Remove patient_id, email, etc.
            request["query_string"] = scrub_query_string(request["query_string"])
        
        # Scrub POST data
        if "data" in request:
            request["data"] = scrub_data(request["data"])
    
    # Scrub exception data
    if "exception" in event:
        for exception in event["exception"].get("values", []):
            if "value" in exception:
                exception["value"] = scrub_text(exception["value"])
    
    # Scrub breadcrumbs
    if "breadcrumbs" in event:
        for breadcrumb in event["breadcrumbs"].get("values", []):
            if "message" in breadcrumb:
                breadcrumb["message"] = scrub_text(breadcrumb["message"])
            if "data" in breadcrumb:
                breadcrumb["data"] = scrub_data(breadcrumb["data"])
    
    return event


def scrub_query_string(query_string: str) -> str:
    """Scrub sensitive data from query strings."""
    import re
    
    # Remove patient_id, email, etc.
    patterns = [
        (r'patient_id=[^&]+', 'patient_id=[Filtered]'),
        (r'email=[^&]+', 'email=[Filtered]'),
        (r'phone=[^&]+', 'phone=[Filtered]'),
    ]
    
    for pattern, replacement in patterns:
        query_string = re.sub(pattern, replacement, query_string)
    
    return query_string


def scrub_data(data: Any) -> Any:
    """Recursively scrub sensitive data from dictionaries and lists."""
    if isinstance(data, dict):
        scrubbed = {}
        sensitive_keys = [
            "patient_id", "email", "phone", "ssn", "password",
            "api_key", "token", "secret", "authorization"
        ]
        
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                scrubbed[key] = "[Filtered]"
            else:
                scrubbed[key] = scrub_data(value)
        
        return scrubbed
    
    elif isinstance(data, list):
        return [scrub_data(item) for item in data]
    
    elif isinstance(data, str):
        return scrub_text(data)
    
    else:
        return data


def scrub_text(text: str) -> str:
    """Scrub PII patterns from text."""
    import re
    
    # Email addresses
    text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
    
    # Phone numbers (various formats)
    text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE]', text)
    
    # SSN
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)
    
    # Credit card numbers
    text = re.sub(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CARD]', text)
    
    return text


def should_ignore_error(event: Dict[str, Any], hint: Dict[str, Any]) -> bool:
    """
    Determine if an error should be ignored.
    
    Ignores:
    - Known client-side errors (404, 401)
    - Rate limit errors (429)
    - Cancelled requests
    - Health check failures
    
    Args:
        event: Sentry event dictionary
        hint: Additional context about the event
    
    Returns:
        True if error should be ignored, False otherwise
    """
    # Ignore 404 errors
    if event.get("request", {}).get("status_code") == 404:
        return True
    
    # Ignore 401 unauthorized errors
    if event.get("request", {}).get("status_code") == 401:
        return True
    
    # Ignore 429 rate limit errors
    if event.get("request", {}).get("status_code") == 429:
        return True
    
    # Ignore cancelled requests
    if "exception" in event:
        for exception in event["exception"].get("values", []):
            if "CancelledError" in exception.get("type", ""):
                return True
            if "asyncio.CancelledError" in exception.get("type", ""):
                return True
    
    # Ignore health check failures
    if "/api/health" in event.get("request", {}).get("url", ""):
        return True
    
    return False


def configure_sentry():
    """
    Configure Sentry SDK with custom settings.
    
    This function should be called during application startup.
    """
    if not SENTRY_DSN:
        log.info("sentry_disabled", reason="no_dsn_configured")
        return
    
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.redis import RedisIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        
        # Configure logging integration
        logging_integration = LoggingIntegration(
            level=None,  # Capture all logs
            event_level="error"  # Send errors as events
        )
        
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            environment=SENTRY_ENVIRONMENT,
            release=SENTRY_RELEASE,
            
            # Performance monitoring
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
            profiles_sample_rate=SENTRY_PROFILES_SAMPLE_RATE,
            
            # Integrations
            integrations=[
                FastApiIntegration(),
                StarletteIntegration(),
                SqlalchemyIntegration(),
                RedisIntegration(),
                logging_integration,
            ],
            
            # Event filtering and scrubbing
            before_send=before_send,
            
            # Additional options
            attach_stacktrace=True,
            send_default_pii=False,  # HIPAA compliance
            max_breadcrumbs=50,
            debug=SENTRY_ENVIRONMENT == "development",
            
            # Performance options
            _experiments={
                "profiles_sample_rate": SENTRY_PROFILES_SAMPLE_RATE,
            },
        )
        
        log.info(
            "sentry_initialized",
            environment=SENTRY_ENVIRONMENT,
            release=SENTRY_RELEASE,
            traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE
        )
        
    except ImportError:
        log.warning("sentry_sdk_not_installed")
    except Exception as e:
        log.error("sentry_initialization_failed", error=str(e))


def capture_exception(error: Exception, context: Optional[Dict[str, Any]] = None):
    """
    Manually capture an exception to Sentry.
    
    Args:
        error: Exception to capture
        context: Additional context to attach to the event
    """
    try:
        import sentry_sdk
        
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_context(key, value)
                sentry_sdk.capture_exception(error)
        else:
            sentry_sdk.capture_exception(error)
            
    except ImportError:
        log.warning("sentry_sdk_not_installed")
    except Exception as e:
        log.error("sentry_capture_failed", error=str(e))


def capture_message(message: str, level: str = "info", context: Optional[Dict[str, Any]] = None):
    """
    Manually capture a message to Sentry.
    
    Args:
        message: Message to capture
        level: Severity level ("debug", "info", "warning", "error", "fatal")
        context: Additional context to attach to the event
    """
    try:
        import sentry_sdk
        
        if context:
            with sentry_sdk.push_scope() as scope:
                for key, value in context.items():
                    scope.set_context(key, value)
                sentry_sdk.capture_message(message, level=level)
        else:
            sentry_sdk.capture_message(message, level=level)
            
    except ImportError:
        log.warning("sentry_sdk_not_installed")
    except Exception as e:
        log.error("sentry_capture_failed", error=str(e))


def set_user_context(user_id: str, email: Optional[str] = None, username: Optional[str] = None):
    """
    Set user context for Sentry events.
    
    Note: Email is scrubbed for HIPAA compliance.
    
    Args:
        user_id: User ID (anonymized)
        email: User email (will be scrubbed)
        username: Username
    """
    try:
        import sentry_sdk
        
        sentry_sdk.set_user({
            "id": user_id,
            "username": username,
            # Email is scrubbed by before_send
        })
        
    except ImportError:
        pass
    except Exception as e:
        log.error("sentry_set_user_failed", error=str(e))


def set_tag(key: str, value: str):
    """
    Set a tag for Sentry events.
    
    Args:
        key: Tag key
        value: Tag value
    """
    try:
        import sentry_sdk
        sentry_sdk.set_tag(key, value)
    except ImportError:
        pass
    except Exception as e:
        log.error("sentry_set_tag_failed", error=str(e))


def add_breadcrumb(message: str, category: str = "default", level: str = "info", data: Optional[Dict[str, Any]] = None):
    """
    Add a breadcrumb to Sentry events.
    
    Args:
        message: Breadcrumb message
        category: Breadcrumb category
        level: Severity level
        data: Additional data
    """
    try:
        import sentry_sdk
        
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data or {}
        )
        
    except ImportError:
        pass
    except Exception as e:
        log.error("sentry_add_breadcrumb_failed", error=str(e))


# Initialize Sentry on module import
configure_sentry()
