"""Service for orchestrating content scraping"""

import logging
from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models import Source, Post, User
from scrapers import ScraperFactory
from utils.safe_logging import sanitize_error_message, get_safe_error_code

logger = logging.getLogger(__name__)


class ScrapingService:
    """
    Service for coordinating content scraping operations

    Handles:
    - Source verification
    - Content scraping
    - Post normalization and storage
    - Source status updates
    - Error handling
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize scraping service

        Args:
            db: Database session
        """
        self.db = db

    async def verify_source(
        self,
        url: str,
        platform: Optional[str] = None,
        user_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Verify a source URL before saving

        Args:
            url: Source URL to verify
            platform: Platform name (optional, will auto-detect)
            user_id: User UUID (optional, for duplicate checking)

        Returns:
            Verification result with status and metadata
        """
        try:
            # Check for duplicates only if user_id is provided
            if user_id:
                result = await self.db.execute(
                    select(Source)
                    .where(Source.user_id == user_id)
                    .where(Source.url == url)
                )
                existing_source = result.scalar_one_or_none()

                if existing_source:
                    # Generate recommendations for existing source
                    recommendations = []
                    if existing_source.is_private:
                        recommendations.append("Откройте профиль временно или загрузите файл с постами через /ingest/manual_posts")
                    if existing_source.post_count < 50:
                        recommendations.append("Добавьте ещё источники/файл/референсы для лучшего качества анализа стиля")

                    return {
                        'handle': existing_source.handle or '',
                        'accessible': True,
                        'private': existing_source.is_private,
                        'post_count': existing_source.post_count,
                        'normalized_url': url,
                        'message': "You have already added this source",
                        'recommendations': recommendations
                    }

            # Create scraper and verify
            scraper = ScraperFactory.create_scraper(url, platform=platform)
            verification_result = await scraper.verify()

            # Transform scraper response to T6 SourceVerifyResponse format
            status = verification_result.get('status', 'ERROR')
            is_private = verification_result.get('is_private', False)
            post_count = verification_result.get('posts_count', 0)

            # Generate recommendations based on private status and post count
            recommendations = []
            if is_private:
                recommendations.append("Откройте профиль временно или загрузите файл с постами через /ingest/manual_posts")
            if post_count < 50:
                recommendations.append("Добавьте ещё источники/файл/референсы для лучшего качества анализа стиля")

            response = {
                'handle': verification_result.get('handle', ''),
                'accessible': status == 'OK',
                'private': is_private,
                'post_count': post_count,
                'normalized_url': url,  # scrapers don't normalize URLs in mock
                'message': verification_result.get('message', f'Status: {status}'),
                'recommendations': recommendations
            }

            logger.info(f"Verification result for {url}: {status}")
            return response

        except ValueError as e:
            # Invalid URL or unsupported platform
            # Log only error type (security: no URLs in logs)
            logger.error(f"Verification error: {get_safe_error_code(e)}")
            return {
                'handle': '',
                'accessible': False,
                'private': False,
                'post_count': 0,
                'normalized_url': url,
                'message': str(e),
                'recommendations': []
            }
        except Exception as e:
            # Log only error type (security: no sensitive data in logs)
            logger.error(f"Unexpected error during verification: {get_safe_error_code(e)}")
            return {
                'handle': '',
                'accessible': False,
                'private': False,
                'post_count': 0,
                'normalized_url': url,
                'message': "Verification failed",
                'recommendations': []
            }

    async def scrape_source(
        self,
        source_id: UUID,
        user_id: UUID,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Scrape posts from a source and save to database

        Args:
            source_id: Source UUID to scrape
            user_id: User UUID (for verification)
            limit: Maximum number of posts to scrape

        Returns:
            Scraping result with status and post count
        """
        try:
            # Load source from database
            result = await self.db.execute(
                select(Source)
                .where(Source.id == source_id)
                .where(Source.user_id == user_id)
            )
            source = result.scalar_one_or_none()

            if not source:
                return {
                    "status": "ERROR",
                    "posts_collected": 0,
                    "message": "Source not found"
                }

            # Update source status to 'scraping'
            source.status = 'scraping'
            await self.db.commit()

            # Create scraper and scrape content
            scraper = ScraperFactory.create_scraper(
                source.url,
                platform=source.platform
            )

            logger.info(f"Starting scrape for source {source_id} ({source.platform})")
            scraped_posts = await scraper.scrape(limit=limit)

            # Save posts to database
            saved_count = await self._save_posts(
                scraped_posts,
                source=source,
                user_id=user_id
            )

            # Update source metadata
            source.status = 'done'
            source.post_count = saved_count
            source.updated_at = datetime.utcnow()

            # Extract handle if not set
            if not source.handle and scraped_posts:
                source.handle = scraped_posts[0].get('author_handle')

            await self.db.commit()

            logger.info(f"Scraping completed: {saved_count} posts saved")
            return {
                "status": "SUCCESS",
                "posts_collected": saved_count,
                "message": f"Successfully collected {saved_count} posts"
            }

        except Exception as e:
            # Log only error type (security: no sensitive data in logs)
            logger.error(f"Error during scraping: {get_safe_error_code(e)}")

            # Update source status to 'error'
            if source:
                source.status = 'error'
                source.meta = source.meta or {}
                source.meta['error_type'] = get_safe_error_code(e)  # Store only error type
                source.meta['error_time'] = datetime.utcnow().isoformat()
                await self.db.commit()

            return {
                "status": "ERROR",
                "posts_collected": 0,
                "message": "Scraping failed"
            }

    async def _save_posts(
        self,
        scraped_posts: list,
        source: Source,
        user_id: UUID
    ) -> int:
        """
        Save scraped posts to database

        Args:
            scraped_posts: List of normalized post dictionaries
            source: Source model instance
            user_id: User UUID

        Returns:
            Number of posts saved
        """
        saved_count = 0

        for post_data in scraped_posts:
            try:
                # Check if post already exists (idempotency)
                result = await self.db.execute(
                    select(Post)
                    .where(Post.source_id == source.id)
                    .where(Post.platform_post_id == post_data['platform_post_id'])
                )
                existing_post = result.scalar_one_or_none()

                if existing_post:
                    # Post already exists, skip
                    continue

                # Create new post
                post = Post(
                    user_id=user_id,
                    source_id=source.id,
                    platform=source.platform,
                    platform_post_id=post_data['platform_post_id'],
                    author_handle=post_data.get('author_handle'),
                    posted_at=post_data.get('posted_at'),
                    text=post_data.get('text'),
                    media=post_data.get('media', []),
                    reactions=post_data.get('reactions', {}),
                    link=post_data.get('link'),
                    lang=None,  # TODO: Add language detection
                    qdrant_point_id=None,  # TODO: Add vector embedding
                    raw=post_data.get('raw', {})
                )

                self.db.add(post)

                # Commit each post individually to avoid transaction rollback issues
                try:
                    await self.db.commit()
                    saved_count += 1
                except Exception as commit_error:
                    # Rollback failed transaction and continue with next post
                    await self.db.rollback()
                    logger.error(f"Error committing post {post_data.get('platform_post_id')}: {get_safe_error_code(commit_error)}")
                    continue

            except Exception as e:
                # Log only error type (security: no post content in logs)
                logger.error(f"Error saving post {post_data.get('platform_post_id')}: {get_safe_error_code(e)}")
                continue

        return saved_count
