"""Safe logging utilities to prevent PII leakage in logs"""

import re
from typing import Any


def sanitize_error_message(error: Exception) -> str:
    """
    Sanitize error message to remove potentially sensitive information

    Removes:
    - URLs with auth tokens
    - Email addresses
    - Phone numbers
    - API keys
    - JWT tokens

    Args:
        error: Exception to sanitize

    Returns:
        Safe error message with only error type and generic info
    """
    error_type = type(error).__name__
    error_msg = str(error)

    # Remove URLs with tokens/credentials
    error_msg = re.sub(r'https?://[^\s]*(?:token|key|secret|password)=[^\s&]*', '[REDACTED_URL]', error_msg, flags=re.IGNORECASE)

    # Remove email addresses
    error_msg = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', error_msg)

    # Remove phone numbers (basic pattern)
    error_msg = re.sub(r'\+?\d{10,15}', '[PHONE]', error_msg)

    # Remove JWT tokens
    error_msg = re.sub(r'eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}', '[JWT_TOKEN]', error_msg)

    # Remove API keys (patterns like: sk-xxx, api_xxx)
    error_msg = re.sub(r'\b(?:sk|api|key)[-_][A-Za-z0-9]{20,}\b', '[API_KEY]', error_msg, flags=re.IGNORECASE)

    # Truncate long messages
    if len(error_msg) > 200:
        error_msg = error_msg[:197] + '...'

    return f"{error_type}: {error_msg}"


def get_safe_error_code(error: Exception) -> str:
    """
    Get only error type without details for logging

    Args:
        error: Exception

    Returns:
        Error type name (e.g., "ValueError", "ConnectionError")
    """
    return type(error).__name__


def safe_log_dict(data: dict, max_length: int = 100) -> dict:
    """
    Create safe version of dict for logging by truncating long values

    Args:
        data: Dictionary to sanitize
        max_length: Maximum length for string values

    Returns:
        Safe dictionary with truncated values
    """
    safe_data = {}

    for key, value in data.items():
        if isinstance(value, str) and len(value) > max_length:
            safe_data[key] = value[:max_length] + '...[truncated]'
        elif isinstance(value, (dict, list)):
            safe_data[key] = '[complex_object]'
        else:
            safe_data[key] = value

    return safe_data
