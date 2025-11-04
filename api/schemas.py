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
    text: str
    platform: str


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
