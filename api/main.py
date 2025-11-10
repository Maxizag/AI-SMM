from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.models import SecurityScheme, HTTPBearer as HTTPBearerModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from uuid import UUID
from typing import List

from config import get_settings
from database import get_db, engine
from models import User, Source, StyleProfile
from schemas import (
    UserCreate, UserResponse,
    SourceCreate, SourceResponse,
    StyleProfileCreate, StyleProfileResponse,
    HealthResponse
)
from routers import auth, onboarding
from middleware.auth_middleware import AuthMiddleware
from middleware.rate_limit import RateLimitMiddleware
from middleware.idempotency import IdempotencyMiddleware

settings = get_settings()

app = FastAPI(
    title="AI-SMM Agency API",
    description="API for AI-powered SMM content generation",
    version="0.1.0",
    swagger_ui_parameters={
        "persistAuthorization": True  # Save authorization between page refreshes
    }
)

# Include routers
app.include_router(auth.router)
app.include_router(onboarding.router)

# Middleware (order matters: added last runs first)
# 1. CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Idempotency middleware (for POST/PUT/PATCH requests)
app.add_middleware(IdempotencyMiddleware, cache_ttl_hours=24)

# 3. Rate limiting middleware (requires user_id from AuthMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_minute=30)

# 4. Auth middleware (extracts user_id from JWT, runs first)
app.add_middleware(AuthMiddleware)


@app.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    """Health check endpoint"""
    try:
        # Test database connection
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="ok",
        service="api",
        database=db_status
    )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI-SMM Agency API",
        "version": "0.1.0",
        "docs": "/docs"
    }


# User endpoints
@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    """Create a new user"""
    # Check if user with this tg_user_id already exists
    result = await db.execute(
        select(User).where(User.tg_user_id == user_data.tg_user_id)
    )
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"User with tg_user_id {user_data.tg_user_id} already exists"
        )

    user = User(**user_data.model_dump())
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get user by ID"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {user_id} not found"
        )

    return user


@app.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all users"""
    result = await db.execute(
        select(User).offset(skip).limit(limit)
    )
    users = result.scalars().all()
    return users


# StyleProfile endpoints
@app.post("/style-profiles", response_model=StyleProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_style_profile(
    profile_data: StyleProfileCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new style profile"""
    # Verify user exists
    result = await db.execute(select(User).where(User.id == profile_data.user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with id {profile_data.user_id} not found"
        )

    profile = StyleProfile(**profile_data.model_dump())
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@app.get("/style-profiles/{profile_id}", response_model=StyleProfileResponse)
async def get_style_profile(profile_id: UUID, db: AsyncSession = Depends(get_db)):
    """Get style profile by ID"""
    result = await db.execute(
        select(StyleProfile).where(StyleProfile.id == profile_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"StyleProfile with id {profile_id} not found"
        )

    return profile


@app.get("/users/{user_id}/style-profiles", response_model=List[StyleProfileResponse])
async def list_user_style_profiles(
    user_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """List all style profiles for a user"""
    result = await db.execute(
        select(StyleProfile)
        .where(StyleProfile.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    profiles = result.scalars().all()
    return profiles


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
