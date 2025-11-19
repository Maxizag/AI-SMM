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
from utils.safe_logging import sanitize_error_message, get_safe_error_code

logger = logging.getLogger(__name__)


# ============================================================================
# Helper functions for job orchestration
# ============================================================================

async def _update_job(
    db: AsyncSession,
    job_id: UUID,
    status: Optional[str] = None,
    total_collected: Optional[int] = None,
    errors: Optional[list] = None,
    summary: Optional[dict] = None
) -> ScrapingJob:
    """
    Update scraping job with new data

    Args:
        db: Database session
        job_id: Job UUID
        status: New status (queued|running|done|partial|error)
        total_collected: Total posts collected
        errors: List of error objects
        summary: Summary statistics

    Returns:
        Updated ScrapingJob instance
    """
    result = await db.execute(
        select(ScrapingJob).where(ScrapingJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise ValueError(f"Job {job_id} not found")

    if status:
        job.status = status
        if status == 'running' and not job.started_at:
            job.started_at = datetime.utcnow()
        elif status in ('done', 'partial', 'error'):
            job.completed_at = datetime.utcnow()

    if total_collected is not None:
        job.total_collected = total_collected

    if errors is not None:
        job.errors = errors

    if summary is not None:
        job.progress['summary'] = summary

    await db.commit()
    await db.refresh(job)
    return job


async def _mark_source(
    db: AsyncSession,
    job_id: UUID,
    source_id: UUID,
    status: str,
    collected: int = 0,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None
) -> None:
    """
    Update source status and add to job progress

    Args:
        db: Database session
        job_id: Job UUID
        source_id: Source UUID
        status: Source status (running|done|error)
        collected: Number of posts collected
        error_code: Error code if failed
        error_message: User-facing error message for bot UX
    """
    # Get job
    result = await db.execute(
        select(ScrapingJob).where(ScrapingJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        return

    # Get source
    result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        return

    # Update source
    source.status = 'scraping' if status == 'running' else status
    if status == 'done':
        source.post_count = collected
        source.updated_at = datetime.utcnow()

    # Find or create progress entry
    progress_entry = None
    for entry in job.progress.get('by_source', []):
        if entry.get('source_id') == str(source_id):
            progress_entry = entry
            break

    if not progress_entry:
        progress_entry = {
            'source_id': str(source_id),
            'platform': source.platform,
            'collected': 0,
            'status': status
        }
        if 'by_source' not in job.progress:
            job.progress['by_source'] = []
        job.progress['by_source'].append(progress_entry)

    # Update progress entry
    progress_entry['status'] = status
    progress_entry['collected'] = collected
    if error_code:
        progress_entry['error_code'] = error_code
    if error_message:
        progress_entry['error_message'] = error_message

    await db.commit()


async def get_sources_for_job(
    db: AsyncSession,
    user_id: UUID,
    source_ids: Optional[list] = None
) -> list[Source]:
    """
    Get sources for scraping job

    Args:
        db: Database session
        user_id: User UUID
        source_ids: Optional list of specific source IDs to scrape

    Returns:
        List of Source objects with status='verified'
    """
    query = select(Source).where(Source.user_id == user_id)

    if source_ids:
        # Scrape specific sources
        source_uuids = [UUID(sid) if isinstance(sid, str) else sid for sid in source_ids]
        query = query.where(Source.id.in_(source_uuids))
    else:
        # Scrape all verified sources
        query = query.where(Source.status == 'verified')

    result = await db.execute(query)
    return list(result.scalars().all())


async def _execute_scraping_job(job_id: str, user_id: str, source_ids: Optional[list] = None):
    """
    Internal async function to execute scraping job (simplified orchestration)

    Args:
        job_id: UUID of the ScrapingJob
        user_id: UUID of the user
        source_ids: Optional list of source IDs to scrape. If None, scrape all verified sources
    """
    job_uuid = UUID(job_id)
    user_uuid = UUID(user_id)

    async with AsyncSessionLocal() as db:
        try:
            # Initialize job
            job = await _update_job(db, job_uuid, status='running')
            target_posts = job.target_posts
            min_posts = job.min_posts
            logger.info(f"Started scraping job {job_id} (target={target_posts}, min={min_posts})")

            # Get sources
            sources = await get_sources_for_job(db, user_uuid, source_ids)

            if not sources:
                logger.warning(f"No sources found for job {job_id}")
                error = create_error_object(ScrapingErrorCode.JOB_NO_SOURCES)
                await _update_job(db, job_uuid, status='error', errors=[error])
                return

            logger.info(f"Found {len(sources)} sources to scrape")

            # Initialize progress
            job.progress = {"by_source": []}
            await db.commit()

            # Tracking variables
            total_collected = 0
            all_errors = []
            private_sources_count = 0
            failed_sources_count = 0
            all_posts_collected = True  # Track if we collected all available posts

            # Process each source
            for source in sources:
                logger.info(f"Scraping source {source.id} ({source.platform})")

                try:
                    # Create scraper
                    scraper = ScraperFactory.create_scraper(source.url, platform=source.platform)

                    # Verify source accessibility (catch private accounts early)
                    try:
                        verification = await scraper.verify()
                        verify_status = verification.get('status', 'OK')

                        # Handle PLATFORM_PRIVATE
                        if verify_status == 'CLOSED' or verification.get('is_private', False):
                            private_sources_count += 1
                            error = create_error_object(
                                ScrapingErrorCode.PLATFORM_PRIVATE,
                                source_id=str(source.id),
                                platform=source.platform
                            )
                            all_errors.append(error)

                            # Update source with error details
                            source.status = 'error'
                            source.meta = source.meta or {}
                            source.meta['error_code'] = ScrapingErrorCode.PLATFORM_PRIVATE.value
                            source.meta['error'] = error['message']
                            source.meta['is_private'] = True
                            source.meta['error_time'] = datetime.utcnow().isoformat()
                            await db.commit()

                            await _mark_source(
                                db, job_uuid, source.id,
                                status='error',
                                error_code=ScrapingErrorCode.PLATFORM_PRIVATE.value,
                                error_message=error['message']
                            )
                            continue

                        # Handle INVALID_URL
                        elif verify_status == 'INVALID_URL':
                            failed_sources_count += 1
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
                            await db.commit()

                            await _mark_source(
                                db, job_uuid, source.id,
                                status='error',
                                error_code=ScrapingErrorCode.PLATFORM_INVALID_URL.value,
                                error_message=error['message']
                            )
                            continue

                        # Handle LOW_CONTENT (warning, continue scraping)
                        elif verify_status == 'LOW_CONTENT':
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
                            await db.commit()
                            # Don't fail, try to scrape what we can

                    except Exception as verify_error:
                        logger.warning(f"Verification failed for {source.id}, continuing: {get_safe_error_code(verify_error)}")
                        # Continue with scraping even if verification fails

                    # Calculate how many posts to scrape
                    posts_per_source = target_posts // len(sources)
                    remaining = target_posts - total_collected
                    limit = min(posts_per_source, remaining, 100)  # Max 100 per source

                    # Scrape posts
                    scraped_posts = await scraper.scrape(limit=limit)

                    if not scraped_posts:
                        logger.warning(f"No posts scraped from {source.id}")
                        failed_sources_count += 1

                    # Check if there might be more posts available
                    # If we got as many posts as we requested, there might be more
                    if len(scraped_posts) >= limit:
                        all_posts_collected = False

                    # Save posts to database
                    saved_count = await _save_posts(db, scraped_posts, source, user_uuid)

                    # Extract handle if not set
                    if not source.handle and scraped_posts:
                        source.handle = scraped_posts[0].get('author_handle')
                        await db.commit()

                    # Mark source as done
                    await _mark_source(db, job_uuid, source.id, status='done', collected=saved_count)
                    total_collected += saved_count

                    logger.info(f"Successfully scraped {saved_count} posts from {source.id}")

                    # Check if we hit target
                    if total_collected >= target_posts:
                        logger.info(f"Reached target {target_posts}, stopping early")
                        break

                except Exception as e:
                    # Log only error type, not full message (security: no PII in logs)
                    logger.error(f"Error scraping {source.id}: {get_safe_error_code(e)}")
                    failed_sources_count += 1

                    # Create structured error (error_code only, no details in logs)
                    error = create_error_object(
                        ScrapingErrorCode.INTERNAL_ERROR,
                        source_id=str(source.id),
                        platform=source.platform,
                        details=get_safe_error_code(e)  # Store only error type, not message
                    )
                    all_errors.append(error)

                    # Update source status with error details
                    source.status = 'error'
                    source.meta = source.meta or {}
                    source.meta['error_code'] = ScrapingErrorCode.INTERNAL_ERROR.value
                    source.meta['error_type'] = get_safe_error_code(e)  # Store type, not full message
                    source.meta['error_time'] = datetime.utcnow().isoformat()
                    await db.commit()

                    await _mark_source(
                        db, job_uuid, source.id,
                        status='error',
                        error_code=ScrapingErrorCode.INTERNAL_ERROR.value,
                        error_message=error['message']
                    )

            # Determine final status based on results
            successful_sources = len(sources) - failed_sources_count - private_sources_count

            # Build summary
            summary = {
                'total_sources': len(sources),
                'private_sources': private_sources_count,
                'failed_sources': failed_sources_count,
                'successful_sources': successful_sources,
                'total_collected': total_collected,
                'quality_sufficient': total_collected >= 50
            }

            # Determine status and add appropriate errors
            if failed_sources_count == len(sources) and total_collected == 0:
                # All sources failed
                final_status = 'error'
                all_errors.append(create_error_object(ScrapingErrorCode.JOB_ALL_SOURCES_FAILED))
                logger.error(f"Job {job_id} failed: all sources failed")

            elif total_collected >= target_posts:
                # Hit target
                final_status = 'done'
                logger.info(f"Job {job_id} done: {total_collected}/{target_posts} posts")

                # Warn if below 50
                if total_collected < 50:
                    all_errors.append(create_error_object(
                        ScrapingErrorCode.JOB_INSUFFICIENT_POSTS,
                        total_collected=total_collected,
                        min_required=50
                    ))

            elif total_collected >= min_posts:
                # Partial success
                final_status = 'partial'
                logger.warning(f"Job {job_id} partial: {total_collected}/{target_posts} posts")

                # Warn if below 50
                if total_collected < 50:
                    all_errors.append(create_error_object(
                        ScrapingErrorCode.JOB_INSUFFICIENT_POSTS,
                        total_collected=total_collected,
                        min_required=50
                    ))

            else:
                # Below minimum - but check if we collected all available posts
                if all_posts_collected:
                    # We collected ALL available posts, even if < min_posts - this is success
                    final_status = 'partial'
                    logger.warning(f"Job {job_id} partial: {total_collected} posts (all available)")

                    # Add warning about low content
                    if total_collected < 50:
                        all_errors.append(create_error_object(
                            ScrapingErrorCode.JOB_INSUFFICIENT_POSTS,
                            total_collected=total_collected,
                            min_required=50
                        ))
                else:
                    # Not all posts collected - there are more available but we failed to get them
                    final_status = 'error'
                    all_errors.append(create_error_object(
                        ScrapingErrorCode.JOB_INSUFFICIENT_POSTS,
                        total_collected=total_collected,
                        min_required=min_posts,
                        target=target_posts
                    ))
                    logger.error(f"Job {job_id} failed: {total_collected}/{min_posts} minimum")

            # Generate recommendations based on total_collected (business rules)
            recommendations = []
            if total_collected < 50:
                recommendations.append("Добавьте ещё источник для достижения минимума в 50 постов")
                recommendations.append("Или загрузите файл с постами через /ingest/manual_posts")
                recommendations.append("Можете добавить референсы через /ingest/hints (вес ≤ 0.3)")
            elif total_collected < 100:
                recommendations.append("Рекомендуем собрать 100 постов для лучшего качества анализа")

            # Add recommendations to summary
            summary['recommendations'] = recommendations

            # Update job with final status
            await _update_job(
                db, job_uuid,
                status=final_status,
                total_collected=total_collected,
                errors=all_errors if all_errors else None,
                summary=summary
            )

            logger.info(f"Job {job_id} finished: {final_status}")

        except Exception as e:
            # Log only error type (security: no PII/stack traces in production logs)
            logger.error(f"Fatal error in job {job_id}: {get_safe_error_code(e)}")

            # Try to update job status to error
            try:
                async with AsyncSessionLocal() as error_db:
                    error = create_error_object(
                        ScrapingErrorCode.INTERNAL_ERROR,
                        details=get_safe_error_code(e)  # Store only error type
                    )
                    await _update_job(error_db, job_uuid, status='error', errors=[error])
            except Exception as inner_e:
                logger.error(f"Failed to update job after fatal error: {get_safe_error_code(inner_e)}")


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
            # Log only error type (security: no post content in logs)
            logger.error(f"Error saving post {post_data.get('platform_post_id')}: {get_safe_error_code(e)}")
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
