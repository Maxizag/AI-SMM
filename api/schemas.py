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


# Source verification schemas
class SourceVerifyRequest(BaseModel):
    url: str
    user_id: UUID


class SourceVerifyResponse(BaseModel):
    status: str  # OK, CLOSED, LOW_CONTENT, DUPLICATE, INVALID_URL
    message: Optional[str] = None
    posts_count: Optional[int] = None  # For LOW_CONTENT case
