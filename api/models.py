import uuid
from datetime import datetime
from sqlalchemy import BigInteger, String, Text, DateTime, ForeignKey, JSON, Boolean, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    tg_user_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    sources: Mapped[list["Source"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    style_profiles: Mapped[list["StyleProfile"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    briefs: Mapped[list["Brief"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    style_seeds: Mapped[list["StyleSeed"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    scraping_jobs: Mapped[list["ScrapingJob"]] = relationship(
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User(id={self.id}, tg_user_id={self.tg_user_id}, name='{self.name}')>"


class Source(Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("platform IN ('telegram', 'vk', 'instagram')", name="check_platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    handle: Mapped[str] = mapped_column(Text, nullable=True)  # @channel, vk.com/club123, instagram handle
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    post_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20),
        default='new',
        nullable=False
    )  # new|verified|scraping|done|error
    meta: Mapped[dict] = mapped_column(JSONB, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="sources")
    posts: Mapped[list["Post"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Source(id={self.id}, platform='{self.platform}', status='{self.status}')>"


class StyleProfile(Base):
    __tablename__ = "style_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="style_profiles")

    def __repr__(self):
        return f"<StyleProfile(id={self.id}, user_id={self.user_id})>"


class Brief(Base):
    __tablename__ = "briefs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    goal: Mapped[str] = mapped_column(Text, nullable=True)
    audience: Mapped[str] = mapped_column(Text, nullable=True)
    tone: Mapped[str] = mapped_column(Text, nullable=True)
    topic: Mapped[str] = mapped_column(Text, nullable=True)
    frequency: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="briefs")

    def __repr__(self):
        return f"<Brief(id={self.id}, user_id={self.user_id})>"


class StyleSeed(Base):
    __tablename__ = "style_seed"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    tone: Mapped[str] = mapped_column(Text, nullable=True)
    goal: Mapped[str] = mapped_column(Text, nullable=True)
    topic: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="style_seeds")

    def __repr__(self):
        return f"<StyleSeed(id={self.id}, user_id={self.user_id})>"


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint("platform IN ('telegram', 'vk', 'instagram')", name="check_post_platform"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    platform_post_id: Mapped[str] = mapped_column(Text, nullable=False)  # message_id / post_id / shortcode
    author_handle: Mapped[str] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=True)
    media: Mapped[dict] = mapped_column(JSONB, nullable=True)  # [{type:'image|video', url:'s3://...'}]
    reactions: Mapped[dict] = mapped_column(JSONB, nullable=True)  # {likes,comments,views,shares}
    link: Mapped[str] = mapped_column(Text, nullable=True)  # исходная ссылка
    lang: Mapped[str] = mapped_column(String(10), nullable=True)  # auto-detect
    qdrant_point_id: Mapped[str] = mapped_column(Text, nullable=True)  # ID точки в Qdrant для эмбеддинга
    raw: Mapped[dict] = mapped_column(JSONB, nullable=True)  # сырой ответ API для отладки
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship()
    source: Mapped["Source"] = relationship(back_populates="posts")

    def __repr__(self):
        return f"<Post(id={self.id}, platform='{self.platform}', platform_post_id='{self.platform_post_id}')>"


class ScrapingJob(Base):
    """
    Асинхронная джоба для скрапинга контента

    Статусы:
    - queued: джоба создана, ожидает выполнения
    - running: джоба выполняется
    - done: джоба успешно завершена
    - partial: джоба завершена, но собрано меньше target_posts
    - error: джоба завершена с ошибкой
    """
    __tablename__ = "scraping_jobs"
    __table_args__ = (
        CheckConstraint("status IN ('queued', 'running', 'done', 'partial', 'error')", name="check_job_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default='queued',
        nullable=False
    )
    target_posts: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    min_posts: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    total_collected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # JSONB для хранения прогресса по источникам
    # Формат: {"by_source": [{"source_id": "uuid", "platform": "telegram", "collected": 40, "status": "done"}]}
    progress: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Список ошибок если были
    errors: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # ID задачи Celery для возможности отмены
    celery_task_id: Mapped[str] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship()

    def __repr__(self):
        return f"<ScrapingJob(id={self.id}, status='{self.status}', collected={self.total_collected}/{self.target_posts})>"
