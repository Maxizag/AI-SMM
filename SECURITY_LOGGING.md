# Security Guidelines: Logging & Data Storage

## Overview

This document outlines security practices for logging and data storage to prevent PII (Personally Identifiable Information) and sensitive data leakage.

## 1. Logging Best Practices

### ✅ DO: Log only safe information

**Allowed in logs:**
- Error types (e.g., `ValueError`, `ConnectionError`)
- Status codes and structured error codes (e.g., `PLATFORM_PRIVATE`)
- UUIDs (source_id, job_id, user_id)
- Counters and metrics (posts collected, retry count)
- Platform names (telegram, vk, instagram)
- Timestamps

**Example:**
```python
logger.info(f"Scraping source {source.id} ({source.platform})")
logger.error(f"Error scraping {source.id}: {get_safe_error_code(e)}")
```

### ❌ DON'T: Log sensitive data

**NEVER log:**
- Full error messages with URLs or tokens
- User handles or usernames
- Post content or text
- Email addresses or phone numbers
- API keys or JWT tokens
- Stack traces in production (contains code paths and values)
- Full exception messages (`str(e)` may contain sensitive data)

**Bad example:**
```python
# ❌ WRONG - may expose URLs with tokens
logger.error(f"Failed to fetch: {str(e)}")

# ❌ WRONG - exposes post content
logger.debug(f"Saving post: {post_data['text']}")
```

**Good example:**
```python
# ✅ CORRECT - only error type
logger.error(f"Failed to fetch: {get_safe_error_code(e)}")

# ✅ CORRECT - only post ID
logger.debug(f"Saving post: {post_data['platform_post_id']}")
```

## 2. Safe Logging Utilities

Use the utilities in `api/utils/safe_logging.py`:

### `get_safe_error_code(error: Exception) -> str`

Returns only the error type name without details.

```python
from utils.safe_logging import get_safe_error_code

try:
    scrape_url("https://example.com?token=secret123")
except Exception as e:
    # Logs only "ConnectionError" instead of full message
    logger.error(f"Scraping failed: {get_safe_error_code(e)}")
```

### `sanitize_error_message(error: Exception) -> str`

Returns error message with sensitive data redacted.

```python
from utils.safe_logging import sanitize_error_message

try:
    verify_source(url)
except Exception as e:
    # Redacts tokens, emails, phones, API keys
    safe_msg = sanitize_error_message(e)
    logger.error(f"Verification failed: {safe_msg}")
```

### `safe_log_dict(data: dict, max_length: int = 100) -> dict`

Truncates long values for logging.

```python
from utils.safe_logging import safe_log_dict

# Truncate long strings to prevent log spam
logger.debug(f"Processing: {safe_log_dict(post_data)}")
```

## 3. Raw Field in Posts

The `raw` field in the `Post` model **MUST NOT** contain:

❌ **Prohibited data:**
- Full API responses (may contain internal IDs, tokens)
- User profile information (email, phone, real name)
- Authentication tokens or session data
- Private user data (location, IP address)
- Complete message objects (use normalized fields instead)

✅ **Allowed data:**
- Non-sensitive metadata (post type, content format)
- Public metrics (view count, like count)
- Platform-specific IDs that are already public
- Empty object `{}` (safest option for mock data)

**Example:**
```python
# ❌ WRONG - contains full API response
"raw": msg.to_dict()

# ❌ WRONG - contains user profile
"raw": {"author": user.profile.to_dict()}

# ✅ CORRECT - empty or minimal metadata
"raw": {}

# ✅ CORRECT - only public metadata
"raw": {"post_type": "photo", "is_pinned": True}
```

## 4. Error Storage in Database

When storing errors in `source.meta` or `job.errors`:

✅ **DO:**
- Store error codes: `PLATFORM_PRIVATE`, `INVALID_URL`
- Store error types: `ConnectionError`, `ValueError`
- Store timestamps: `error_time`
- Store structured error objects with codes

❌ **DON'T:**
- Store full exception messages
- Store stack traces
- Store URLs with authentication tokens
- Store user input that may contain PII

**Example:**
```python
# ✅ CORRECT
source.meta = {
    'error_code': 'PLATFORM_PRIVATE',
    'error_type': 'PermissionError',
    'error_time': datetime.utcnow().isoformat()
}

# ❌ WRONG
source.meta = {
    'error': str(e),  # May contain sensitive data
    'traceback': traceback.format_exc()  # Exposes code paths
}
```

## 5. Celery Task Logging

Celery workers should follow the same rules:

✅ **DO:**
```python
logger.info(f"Started scraping job {job_id}")
logger.error(f"Job {job_id} failed: {get_safe_error_code(e)}")
```

❌ **DON'T:**
```python
logger.error(f"Job failed: {str(e)}", exc_info=True)  # Stack traces in production
logger.debug(f"Processing posts: {posts}")  # May contain post content
```

## 6. Environment-Specific Settings

### Development
- Full error messages and stack traces are OK
- Use `exc_info=True` for debugging
- Log more details for troubleshooting

### Production
- **NEVER** use `exc_info=True`
- Use `get_safe_error_code()` for all exceptions
- Minimize log verbosity
- Use structured logging with error codes

**Conditional logging:**
```python
import os

if os.getenv('ENV') == 'dev':
    logger.error(f"Error: {e}", exc_info=True)
else:
    logger.error(f"Error: {get_safe_error_code(e)}")
```

## 7. Compliance & Auditing

### GDPR Compliance
- Logs must not contain personal data
- Post content is personal data and must not be logged
- User handles/usernames are personal data

### Security Auditing
- Review logs before shipping to production
- Use `grep` to search for potential leaks:
  ```bash
  # Search for email patterns
  grep -r '@[a-zA-Z0-9]' logs/

  # Search for phone numbers
  grep -r '+[0-9]' logs/

  # Search for tokens
  grep -r 'token=' logs/
  ```

## 8. Code Review Checklist

Before merging code, verify:

- [ ] No `str(e)` or `{e}` in production log statements
- [ ] No post content in logs (`post_data['text']`)
- [ ] No URLs in logs (may contain tokens)
- [ ] No `exc_info=True` without environment check
- [ ] `raw` field contains only non-sensitive metadata
- [ ] Error storage uses codes, not full messages
- [ ] All scrapers use `get_safe_error_code()`

## 9. Incident Response

If sensitive data is logged:

1. **Immediately rotate** any exposed tokens/keys
2. **Purge logs** containing sensitive data
3. **Update code** to use safe logging utilities
4. **Audit** similar code paths for same issue
5. **Document** the incident and prevention steps

## 10. References

- `api/utils/safe_logging.py` - Safe logging utilities
- `api/tasks/scraping_tasks.py` - Example of safe Celery logging
- `api/services/scraping_service.py` - Example of safe service logging
- `api/scrapers/` - Example of safe scraper data handling
