from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database import get_db
from models import User
from schemas import TelegramAuthRequest, AuthTokenResponse, UserResponse
from auth_utils import create_access_token

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/tg", response_model=AuthTokenResponse)
async def authenticate_telegram_user(
    auth_data: TelegramAuthRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate or register user via Telegram

    - If user exists, return existing user with new token
    - If user doesn't exist, create new user and return with token
    """
    # Check if user already exists
    result = await db.execute(
        select(User).where(User.tg_user_id == auth_data.tg_user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        # Create new user
        user = User(
            tg_user_id=auth_data.tg_user_id,
            name=auth_data.name
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # Create access token
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "tg_user_id": user.tg_user_id,
            "name": user.name
        }
    )

    return AuthTokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            tg_user_id=user.tg_user_id,
            name=user.name,
            created_at=user.created_at
        )
    )
