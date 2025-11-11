from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List, Optional
from datetime import datetime
import re

from database import get_db
from models import User, Source, Brief, StyleSeed, ScrapingJob, Post
from schemas import (
    SourceCreate, SourceResponse,
    SourceVerifyRequest, SourceVerifyResponse,
    SourceCreateV2, SourceCreateV2Response,
    ScrapeRequest, ScrapeResponse,
    JobStatusResponse,
    ManualPostsRequest, ManualPostsResponse,
    HintsRequest, HintsResponse,
    BriefCreate, BriefResponse,
    StyleSeedCreate, StyleSeedResponse,
    UserResponse
)
from services.scraping_service import ScrapingService
from auth_utils import get_current_user_id
from utils.url_normalizer import normalize_url

router = APIRouter(tags=["Onboarding"])


# Protected endpoint to get current user info (demonstrates Bearer auth in Swagger)
@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Get current authenticated user information

    This endpoint requires Bearer token authentication.
    Use POST /auth/tg to get a token first.
    """
    result = await db.execute(select(User).where(User.id == current_user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    return user


# Source verification endpoint (T6 spec)
@router.post("/sources/verify", response_model=SourceVerifyResponse)
async def verify_source(
    verify_data: SourceVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify a source URL before saving (T6 spec)

    Uses platform-specific scrapers to check:
    - URL validity
    - Account accessibility (public/private)
    - Content availability (≥50 posts recommended)

    Request:
    - platform: telegram|vk|instagram
    - url: Source URL to verify

    Response:
    - handle: Extracted handle/username
    - accessible: Boolean indicating if source is accessible
    - private: Boolean indicating if source is private
    - post_count: Estimated number of posts
    - normalized_url: Cleaned/normalized URL (for deduplication)
    - message: Human-readable status message

    Returns one of:
    - OK: URL is valid and has enough content
    - CLOSED: Account is closed/private
    - LOW_CONTENT: Less than 50 posts
    - INVALID_URL: URL format is invalid or unsupported platform
    """
    url = verify_data.url.strip()
    platform = verify_data.platform

    # Normalize URL first
    normalized_url = normalize_url(url)

    # Use scraping service for verification
    scraping_service = ScrapingService(db)
    result = await scraping_service.verify_source(normalized_url, platform=platform)

    return SourceVerifyResponse(**result)


# Create source V2 endpoint (T6 spec)
@router.post("/sources/v2", response_model=SourceCreateV2Response, status_code=status.HTTP_201_CREATED)
async def create_source_v2(
    source_data: SourceCreateV2,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new verified source (T6 spec)

    This endpoint creates a source with already-verified data from POST /sources/verify.

    Request:
    - platform: telegram|vk|instagram
    - url: Source URL
    - handle: Extracted handle/username
    - private: Whether source is private
    - post_count_hint: Estimated post count (optional)

    Response:
    - source_id: UUID of created source
    - status: "verified"

    Error (409):
    - error: "duplicate_source"
    - message: "Эта ссылка уже добавлена"

    Note: Requires Bearer token authentication.
    """
    # Normalize URL for deduplication
    normalized_url = normalize_url(source_data.url)

    # Check for duplicates by normalized URL
    result = await db.execute(
        select(Source)
        .where(Source.user_id == current_user_id)
        .where(Source.url == normalized_url)
    )
    existing_source = result.scalar_one_or_none()

    if existing_source:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "duplicate_source",
                "message": "Эта ссылка уже добавлена",
                "existing_source_id": str(existing_source.id)
            }
        )

    # Create source with 'verified' status (using normalized URL)
    source = Source(
        user_id=current_user_id,
        platform=source_data.platform,
        url=normalized_url,  # Store normalized URL for deduplication
        handle=source_data.handle,
        is_private=source_data.private,
        post_count=source_data.post_count_hint or 0,
        status='verified'
    )

    db.add(source)
    await db.commit()
    await db.refresh(source)

    return SourceCreateV2Response(
        source_id=source.id,
        status="verified"
    )


# Ingest/scrape endpoint (T6 spec - async with Celery)
@router.post("/ingest/scrape", response_model=ScrapeResponse)
async def scrape_source(
    scrape_data: ScrapeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Start asynchronous scraping job (T6 spec)

    Creates a scraping job and queues it for background processing.
    Use GET /ingest/status?job_id={job_id} to check progress.

    Request:
    - user_id: User UUID
    - source_ids: Optional list of source IDs (if empty, scrapes all verified sources)
    - target_posts: Target number of posts to collect (default: 100)
    - min_posts: Minimum acceptable posts (default: 50)

    Response:
    - job_id: UUID of the scraping job
    - status: "queued"
    - message: Human-readable message

    The job will process asynchronously and can be monitored via GET /ingest/status.
    """
    user_id = scrape_data.user_id
    source_ids = scrape_data.source_ids
    target_posts = scrape_data.target_posts
    min_posts = scrape_data.min_posts

    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )

    # Create ScrapingJob in database
    job = ScrapingJob(
        user_id=user_id,
        status='queued',
        target_posts=target_posts,
        min_posts=min_posts,
        total_collected=0,
        progress={},
        errors=[]
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Launch Celery task using lazy import to avoid loading celery at FastAPI startup
    from celery_app import celery_app
    task = celery_app.send_task(
        'scraping.run_scraping_job',
        args=[str(job.id), str(user_id), [str(sid) for sid in source_ids] if source_ids else None]
    )

    # Store Celery task ID for cancellation support
    job.celery_task_id = task.id
    await db.commit()

    return ScrapeResponse(
        job_id=job.id,
        status="queued",
        message=f"Scraping job created and queued. Use GET /ingest/status?job_id={job.id} to check progress."
    )


# Get job status endpoint (T6 spec)
@router.get("/ingest/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get scraping job status and progress (T6 spec)

    Query parameters:
    - job_id: UUID of the scraping job

    Response:
    - job_id: UUID of the job
    - status: queued|running|done|partial|error
    - progress: {
        total_collected: int,
        by_source: [
          {source_id, platform, collected, status}
        ]
      }
    - errors: List of error messages (if any)

    Status meanings:
    - queued: Job is waiting to be processed
    - running: Job is currently being processed
    - done: Job completed successfully (≥target_posts collected)
    - partial: Job completed but with fewer posts than target (≥min_posts)
    - error: Job failed
    """
    result = await db.execute(
        select(ScrapingJob).where(ScrapingJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id {job_id} not found"
        )

    # Build progress response with summary
    progress = {
        "total_collected": job.total_collected,
        "by_source": job.progress.get("by_source", []),
        "summary": job.progress.get("summary", {})
    }

    # Ensure errors are properly structured
    # Convert legacy string errors to structured format if needed
    structured_errors = []
    for error in (job.errors or []):
        if isinstance(error, dict):
            structured_errors.append(error)
        elif isinstance(error, str):
            # Legacy string error - wrap it
            structured_errors.append({
                "code": "INTERNAL_ERROR",
                "message": error
            })
        else:
            # Unknown format, convert to string
            structured_errors.append({
                "code": "INTERNAL_ERROR",
                "message": str(error)
            })

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=progress,
        errors=structured_errors
    )


# Manual posts endpoint (T6 spec)
@router.post("/ingest/manual_posts", response_model=ManualPostsResponse)
async def add_manual_posts(
    data: ManualPostsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Add manual posts (T6 spec)

    Allows users to manually add their own posts for style analysis.
    These posts are stored with platform="manual".

    Request:
    - user_id: User UUID
    - posts: List of manual posts
      - platform: "manual" (default)
      - text: Post text content
      - posted_at: Optional timestamp
      - media: Optional list of media objects

    Response:
    - stored: Number of posts successfully stored
    """
    user_id = data.user_id

    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )

    # Create a "manual" source if it doesn't exist
    result = await db.execute(
        select(Source)
        .where(Source.user_id == user_id)
        .where(Source.platform == "manual")
    )
    manual_source = result.scalar_one_or_none()

    if not manual_source:
        manual_source = Source(
            user_id=user_id,
            platform="manual",
            url="manual://user-posts",
            handle="manual",
            is_private=True,
            post_count=0,
            status='verified'
        )
        db.add(manual_source)
        await db.commit()
        await db.refresh(manual_source)

    # Store each manual post
    stored_count = 0
    for manual_post in data.posts:
        try:
            # Create unique platform_post_id based on timestamp and content hash
            post_id = f"manual_{datetime.utcnow().timestamp()}_{hash(manual_post.text) % 10000}"

            # Check if similar post already exists
            result = await db.execute(
                select(Post)
                .where(Post.source_id == manual_source.id)
                .where(Post.text == manual_post.text)
            )
            existing_post = result.scalar_one_or_none()

            if existing_post:
                # Skip duplicate
                continue

            post = Post(
                user_id=user_id,
                source_id=manual_source.id,
                platform="manual",
                platform_post_id=post_id,
                author_handle="manual",
                posted_at=manual_post.posted_at or datetime.utcnow(),
                text=manual_post.text,
                media=manual_post.media or [],
                reactions={},
                link=None,
                lang=None,
                qdrant_point_id=None,
                raw={}
            )

            db.add(post)
            stored_count += 1

        except Exception as e:
            # Log error but continue with other posts
            continue

    # Update source post count
    manual_source.post_count += stored_count

    await db.commit()

    return ManualPostsResponse(stored=stored_count)


# Hints/references endpoint (T6 spec - optional)
@router.post("/ingest/hints", response_model=HintsResponse)
async def add_hints(
    data: HintsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Add hint/reference sources (T6 spec - optional)

    Allows users to provide reference channels/accounts for style inspiration.
    These are marked as "reference" sources with lower weight in style analysis.

    Request:
    - user_id: User UUID
    - references: List of reference sources
      - platform: telegram|vk|instagram
      - url: Source URL
    - weight: Weight for style analysis (max 0.3, default 0.2)

    Response:
    - status: "ok"
    - references_added: Number of references added
    - message: Human-readable message

    Note: These sources are scraped but marked with meta.is_reference=true
    and contribute less to the user's style profile.
    """
    user_id = data.user_id
    references = data.references
    weight = min(data.weight, 0.3)  # Enforce max weight

    # Verify user exists
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )

    added_count = 0

    for ref_source in references:
        try:
            # Check if already exists
            result = await db.execute(
                select(Source)
                .where(Source.user_id == user_id)
                .where(Source.url == ref_source.url)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing source to be a reference
                existing.meta = existing.meta or {}
                existing.meta['is_reference'] = True
                existing.meta['weight'] = weight
                added_count += 1
                continue

            # Create new reference source
            source = Source(
                user_id=user_id,
                platform=ref_source.platform,
                url=ref_source.url,
                status='new',
                meta={
                    'is_reference': True,
                    'weight': weight
                }
            )

            db.add(source)
            added_count += 1

        except Exception as e:
            # Log and continue
            continue

    await db.commit()

    return HintsResponse(
        status="ok",
        references_added=added_count,
        message=f"Added {added_count} reference sources with weight {weight}"
    )


# Sources endpoints
@router.post("/sources", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    source_data: SourceCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new source for onboarding

    Saves content source information (platform and URL) for a user.
    Used in onboarding flow when user provides their social media profiles.
    """
    # Verify user exists
    result = await db.execute(select(User).where(User.id == source_data.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {source_data.user_id} not found"
        )

    source = Source(**source_data.model_dump())
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return source


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def get_source(source_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get source by ID"""
    result = await db.execute(select(Source).where(Source.id == source_id))
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with id {source_id} not found"
        )

    return source


@router.get("/users/{user_id}/sources", response_model=List[SourceResponse])
async def list_user_sources(
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all sources for a user"""
    result = await db.execute(
        select(Source)
        .where(Source.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    sources = result.scalars().all()
    return sources


# Briefs endpoints
@router.post("/briefs", response_model=BriefResponse, status_code=status.HTTP_201_CREATED)
async def create_brief(
    brief_data: BriefCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a content brief

    Saves content brief information from experienced users.
    Used in onboarding Branch 1: users who have content experience.

    Fields:
    - goal: Content goal/objective
    - audience: Target audience description
    - tone: Desired tone of voice
    - topic: Main topic/niche
    - frequency: Posting frequency
    """
    # Verify user exists
    result = await db.execute(select(User).where(User.id == brief_data.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {brief_data.user_id} not found"
        )

    brief = Brief(**brief_data.model_dump())
    db.add(brief)
    await db.commit()
    await db.refresh(brief)
    return brief


@router.get("/briefs/{brief_id}", response_model=BriefResponse)
async def get_brief(brief_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get brief by ID"""
    result = await db.execute(select(Brief).where(Brief.id == brief_id))
    brief = result.scalar_one_or_none()

    if not brief:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Brief with id {brief_id} not found"
        )

    return brief


@router.get("/users/{user_id}/briefs", response_model=List[BriefResponse])
async def list_user_briefs(
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all briefs for a user"""
    result = await db.execute(
        select(Brief)
        .where(Brief.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    briefs = result.scalars().all()
    return briefs


# StyleSeed endpoints
@router.post("/style_seed", response_model=StyleSeedResponse, status_code=status.HTTP_201_CREATED)
async def create_style_seed(
    seed_data: StyleSeedCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a style seed

    Saves initial style preferences from new users.
    Used in onboarding Branch 2: users without content experience.

    Fields:
    - tone: Preferred tone (casual, professional, etc.)
    - goal: Content goal
    - topic: Main topic/niche
    """
    # Verify user exists
    result = await db.execute(select(User).where(User.id == seed_data.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {seed_data.user_id} not found"
        )

    seed = StyleSeed(**seed_data.model_dump())
    db.add(seed)
    await db.commit()
    await db.refresh(seed)
    return seed


@router.get("/style_seed/{seed_id}", response_model=StyleSeedResponse)
async def get_style_seed(seed_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get style seed by ID"""
    result = await db.execute(select(StyleSeed).where(StyleSeed.id == seed_id))
    seed = result.scalar_one_or_none()

    if not seed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"StyleSeed with id {seed_id} not found"
        )

    return seed


@router.get("/users/{user_id}/style_seed", response_model=List[StyleSeedResponse])
async def list_user_style_seeds(
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all style seeds for a user"""
    result = await db.execute(
        select(StyleSeed)
        .where(StyleSeed.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    seeds = result.scalars().all()
    return seeds
