"""Base scraper abstract class"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class for content scrapers

    All platform-specific scrapers must implement this interface
    """

    def __init__(self, url: str):
        """
        Initialize scraper with source URL

        Args:
            url: URL to the content source (channel, group, profile, etc.)
        """
        self.url = url
        self.platform = self._get_platform_name()

    @abstractmethod
    def _get_platform_name(self) -> str:
        """Return platform name: 'telegram', 'vk', or 'instagram'"""
        pass

    @abstractmethod
    async def verify(self) -> Dict[str, Any]:
        """
        Verify that the source is accessible and has enough content

        Returns:
            Dict with:
                - status: 'OK', 'CLOSED', 'LOW_CONTENT', 'INVALID_URL'
                - message: Human-readable message
                - posts_count: Number of available posts (optional)
                - handle: Account handle/username (optional)
                - is_private: Whether account is private (optional)
        """
        pass

    @abstractmethod
    async def scrape(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Scrape posts from the source

        Args:
            limit: Maximum number of posts to scrape

        Returns:
            List of normalized post dictionaries with fields:
                - platform_post_id: Unique post ID from platform
                - author_handle: Author username/handle
                - posted_at: Post datetime (datetime object or None)
                - text: Post text content
                - media: List of media items [{type: 'image'|'video', url: str}]
                - reactions: Dict of engagement metrics {likes, comments, views, shares}
                - link: Direct link to the post
                - raw: Raw API response for debugging
        """
        pass

    def normalize_datetime(self, dt: Any) -> Optional[datetime]:
        """
        Normalize different datetime formats to Python datetime

        Args:
            dt: Datetime in various formats (timestamp, string, datetime object)

        Returns:
            datetime object or None
        """
        if dt is None:
            return None

        if isinstance(dt, datetime):
            return dt

        if isinstance(dt, (int, float)):
            # Unix timestamp
            return datetime.fromtimestamp(dt)

        if isinstance(dt, str):
            # Try parsing ISO format
            try:
                return datetime.fromisoformat(dt.replace('Z', '+00:00'))
            except:
                pass

        return None

    def extract_handle_from_url(self, url: str) -> Optional[str]:
        """
        Extract username/handle from URL

        Override in subclasses for platform-specific extraction

        Args:
            url: Source URL

        Returns:
            Extracted handle or None
        """
        return None
