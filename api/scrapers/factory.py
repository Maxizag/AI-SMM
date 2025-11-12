"""Scraper factory for instantiating platform-specific scrapers"""

import re
from typing import Optional
from .base import BaseScraper
from .telegram import TelegramScraper
from .vk import VKScraper
from .instagram import InstagramScraper


class ScraperFactory:
    """
    Factory class for creating platform-specific scrapers

    Automatically detects platform from URL and returns appropriate scraper
    """

    @staticmethod
    def detect_platform(url: str) -> Optional[str]:
        """
        Detect social media platform from URL

        Args:
            url: Source URL

        Returns:
            Platform name: 'telegram', 'vk', 'instagram', or None if unknown
        """
        url_lower = url.lower()

        if 't.me' in url_lower or url.startswith('@'):
            return 'telegram'
        elif 'vk.com' in url_lower or 'vkontakte' in url_lower:
            return 'vk'
        elif 'instagram.com' in url_lower:
            return 'instagram'

        return None

    @staticmethod
    def create_scraper(
        url: str,
        platform: Optional[str] = None,
        **kwargs
    ) -> BaseScraper:
        """
        Create appropriate scraper for the given URL

        Args:
            url: Source URL
            platform: Force specific platform (optional, will auto-detect if not provided)
            **kwargs: Platform-specific arguments:
                - telegram: progress_callback (optional callback for progress tracking)
                - vk: access_token
                - instagram: session_file

        Returns:
            Instance of platform-specific scraper

        Raises:
            ValueError: If platform cannot be detected or is unsupported
        """
        # Auto-detect platform if not provided
        if not platform:
            platform = ScraperFactory.detect_platform(url)

        if not platform:
            raise ValueError(f"Could not detect platform from URL: {url}")

        # Create platform-specific scraper
        if platform == 'telegram':
            # Telegram credentials come from settings (config.py/.env)
            # Optional progress callback can be passed
            progress_callback = kwargs.get('progress_callback')
            return TelegramScraper(url, progress_callback=progress_callback)

        elif platform == 'vk':
            access_token = kwargs.get('access_token')
            return VKScraper(url, access_token=access_token)

        elif platform == 'instagram':
            session_file = kwargs.get('session_file')
            return InstagramScraper(url, session_file=session_file)

        else:
            raise ValueError(f"Unsupported platform: {platform}")

    @staticmethod
    def get_supported_platforms() -> list:
        """
        Get list of supported platforms

        Returns:
            List of supported platform names
        """
        return ['telegram', 'vk', 'instagram']
