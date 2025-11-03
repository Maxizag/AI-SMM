import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "aismm"
    postgres_user: str = "aismm"
    postgres_password: str = "devpass"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Qdrant
    qdrant_url: str = "http://qdrant:6333"

    # API Keys
    openai_api_key: str = ""
    telegram_bot_token: str = ""
    jwt_secret: str = "changeme"

    # Environment
    env: str = "dev"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    @property
    def database_url_sync(self) -> str:
        return f"postgresql://{self.postgres_user}:{self.postgres_password}@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"

    class Config:
        env_file = "../.env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
