"""URL normalization utilities for deduplication"""

from urllib.parse import urlparse, urlunparse
import re


def normalize_url(url: str) -> str:
    """
    Normalize URL for deduplication

    Rules:
    1. Remove trailing slashes
    2. Convert to lowercase (domain only)
    3. Remove www. prefix
    4. Remove query parameters (except for specific cases)
    5. Remove fragments (#)
    6. Normalize path separators

    Examples:
        https://t.me/durov/ -> https://t.me/durov
        https://T.me/Durov -> https://t.me/durov
        https://www.t.me/durov -> https://t.me/durov
        https://t.me/durov?start=xxx -> https://t.me/durov
        https://vk.com/club123 -> https://vk.com/club123
        https://instagram.com/username/ -> https://instagram.com/username

    Args:
        url: Source URL to normalize

    Returns:
        Normalized URL
    """
    if not url:
        return url

    # Strip whitespace
    url = url.strip()

    # Add https:// if no scheme
    if not url.startswith(('http://', 'https://')):
        # Handle @username format for Telegram
        if url.startswith('@'):
            url = f"https://t.me/{url[1:]}"
        else:
            url = f"https://{url}"

    # Parse URL
    parsed = urlparse(url)

    # Normalize domain (lowercase, remove www.)
    domain = parsed.netloc.lower()
    if domain.startswith('www.'):
        domain = domain[4:]

    # Normalize path (remove trailing slash, lowercase for specific platforms)
    path = parsed.path

    # Remove trailing slash
    if path.endswith('/') and path != '/':
        path = path[:-1]

    # For Telegram, VK, Instagram - keep path as is (case-sensitive usernames)
    # But normalize the structure
    if 't.me' in domain or 'telegram.me' in domain:
        # Telegram: normalize domain to t.me
        domain = 't.me'
        # Remove joinchat/ prefix variations
        path = re.sub(r'^/(joinchat|join)/', '/joinchat/', path)

    elif 'vk.com' in domain or 'vk.ru' in domain:
        # VK: normalize domain to vk.com
        domain = 'vk.com'
        # Normalize club/public/id paths
        path = re.sub(r'^/(club|public|id)(\d+)', r'/\1\2', path)

    elif 'instagram.com' in domain or 'instagr.am' in domain:
        # Instagram: normalize domain to instagram.com
        domain = 'instagram.com'

    # Reconstruct URL without query and fragment
    normalized = urlunparse((
        parsed.scheme,
        domain,
        path,
        '',  # params (empty)
        '',  # query (removed for dedup)
        ''   # fragment (removed)
    ))

    return normalized


def extract_handle_from_url(url: str) -> str:
    """
    Extract handle/username from normalized URL

    Examples:
        https://t.me/durov -> durov
        https://vk.com/club123 -> club123
        https://instagram.com/username -> username
        @channel -> channel

    Args:
        url: Source URL (normalized or not)

    Returns:
        Extracted handle/username
    """
    if not url:
        return ''

    # Handle @username format
    if url.startswith('@'):
        return url[1:]

    # Parse URL
    parsed = urlparse(url)
    path = parsed.path.strip('/')

    # Extract last part of path
    if '/' in path:
        parts = path.split('/')
        # For joinchat links, return the invite hash
        if 'joinchat' in parts:
            return path  # Keep full path for invite links
        # Otherwise return last part
        return parts[-1]

    return path
