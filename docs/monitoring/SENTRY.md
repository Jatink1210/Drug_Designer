# Drug Designer - Sentry Error Tracking

## Overview

Sentry provides real-time error tracking, performance monitoring, and alerting for the Drug Designer platform. This document describes the Sentry configuration, usage, and best practices.

**Task**: 15.3 Set up Sentry error tracking  
**Priority**: P2  
**Requirements**: NFR-MAIN-002 (Monitoring & Observability)

## Configuration

### Environment Variables

```bash
# Required
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# Optional
DSS_ENV=production                    # Environment name (development, staging, production)
SENTRY_RELEASE=drug-designer@1.0.0   # Release version
SENTRY_TRACES_SAMPLE_RATE=0.1        # Performance monitoring sample rate (0.0-1.0)
SENTRY_PROFILES_SAMPLE_RATE=0.1      # Profiling sample rate (0.0-1.0)
```

### Initialization

Sentry is automatically initialized when the application starts if `SENTRY_DSN` is configured:

```python
from apps.api.core.sentry_config import configure_sentry

# Called automatically on module import
configure_sentry()
```

## Features

### 1. Automatic Error Capture

All unhandled exceptions are automatically captured and sent to Sentry:

```python
# This error will be automatically captured
raise ValueError("Something went wrong")
```

### 2. Performance Monitoring

API request performance is automatically tracked:

- Request duration
- Database query performance
- External API calls
- Model inference time

Sample rate is controlled by `SENTRY_TRACES_SAMPLE_RATE` (default: 10%).

### 3. User Context

Set user context for better error tracking:

```python
from apps.api.core.sentry_config import set_user_context

set_user_context(
    user_id="user-123",
    username="john.doe"
)
```

### 4. Custom Tags

Add custom tags to events:

```python
from apps.api.core.sentry_config import set_tag

set_tag("module", "clinical_workflow")
set_tag("stage", "ehr_ingestion")
```

### 5. Breadcrumbs

Add breadcrumbs to track user actions:

```python
from apps.api.core.sentry_config import add_breadcrumb

add_breadcrumb(
    message="User started clinical workflow",
    category="workflow",
    level="info",
    data={"workflow_id": "wf-123"}
)
```

### 6. Manual Error Capture

Capture exceptions manually:

```python
from apps.api.core.sentry_config import capture_exception

try:
    risky_operation()
except Exception as e:
    capture_exception(e, context={
        "operation": "risky_operation",
        "user_id": "user-123"
    })
```

### 7. Manual Message Capture

Capture messages manually:

```python
from apps.api.core.sentry_config import capture_message

capture_message(
    "Clinical workflow completed successfully",
    level="info",
    context={"workflow_id": "wf-123"}
)
```

## PII/PHI Scrubbing (HIPAA Compliance)

Sentry is configured to automatically scrub PII/PHI data before sending events:

### Scrubbed Data

- **Patient IDs**: Replaced with `[Filtered]`
- **Email addresses**: Replaced with `[EMAIL]`
- **Phone numbers**: Replaced with `[PHONE]`
- **SSN**: Replaced with `[SSN]`
- **Credit card numbers**: Replaced with `[CARD]`
- **Authorization headers**: Replaced with `[Filtered]`
- **API keys**: Replaced with `[Filtered]`
- **Passwords**: Replaced with `[Filtered]`

### Scrubbing Implementation

The `before_send` hook in `apps/api/core/sentry_config.py` scrubs all PII/PHI data:

```python
def before_send(event, hint):
    # Scrub PII/PHI from event data
    event = scrub_pii(event)
    return event
```

### Verification

To verify PII scrubbing:

1. Trigger an error with PII data
2. Check Sentry event details
3. Verify all PII is replaced with `[Filtered]` or similar

## Error Filtering

Certain errors are automatically filtered and not sent to Sentry:

### Ignored Errors

- **404 Not Found**: Client-side routing errors
- **401 Unauthorized**: Authentication failures
- **429 Rate Limit**: Rate limiting errors
- **Cancelled Requests**: User-cancelled operations
- **Health Check Failures**: `/api/health` endpoint errors

### Custom Filtering

Add custom filtering in `should_ignore_error()`:

```python
def should_ignore_error(event, hint):
    # Ignore specific error types
    if "SpecificError" in str(hint.get("exc_info")):
        return True
    return False
```

## Integrations

### FastAPI Integration

Automatically captures:
- Unhandled exceptions
- Request/response data
- Performance metrics

### SQLAlchemy Integration

Automatically captures:
- Database query errors
- Connection errors
- Query performance

### Redis Integration

Automatically captures:
- Redis connection errors
- Command errors

### Logging Integration

Automatically captures:
- Error-level log messages
- Exception stack traces

## Alerting

### Slack Alerts

Configure Slack alerts in Sentry dashboard:

1. Go to Settings → Integrations → Slack
2. Connect Slack workspace
3. Configure alert rules:
   - New issue created
   - Issue frequency threshold
   - Issue regression

### Email Alerts

Configure email alerts in Sentry dashboard:

1. Go to Settings → Alerts
2. Create alert rule
3. Set conditions:
   - Error rate > 1%
   - New error type
   - Error spike (10x increase)

### PagerDuty Integration

For critical errors:

1. Go to Settings → Integrations → PagerDuty
2. Connect PagerDuty account
3. Configure escalation policies

## Dashboard

### Key Metrics

- **Error Rate**: Errors per minute
- **Affected Users**: Number of users experiencing errors
- **Error Frequency**: Most common errors
- **Performance**: p95 request duration
- **Release Health**: Crash-free sessions

### Custom Dashboards

Create custom dashboards for:
- Clinical workflow errors
- Connector failures
- Model inference errors
- Database errors

## Best Practices

### 1. Use Releases

Tag deployments with release versions:

```bash
export SENTRY_RELEASE=drug-designer@1.2.3
```

This enables:
- Release tracking
- Regression detection
- Commit tracking

### 2. Set Appropriate Sample Rates

- **Development**: 100% (1.0)
- **Staging**: 50% (0.5)
- **Production**: 10% (0.1)

Lower sample rates reduce costs and noise.

### 3. Add Context

Always add context to manual captures:

```python
capture_exception(error, context={
    "module": "clinical_workflow",
    "stage": "ehr_ingestion",
    "user_id": "user-123",
    "workflow_id": "wf-123"
})
```

### 4. Use Breadcrumbs

Add breadcrumbs for user actions:

```python
add_breadcrumb("User clicked 'Start Workflow'", category="ui")
add_breadcrumb("Workflow started", category="workflow")
add_breadcrumb("Stage 1 completed", category="workflow")
```

### 5. Tag Errors

Use tags for filtering and grouping:

```python
set_tag("component", "api")
set_tag("module", "clinical_workflow")
set_tag("environment", "production")
```

### 6. Monitor Performance

Enable performance monitoring to track:
- Slow API endpoints
- Slow database queries
- Slow external API calls

### 7. Review Regularly

- Review new errors daily
- Triage and assign errors
- Set up alerts for critical errors
- Monitor error trends

## Troubleshooting

### Sentry Not Capturing Errors

1. **Check DSN**: Verify `SENTRY_DSN` is set
2. **Check Network**: Ensure Sentry.io is accessible
3. **Check Filtering**: Verify error is not filtered by `should_ignore_error()`
4. **Check Sample Rate**: Increase sample rate for testing

### Too Many Events

1. **Increase Filtering**: Filter more error types
2. **Reduce Sample Rate**: Lower `SENTRY_TRACES_SAMPLE_RATE`
3. **Set Rate Limits**: Configure rate limits in Sentry dashboard
4. **Group Similar Errors**: Use fingerprinting to group similar errors

### PII Leakage

1. **Review Scrubbing**: Check `scrub_pii()` function
2. **Add Patterns**: Add new PII patterns to `scrub_text()`
3. **Test Thoroughly**: Test with real PII data in development
4. **Audit Events**: Regularly audit Sentry events for PII

### Performance Impact

1. **Reduce Sample Rate**: Lower performance monitoring sample rate
2. **Disable Profiling**: Set `SENTRY_PROFILES_SAMPLE_RATE=0`
3. **Filter Events**: Filter more event types
4. **Use Async**: Sentry SDK sends events asynchronously

## Cost Optimization

### Event Quotas

Set monthly event quotas in Sentry dashboard:
- Errors: 10,000/month
- Transactions: 100,000/month
- Attachments: 1GB/month

### Spike Protection

Enable spike protection to prevent cost overruns:
- Automatically reduce sample rate during spikes
- Set maximum events per hour

### Data Retention

Configure data retention:
- Errors: 90 days
- Performance: 30 days
- Replays: 30 days

## Security

### Access Control

- Use role-based access control (RBAC)
- Limit access to production events
- Require 2FA for admin access

### API Keys

- Rotate DSN keys regularly
- Use separate keys for each environment
- Revoke compromised keys immediately

### Audit Logs

- Enable audit logging in Sentry
- Review access logs regularly
- Monitor for suspicious activity

## Support

### Resources

- **Sentry Documentation**: https://docs.sentry.io/
- **Python SDK**: https://docs.sentry.io/platforms/python/
- **FastAPI Integration**: https://docs.sentry.io/platforms/python/guides/fastapi/

### Contact

For issues or questions:
- Check Sentry status: https://status.sentry.io/
- Contact DevOps team
- Open support ticket

---

**Last Updated**: Task 15.3 Implementation  
**Version**: 1.0  
**Status**: Complete
