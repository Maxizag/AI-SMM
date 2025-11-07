from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID
from typing import List
import re

from database import get_db
from models import User, Source, Brief, StyleSeed
from schemas import (
    SourceCreate, SourceResponse,
    SourceVerifyRequest, SourceVerifyResponse,
    BriefCreate, BriefResponse,
    StyleSeedCreate, StyleSeedResponse
)

router = APIRouter(tags=["Onboarding"])


# Source verification endpoint (mock for now, real parsing in T6)
@router.post("/sources/verify", response_model=SourceVerifyResponse)
async def verify_source(
    verify_data: SourceVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify a source URL (MOCK implementation for T5)

    This is a mock endpoint that simulates verification.
    Real parsing logic will be implemented in Task T6.

    Returns one of:
    - OK: URL is valid and has enough content
    - CLOSED: Account is closed/private
    - LOW_CONTENT: Less than 50 posts
    - DUPLICATE: URL already added by this user
    - INVALID_URL: URL format is invalid

    For testing different responses, use URLs containing:
    - "closed" -> returns CLOSED
    - "low" -> returns LOW_CONTENT
    - invalid format -> returns INVALID_URL
    - already exists in DB -> returns DUPLICATE
    """
    url = verify_data.url.strip()
    user_id = verify_data.user_id

    # 1. Validate URL format
    url_pattern = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # or IP
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    if not url_pattern.match(url):
        return SourceVerifyResponse(
            status="INVALID_URL",
            message="URL format is invalid. Please provide a valid URL starting with http:// or https://"
        )

    # 2. Check for duplicates in database
    result = await db.execute(
        select(Source)
        .where(Source.user_id == user_id)
        .where(Source.url == url)
    )
    existing_source = result.scalar_one_or_none()

    if existing_source:
        return SourceVerifyResponse(
            status="DUPLICATE",
            message="You have already added this source"
        )

    # 3. MOCK responses based on URL content (for testing)
    # Real implementation will be in T6

    url_lower = url.lower()

    # Simulate closed account
    if "closed" in url_lower:
        return SourceVerifyResponse(
            status="CLOSED",
            message="This account appears to be private or closed"
        )

    # Simulate low content
    if "low" in url_lower:
        return SourceVerifyResponse(
            status="LOW_CONTENT",
            message="This account has less than 50 posts. Please add an account with more content.",
            posts_count=25
        )

    # Default: Success
    return SourceVerifyResponse(
        status="OK",
        message="Source verified successfully",
        posts_count=150
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
