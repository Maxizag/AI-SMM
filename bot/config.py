import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Telegram Bot
    telegram_bot_token: str

    # API
    api_base_url: str = "http://api:8000"

    # Database (for direct access if needed)
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "aismm"
    postgres_user: str = "aismm"
    postgres_password: str = "devpass"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Environment
    env: str = "dev"

    class Config:
        env_file = "../.env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
