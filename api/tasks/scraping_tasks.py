"""Celery tasks for async scraping operations"""

import logging
from datetime import datetime
from uuid import UUID
from typing import Optional

from celery import Task
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from celery_app import celery_app
from database import AsyncSessionLocal
from models import ScrapingJob, Source, Post, User
from scrapers import ScraperFactory
from scrapers.error_codes import (
    ScrapingErrorCode,
    create_error_object,
    get_error_message
)

logger = logging.getLogger(__name__)


async def _execute_scraping_job(job_id: str, user_id: str, source_ids: Optional[list] = None):
    """
    Internal async function to execute scraping job

    Args:
        job_id: UUID of the ScrapingJob
        user_id: UUID of the user
        source_ids: Optional list of source IDs to scrape. If None, scrape all verified sources
    """
    async with AsyncSessionLocal() as db:
        try:
            # Load the job from database
            result = await db.execute(
                select(ScrapingJob).where(ScrapingJob.id == UUID(job_id))
            )
            job = result.scalar_one_or_none()

            if not job:
                logger.error(f"ScrapingJob {job_id} not found")
                return

            # Update job status to 'running'
            job.status = 'running'
            job.started_at = datetime.utcnow()
            await db.commit()
            logger.info(f"Started scraping job {job_id}")

            # Get sources to scrape
            query = select(Source).where(Source.user_id == UUID(user_id))

            if source_ids:
                # Scrape specific sources
                source_uuids = [UUID(sid) for sid in source_ids]
                query = query.where(Source.id.in_(source_uuids))
            else:
                # Scrape all verified sources
                query = query.where(Source.status == 'verified')

            result = await db.execute(query)
            sources = result.scalars().all()

            if not sources:
                logger.warning(f"No sources found for job {job_id}")
                job.status = 'error'
                job.completed_at = datetime.utcnow()
                job.errors = ["No sources found to scrape"]
                await db.commit()
                return

            logger.info(f"Found {len(sources)} sources to scrape")

            # Initialize progress tracking
            job.progress = {
                "by_source": []
            }
            job.total_collected = 0
            await db.commit()

            # Track if we hit target
            target_posts = job.target_posts
            min_posts = job.min_posts
            total_collected = 0
            all_errors = []  # List of structured error objects
            private_sources_count = 0
            failed_sources_count = 0

            # Scrape each source
            for source in sources:
                source_progress = {
                    "source_id": str(source.id),
                    "platform": source.platform,
                    "collected": 0,
                    "status": "running"
                }

                try:
                    logger.info(f"Scraping source {source.id} ({source.platform})")

                    # Update source status
                    source.status = 'scraping'
                    await db.commit()

                    # Create scraper
                    scraper = ScraperFactory.create_scraper(
                        source.url,
                        platform=source.platform
                    )

                    # First, verify source accessibility
                    # This helps catch private accounts early
                    try:
                        verification = await scraper.verify()
                        verify_status = verification.get('status', 'OK')

                        # Handle different verification statuses
                        if verify_status == 'CLOSED' or verification.get('is_private', False):
                            # Account is private
                            private_sources_count += 1
                            error = create_error_object(
                                ScrapingErrorCode.PLATFORM_PRIVATE,
                                source_id=str(source.id),
                                platform=source.platform
                            )
                            all_errors.append(error)

                            source.status = 'error'
                            source.meta = source.meta or {}
                            source.meta['error_code'] = ScrapingErrorCode.PLATFORM_PRIVATE.value
                            source.meta['error'] = error['message']
                            source.meta['is_private'] = True
                            source.meta['error_time'] = datetime.utcnow().isoformat()

                            source_progress['status'] = 'error'
                            source_progress['error_code'] = ScrapingErrorCode.PLATFORM_PRIVATE.value
                            await db.commit()
                            continue

                        elif verify_status == 'INVALID_URL':
                            error = create_error_object(
                                ScrapingErrorCode.PLATFORM_INVALID_URL,
                                source_id=str(source.id),
                                platform=source.platform
                            )
                            all_errors.append(error)

                            source.status = 'error'
                            source.meta = source.meta or {}
                            source.meta['error_code'] = ScrapingErrorCode.PLATFORM_INVALID_URL.value
                            source.meta['error'] = error['message']
                            source.meta['error_time'] = datetime.utcnow().isoformat()

                            source_progress['status'] = 'error'
                            source_progress['error_code'] = ScrapingErrorCode.PLATFORM_INVALID_URL.value
                            failed_sources_count += 1
                            await db.commit()
                            continue

                        elif verify_status == 'LOW_CONTENT':
                            # Source has insufficient content
                            error = create_error_object(
                                ScrapingErrorCode.PLATFORM_INSUFFICIENT_CONTENT,
                                source_id=str(source.id),
                                platform=source.platform,
                                posts_count=verification.get('posts_count', 0)
                            )
                            all_errors.append(error)

                            source.meta = source.meta or {}
                            source.meta['warning'] = 'insufficient_content'
                            source.meta['estimated_posts'] = verification.get('posts_count', 0)
                            # Don't fail the source, try to scrape what we can

                    except Exception as verify_error:
                        logger.warning(f"Verification failed for source {source.id}, continuing anyway: {verify_error}")
                        # Continue with scraping even if verification fails

                    # Calculate how many posts to scrape from this source
                    # Distribute evenly across sources
                    posts_per_source = target_posts // len(sources)
                    remaining = target_posts - total_collected
                    limit = min(posts_per_source, remaining, 100)  # Max 100 per source

                    # Scrape posts
                    scraped_posts = await scraper.scrape(limit=limit)

                    if not scraped_posts:
                        logger.warning(f"No posts scraped from source {source.id}")
                        failed_sources_count += 1

                    # Save posts to database
                    saved_count = await _save_posts(db, scraped_posts, source, UUID(user_id))

                    # Update source metadata
                    source.status = 'done'
                    source.post_count = saved_count
                    source.updated_at = datetime.utcnow()

                    # Extract handle if not set
                    if not source.handle and scraped_posts:
                        source.handle = scraped_posts[0].get('author_handle')

                    # Update progress
                    source_progress['collected'] = saved_count
                    source_progress['status'] = 'done'
                    total_collected += saved_count

                    logger.info(f"Successfully scraped {saved_count} posts from source {source.id}")

                except Exception as e:
                    error_msg = f"Error scraping source {source.id}: {str(e)}"
                    logger.error(error_msg)

                    failed_sources_count += 1

                    # Create structured error
                    error = create_error_object(
                        ScrapingErrorCode.INTERNAL_ERROR,
                        source_id=str(source.id),
                        platform=source.platform,
                        details=str(e)
                    )
                    all_errors.append(error)

                    # Update source status
                    source.status = 'error'
                    source.meta = source.meta or {}
                    source.meta['error_code'] = ScrapingErrorCode.INTERNAL_ERROR.value
                    source.meta['error'] = str(e)
                    source.meta['error_time'] = datetime.utcnow().isoformat()

                    # Track error
                    source_progress['status'] = 'error'
                    source_progress['error_code'] = ScrapingErrorCode.INTERNAL_ERROR.value

                finally:
                    # Add source progress to job
                    job.progress['by_source'].append(source_progress)
                    job.total_collected = total_collected
                    await db.commit()

            # Determine final status
            job.completed_at = datetime.utcnow()

            # Check if all sources failed
            if failed_sources_count == len(sources) and total_collected == 0:
                job.status = 'error'
                error = create_error_object(ScrapingErrorCode.JOB_ALL_SOURCES_FAILED)
                all_errors.append(error)
                logger.error(f"Job {job_id} failed: all sources failed")

            # Check if we collected enough posts
            elif total_collected >= target_posts:
                job.status = 'done'
                logger.info(f"Job {job_id} completed successfully: {total_collected}/{target_posts} posts")

                # Add warning if some sources had low content
                if total_collected < 50:
                    error = create_error_object(
                        ScrapingErrorCode.JOB_INSUFFICIENT_POSTS,
                        total_collected=total_collected,
                        min_required=50
                    )
                    all_errors.append(error)

            elif total_collected >= min_posts:
                job.status = 'partial'
                logger.warning(f"Job {job_id} partially completed: {total_collected}/{target_posts} posts")

                # Add recommendation if below 50 posts
                if total_collected < 50:
                    error = create_error_object(
                        ScrapingErrorCode.JOB_INSUFFICIENT_POSTS,
                        total_collected=total_collected,
                        min_required=50
                    )
                    all_errors.append(error)

            else:
                # Collected less than min_posts
                job.status = 'error'
                error = create_error_object(
                    ScrapingErrorCode.JOB_INSUFFICIENT_POSTS,
                    total_collected=total_collected,
                    min_required=min_posts,
                    target=target_posts
                )
                all_errors.append(error)
                logger.error(f"Job {job_id} failed: only {total_collected}/{min_posts} posts collected")

            # Store structured errors
            if all_errors:
                job.errors = all_errors

            # Add summary to job metadata
            job.progress['summary'] = {
                'total_sources': len(sources),
                'private_sources': private_sources_count,
                'failed_sources': failed_sources_count,
                'successful_sources': len(sources) - failed_sources_count - private_sources_count,
                'total_collected': total_collected,
                'quality_sufficient': total_collected >= 50
            }

            await db.commit()
            logger.info(f"Scraping job {job_id} finished with status: {job.status}")

        except Exception as e:
            logger.error(f"Fatal error in scraping job {job_id}: {e}", exc_info=True)

            # Try to update job status to error
            try:
                async with AsyncSessionLocal() as error_db:
                    result = await error_db.execute(
                        select(ScrapingJob).where(ScrapingJob.id == UUID(job_id))
                    )
                    job = result.scalar_one_or_none()
                    if job:
                        job.status = 'error'
                        job.completed_at = datetime.utcnow()
                        job.errors = [f"Fatal error: {str(e)}"]
                        await error_db.commit()
            except Exception as inner_e:
                logger.error(f"Failed to update job status after error: {inner_e}")


async def _save_posts(
    db: AsyncSession,
    scraped_posts: list,
    source: Source,
    user_id: UUID
) -> int:
    """
    Save scraped posts to database

    Args:
        db: Database session
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
            result = await db.execute(
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

            db.add(post)
            saved_count += 1

        except Exception as e:
            logger.error(f"Error saving post {post_data.get('platform_post_id')}: {e}")
            continue

    # Commit all posts at once
    await db.commit()

    return saved_count


@celery_app.task(
    bind=True,
    name='scraping.run_scraping_job',
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
    default_retry_delay=10
)
def run_scraping_job(self, job_id: str, user_id: str, source_ids: Optional[list] = None):
    """
    Celery task for asynchronous content scraping with automatic retry

    This task:
    1. Updates job status to 'running'
    2. Gets sources for scraping
    3. For each source:
       - Runs appropriate scraper
       - Saves posts to database
       - Updates progress in ScrapingJob
    4. Sets final status to 'done', 'partial', or 'error'

    Retry behavior:
    - Automatically retries on any exception
    - Exponential backoff: 10s, 20s, 40s (max 60s)
    - Random jitter to prevent thundering herd
    - Max 3 retries before giving up

    Args:
        job_id: UUID of the ScrapingJob
        user_id: UUID of the user
        source_ids: Optional list of source IDs to scrape
    """
    import asyncio

    # Log retry information
    if self.request.retries > 0:
        logger.info(
            f"Retrying scraping job {job_id} - attempt {self.request.retries + 1}/{self.max_retries + 1}"
        )

    # Store Celery task ID in job for cancellation support
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Run the async scraping function
    loop.run_until_complete(_execute_scraping_job(job_id, user_id, source_ids))

    return {
        'job_id': job_id,
        'status': 'completed'
    }
