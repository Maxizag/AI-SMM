"""Real Telegram scraper using Telethon"""

import logging
import os
import tempfile
from datetime import datetime
from typing import List, Dict, Any

from telethon import TelegramClient
from telethon.tl.types import (
    MessageMediaPhoto,
    MessageMediaDocument,
    MessageMediaWebPage,
    Message
)
from telethon.errors import (
    ChannelPrivateError,
    ChannelInvalidError,
    UsernameInvalidError,
    UsernameNotOccupiedError
)

from scrapers.base import BaseScraper
from config import get_settings
from utils.s3_storage import get_s3_storage
from utils.safe_logging import get_safe_error_code

logger = logging.getLogger(__name__)
settings = get_settings()


class TelegramScraper(BaseScraper):
    """
    Telegram scraper using Telethon (user-bot client)

    Features:
    - Scrape public channels and groups
    - Download photos and videos
    - Upload media to S3
    - Extract views, forwards, replies count
    - Handle private/invalid channels

    Requirements:
    - TELEGRAM_API_ID and TELEGRAM_API_HASH in .env
    - Telethon session (created on first run)
    """

    platform = "telegram"

    def __init__(self, url: str):
        """
        Initialize Telegram scraper

        Args:
            url: Telegram channel URL (e.g., https://t.me/channel or @channel)
        """
        super().__init__(url)

        # Parse handle from URL
        self.handle = self._parse_handle(url)

        # Initialize Telethon client
        self.client = None
        self._init_client()

    def _get_platform_name(self) -> str:
        return "telegram"

    def _parse_handle(self, url: str) -> str:
        """
        Parse Telegram handle from URL

        Supports formats:
        - https://t.me/channel
        - t.me/channel
        - @channel
        - channel

        Returns:
            Clean handle without @ or https://
        """
        url = url.strip()

        # Remove https:// and http://
        if url.startswith('https://'):
            url = url[8:]
        elif url.startswith('http://'):
            url = url[7:]

        # Remove t.me/
        if url.startswith('t.me/'):
            url = url[5:]

        # Remove @ prefix
        if url.startswith('@'):
            url = url[1:]

        # Remove trailing slashes
        url = url.rstrip('/')

        return url

    def _init_client(self):
        """
        Initialize Telethon client with credentials from settings

        Raises:
            ValueError: If API credentials are not configured
        """
        if not settings.telegram_api_id or not settings.telegram_api_hash:
            raise ValueError(
                "Telegram API credentials not configured. "
                "Please set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env"
            )

        self.client = TelegramClient(
            settings.telegram_session_name,
            settings.telegram_api_id,
            settings.telegram_api_hash
        )

    async def verify(self) -> Dict[str, Any]:
        """
        Verify Telegram channel accessibility

        Returns:
            Verification result with status, handle, is_private, posts_count
        """
        try:
            await self.client.connect()

            # Try to get channel entity
            try:
                entity = await self.client.get_entity(self.handle)
            except (ChannelPrivateError, ChannelInvalidError):
                return {
                    'status': 'CLOSED',
                    'handle': f"@{self.handle}",
                    'is_private': True,
                    'posts_count': 0,
                    'message': 'Channel is private or unavailable'
                }
            except (UsernameInvalidError, UsernameNotOccupiedError):
                return {
                    'status': 'INVALID_URL',
                    'handle': f"@{self.handle}",
                    'is_private': False,
                    'posts_count': 0,
                    'message': 'Invalid channel username'
                }

            # Get channel info
            is_private = getattr(entity, 'restricted', False)

            # Try to get message count
            try:
                # Get last few messages to estimate count
                messages = await self.client.get_messages(entity, limit=1)
                if messages:
                    # Last message ID gives approximate post count
                    posts_count = messages[0].id
                else:
                    posts_count = 0
            except Exception:
                posts_count = 0

            # Determine status
            if is_private:
                status = 'CLOSED'
            elif posts_count < 50:
                status = 'LOW_CONTENT'
            else:
                status = 'OK'

            return {
                'status': status,
                'handle': f"@{self.handle}",
                'is_private': is_private,
                'posts_count': posts_count,
                'message': f"Channel verified: {posts_count} posts"
            }

        except Exception as e:
            logger.error(f"Telegram verification error: {get_safe_error_code(e)}")
            return {
                'status': 'ERROR',
                'handle': f"@{self.handle}",
                'is_private': False,
                'posts_count': 0,
                'message': 'Verification failed'
            }
        finally:
            if self.client:
                await self.client.disconnect()

    async def scrape(self, limit: int = 200) -> List[Dict[str, Any]]:
        """
        Scrape posts from Telegram channel

        Args:
            limit: Maximum number of posts to scrape (default: 200)

        Returns:
            List of normalized post dictionaries

        Post format:
        {
            "platform_post_id": str,
            "author_handle": str,
            "posted_at": datetime,
            "text": str,
            "media": [{"type": "photo|video", "url": "s3://..."}],
            "reactions": {"views": int, "forwards": int, "comments": int},
            "link": str,
            "raw": {}  # Empty for security
        }
        """
        try:
            await self.client.connect()

            # Get channel entity
            entity = await self.client.get_entity(self.handle)

            # Fetch messages
            messages: List[Message] = await self.client.get_messages(
                entity,
                limit=limit
            )

            posts = []
            s3_storage = get_s3_storage()

            for msg in messages:
                # Skip empty messages
                if not msg.message and not msg.media:
                    continue

                # Extract media
                media_list = await self._process_media(msg, s3_storage)

                # Build post object
                post = {
                    "platform_post_id": str(msg.id),
                    "author_handle": f"@{self.handle}",
                    "posted_at": msg.date,
                    "text": msg.message or "",
                    "media": media_list,
                    "reactions": {
                        "views": msg.views or 0,
                        "forwards": msg.forwards or 0,
                        "comments": msg.replies.replies if msg.replies else 0
                    },
                    "link": f"https://t.me/{self.handle}/{msg.id}",
                    # SECURITY: raw must NOT contain PII, tokens, or full message data
                    # Only store non-sensitive metadata needed for debugging
                    "raw": {}
                }

                posts.append(post)

            logger.info(f"Scraped {len(posts)} posts from Telegram @{self.handle}")
            return posts

        except (ChannelPrivateError, ChannelInvalidError) as e:
            logger.error(f"Channel access error: {get_safe_error_code(e)}")
            raise ValueError("Channel is private or unavailable")
        except Exception as e:
            logger.error(f"Telegram scraping error: {get_safe_error_code(e)}")
            raise
        finally:
            if self.client:
                await self.client.disconnect()

    async def _process_media(
        self,
        message: Message,
        s3_storage
    ) -> List[Dict[str, str]]:
        """
        Download and upload media files to S3

        Args:
            message: Telethon message object
            s3_storage: S3Storage instance

        Returns:
            List of media objects with type and S3 URL

        Example:
            [
                {"type": "photo", "url": "s3://aismm-media/telegram/abc123.jpg"},
                {"type": "video", "url": "s3://aismm-media/telegram/xyz789.mp4"}
            ]
        """
        media_list = []

        if not message.media:
            return media_list

        try:
            # Handle photo
            if isinstance(message.media, MessageMediaPhoto):
                media_obj = await self._download_and_upload_photo(
                    message,
                    s3_storage
                )
                if media_obj:
                    media_list.append(media_obj)

            # Handle video/document
            elif isinstance(message.media, MessageMediaDocument):
                # Check if it's a video
                if message.media.document.mime_type.startswith('video/'):
                    media_obj = await self._download_and_upload_video(
                        message,
                        s3_storage
                    )
                    if media_obj:
                        media_list.append(media_obj)

        except Exception as e:
            # Log only error type (security: no media URLs in logs)
            logger.warning(f"Failed to process media: {get_safe_error_code(e)}")

        return media_list

    async def _download_and_upload_photo(
        self,
        message: Message,
        s3_storage
    ) -> Dict[str, str]:
        """
        Download photo and upload to S3

        Args:
            message: Telethon message with photo
            s3_storage: S3Storage instance

        Returns:
            Media object with type and S3 URL
        """
        temp_file = None
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as f:
                temp_file = f.name

            # Download photo
            await self.client.download_media(message.media, temp_file)

            # Upload to S3
            s3_url = s3_storage.upload_file(
                temp_file,
                folder=f"telegram/{self.handle}",
                public=True
            )

            if s3_url:
                return {"type": "photo", "url": s3_url}

        except Exception as e:
            logger.error(f"Photo processing error: {get_safe_error_code(e)}")
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

        return None

    async def _download_and_upload_video(
        self,
        message: Message,
        s3_storage
    ) -> Dict[str, str]:
        """
        Download video and upload to S3

        Args:
            message: Telethon message with video
            s3_storage: S3Storage instance

        Returns:
            Media object with type and S3 URL
        """
        temp_file = None
        try:
            # Get file extension from mime type
            mime_type = message.media.document.mime_type
            extension = mime_type.split('/')[-1]  # e.g., "video/mp4" -> "mp4"

            # Create temporary file
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f'.{extension}'
            ) as f:
                temp_file = f.name

            # Download video (with size limit to avoid huge files)
            # Skip videos larger than 50MB
            file_size = message.media.document.size
            if file_size > 50 * 1024 * 1024:  # 50MB
                logger.warning(f"Video too large: {file_size} bytes, skipping")
                return None

            await self.client.download_media(message.media, temp_file)

            # Upload to S3
            s3_url = s3_storage.upload_file(
                temp_file,
                folder=f"telegram/{self.handle}",
                public=True
            )

            if s3_url:
                return {"type": "video", "url": s3_url}

        except Exception as e:
            logger.error(f"Video processing error: {get_safe_error_code(e)}")
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

        return None
