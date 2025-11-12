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
from utils.local_media_storage import get_local_storage
from utils.safe_logging import get_safe_error_code
from utils.telegram_metadata import get_post_metadata

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
            # Start client (will prompt for phone/code on first run)
            await self.client.start()

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
            # Start client (will prompt for phone/code on first run)
            await self.client.start()

            # Get channel entity
            entity = await self.client.get_entity(self.handle)

            # Fetch messages
            messages: List[Message] = await self.client.get_messages(
                entity,
                limit=limit
            )

            posts = []

            # Try to use S3 if configured, otherwise use local storage
            storage = None
            storage_type = "none"
            try:
                if settings.aws_access_key_id and settings.aws_secret_access_key:
                    storage = get_s3_storage()
                    storage_type = "s3"
                    logger.info("Using S3 for media storage")
                else:
                    storage = get_local_storage()
                    storage_type = "local"
                    logger.info("Using local storage for media")
            except Exception as e:
                logger.warning(f"Storage not available, will skip media: {get_safe_error_code(e)}")

            for msg in messages:
                # Skip empty messages
                if not msg.message and not msg.media:
                    continue

                # Extract media
                media_list = []
                if storage and msg.media:
                    media_list = await self._process_media(msg, storage)

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

                # Extract and add metadata (hashtags, mentions, reactions, etc.)
                metadata = get_post_metadata(msg)
                post.update(metadata)

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

        Supports:
        - Photos (single and albums)
        - Videos
        - GIF/animations
        - Audio/voice messages
        - Video notes (round videos)
        - Documents (PDF, DOCX, etc.)

        Args:
            message: Telethon message object
            s3_storage: S3Storage instance

        Returns:
            List of media objects with type, URL, and metadata

        Example:
            [
                {
                    "type": "photo",
                    "url": "s3://aismm-media/telegram/abc123.jpg",
                    "grouped_id": "12345"  # Present if part of album
                },
                {
                    "type": "document",
                    "url": "s3://aismm-media/telegram/file.pdf",
                    "filename": "document.pdf",
                    "mime_type": "application/pdf",
                    "size": 1024000
                }
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
                    # Add grouped_id if this is part of an album
                    if message.grouped_id:
                        media_obj["grouped_id"] = str(message.grouped_id)
                    media_list.append(media_obj)

            # Handle document (video, gif, audio, file)
            elif isinstance(message.media, MessageMediaDocument):
                doc = message.media.document
                mime_type = doc.mime_type or ""

                # Get document attributes
                attributes = doc.attributes
                is_voice = False
                is_video_note = False
                is_animated = False
                filename = None

                for attr in attributes:
                    if hasattr(attr, 'voice') and attr.voice:
                        is_voice = True
                    if hasattr(attr, 'round_message') and attr.round_message:
                        is_video_note = True
                    if hasattr(attr, 'animated') and attr.animated:
                        is_animated = True
                    if hasattr(attr, 'file_name'):
                        filename = attr.file_name

                # Determine media type and process accordingly
                if is_video_note:
                    media_obj = await self._download_and_upload_document(
                        message, s3_storage, media_type="video_note"
                    )
                elif is_voice:
                    media_obj = await self._download_and_upload_document(
                        message, s3_storage, media_type="voice"
                    )
                elif mime_type.startswith('video/') or is_animated:
                    # Regular video or GIF/animation
                    if 'gif' in mime_type.lower() or is_animated:
                        media_type = "gif"
                    else:
                        media_type = "video"
                    media_obj = await self._download_and_upload_video(
                        message, s3_storage, media_type=media_type
                    )
                elif mime_type.startswith('audio/'):
                    media_obj = await self._download_and_upload_document(
                        message, s3_storage, media_type="audio"
                    )
                elif mime_type.startswith('image/'):
                    # Some images come as documents (stickers, etc)
                    media_obj = await self._download_and_upload_document(
                        message, s3_storage, media_type="image"
                    )
                else:
                    # Generic document (PDF, DOCX, etc.)
                    media_obj = await self._download_and_upload_document(
                        message, s3_storage, media_type="document"
                    )

                if media_obj:
                    # Add filename if available
                    if filename:
                        media_obj["filename"] = filename
                    # Add grouped_id if this is part of an album
                    if message.grouped_id:
                        media_obj["grouped_id"] = str(message.grouped_id)
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
        s3_storage,
        media_type: str = "video"
    ) -> Dict[str, str]:
        """
        Download video/gif and upload to S3

        Args:
            message: Telethon message with video
            s3_storage: S3Storage instance
            media_type: Type of media ("video" or "gif")

        Returns:
            Media object with type, URL, and metadata
        """
        temp_file = None
        try:
            doc = message.media.document
            mime_type = doc.mime_type or "video/mp4"
            extension = mime_type.split('/')[-1]  # e.g., "video/mp4" -> "mp4"

            # Create temporary file
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f'.{extension}'
            ) as f:
                temp_file = f.name

            # Download video (with size limit to avoid huge files)
            # Skip videos larger than 50MB
            file_size = doc.size
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
                # Get video duration if available
                duration = None
                for attr in doc.attributes:
                    if hasattr(attr, 'duration'):
                        duration = attr.duration
                        break

                result = {
                    "type": media_type,
                    "url": s3_url,
                    "mime_type": mime_type,
                    "size": file_size
                }

                if duration:
                    result["duration"] = duration

                return result

        except Exception as e:
            logger.error(f"Video processing error: {get_safe_error_code(e)}")
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

        return None

    async def _download_and_upload_document(
        self,
        message: Message,
        s3_storage,
        media_type: str = "document"
    ) -> Dict[str, str]:
        """
        Download document/audio/voice and upload to S3

        Supports:
        - Documents (PDF, DOCX, TXT, etc.)
        - Audio files
        - Voice messages
        - Video notes (round videos)
        - Images (as documents)

        Args:
            message: Telethon message with document
            s3_storage: S3Storage instance
            media_type: Type of media ("document", "audio", "voice", "video_note", "image")

        Returns:
            Media object with type, URL, and metadata
        """
        temp_file = None
        try:
            doc = message.media.document
            mime_type = doc.mime_type or "application/octet-stream"

            # Get file extension from mime type or filename
            extension = None
            filename = None

            # Try to get filename from attributes
            for attr in doc.attributes:
                if hasattr(attr, 'file_name') and attr.file_name:
                    filename = attr.file_name
                    # Extract extension from filename
                    if '.' in filename:
                        extension = filename.rsplit('.', 1)[1]
                    break

            # Fallback to mime type for extension
            if not extension:
                extension = mime_type.split('/')[-1]
                # Handle special cases
                if extension == 'octet-stream':
                    extension = 'bin'

            # Create temporary file
            with tempfile.NamedTemporaryFile(
                delete=False,
                suffix=f'.{extension}'
            ) as f:
                temp_file = f.name

            # Download document (with size limit)
            # Skip files larger than 100MB for documents, 20MB for audio/voice
            size_limit = 20 * 1024 * 1024 if media_type in ['audio', 'voice', 'video_note'] else 100 * 1024 * 1024
            file_size = doc.size

            if file_size > size_limit:
                logger.warning(f"{media_type} too large: {file_size} bytes, skipping")
                return None

            await self.client.download_media(message.media, temp_file)

            # Upload to S3
            s3_url = s3_storage.upload_file(
                temp_file,
                folder=f"telegram/{self.handle}",
                public=True
            )

            if s3_url:
                result = {
                    "type": media_type,
                    "url": s3_url,
                    "mime_type": mime_type,
                    "size": file_size
                }

                # Add filename if available
                if filename:
                    result["filename"] = filename

                # Extract additional metadata from attributes
                for attr in doc.attributes:
                    # Duration (for audio/voice/video_note)
                    if hasattr(attr, 'duration') and attr.duration:
                        result["duration"] = attr.duration

                    # Audio metadata
                    if hasattr(attr, 'title') and attr.title:
                        result["title"] = attr.title
                    if hasattr(attr, 'performer') and attr.performer:
                        result["performer"] = attr.performer

                    # Image dimensions
                    if hasattr(attr, 'w') and hasattr(attr, 'h'):
                        result["width"] = attr.w
                        result["height"] = attr.h

                return result

        except Exception as e:
            logger.error(f"Document processing error: {get_safe_error_code(e)}")
        finally:
            # Clean up temporary file
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

        return None
