from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


# User schemas
class UserBase(BaseModel):
    tg_user_id: int
    name: str


class UserCreate(UserBase):
    pass


class UserResponse(UserBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# Source schemas
class SourceBase(BaseModel):
    platform: Optional[str] = None
    url: Optional[str] = None


class SourceCreate(SourceBase):
    user_id: UUID


class SourceResponse(SourceBase):
    id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# StyleProfile schemas
class StyleProfileBase(BaseModel):
    json: dict = Field(default_factory=dict)


class StyleProfileCreate(StyleProfileBase):
    user_id: UUID


class StyleProfileResponse(StyleProfileBase):
    id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# Health check
class HealthResponse(BaseModel):
    status: str
    service: str
    database: str


# Auth schemas
class TelegramAuthRequest(BaseModel):
    tg_user_id: int
    name: str
    username: Optional[str] = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Brief schemas
class BriefBase(BaseModel):
    goal: Optional[str] = None
    audience: Optional[str] = None
    tone: Optional[str] = None
    topic: Optional[str] = None
    frequency: Optional[str] = None


class BriefCreate(BriefBase):
    user_id: UUID


class BriefResponse(BriefBase):
    id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# StyleSeed schemas
class StyleSeedBase(BaseModel):
    tone: Optional[str] = None
    goal: Optional[str] = None
    topic: Optional[str] = None


class StyleSeedCreate(StyleSeedBase):
    user_id: UUID


class StyleSeedResponse(StyleSeedBase):
    id: UUID
    user_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# Source verification schemas (T6 spec)
class SourceVerifyRequest(BaseModel):
    platform: str  # telegram|vk|instagram
    url: str


class SourceVerifyResponse(BaseModel):
    handle: str
    accessible: bool
    private: bool
    post_count: int
    normalized_url: str
    message: str
    recommendations: list[str] = []  # Actionable recommendations for the user


# Updated Source Create schema (T6 spec)
class SourceCreateV2(BaseModel):
    platform: str
    url: str
    handle: str
    private: bool = False
    post_count_hint: Optional[int] = None


class SourceCreateV2Response(BaseModel):
    source_id: UUID
    status: str  # verified


# Ingest/scrape schemas (T6 spec - async with jobs)
class ScrapeRequest(BaseModel):
    user_id: UUID
    source_ids: Optional[list[UUID]] = None  # if empty - all verified sources
    target_posts: int = 100
    min_posts: int = 50


class ScrapeResponse(BaseModel):
    job_id: UUID
    status: str  # queued
    message: str


# Job status schemas
class SourceProgress(BaseModel):
    source_id: UUID
    platform: str
    collected: int
    status: str  # queued|running|done|error


class ScrapingError(BaseModel):
    """Structured scraping error"""
    code: str
    message: str
    source_id: Optional[str] = None
    platform: Optional[str] = None
    context: Optional[dict] = None


class JobStatusResponse(BaseModel):
    job_id: UUID
    status: str  # queued|running|done|error|partial
    progress: dict  # {total_collected: int, by_source: [SourceProgress], summary: {...}}
    errors: list[ScrapingError | dict] = []  # Support both structured and legacy errors


# Manual posts schemas
class ManualPost(BaseModel):
    platform: str = "manual"
    text: str
    posted_at: Optional[datetime] = None
    media: list[dict] = []


class ManualPostsRequest(BaseModel):
    user_id: UUID
    posts: list[ManualPost]


class ManualPostsResponse(BaseModel):
    stored: int


# Hints/references schemas
class ReferenceSource(BaseModel):
    platform: str
    url: str


class HintsRequest(BaseModel):
    user_id: UUID
    references: list[ReferenceSource]
    weight: float = 0.2  # max 0.3


class HintsResponse(BaseModel):
    status: str
    references_added: int
    message: str
