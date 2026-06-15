"""
database.py — Async database connections
PostgreSQL via SQLAlchemy async + Redis via redis-py async
"""
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import (
    AsyncSession, AsyncEngine,
    async_sessionmaker, create_async_engine
)
from sqlalchemy import text

from app.config import get_settings
from app.models import Base, SEARCH_TRIGGER_SQL

logger = logging.getLogger(__name__)

# ── Module-level singletons ───────────────────────────────────────────────────
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None
_redis: aioredis.Redis | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.db_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_pre_ping=True,       # detect stale connections
            pool_recycle=3600,        # recycle connections every hour
            echo=settings.debug,      # log SQL in debug mode
        )
        logger.info("PostgreSQL engine created")
    return _engine


def get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,  # don't expire objects after commit
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            max_connections=20,
        )
        logger.info("Redis connection pool created")
    return _redis


# ── FastAPI dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a database session.
    Automatically commits on success, rolls back on exception.

    Usage:
        @router.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ── Database initialization ───────────────────────────────────────────────────
async def init_db():
    """
    Create all tables and install full-text search trigger.
    Called once at app startup.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        # Create all tables defined in models.py
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified")

        # Install the full-text search trigger
        # asyncpg cannot run multiple statements in one call.
        # models.py separates each statement with a blank line (no semicolons).
        statements = [
            s.strip() for s in SEARCH_TRIGGER_SQL.strip().split("\n\n")
            if s.strip()
        ]
        for stmt in statements:
            await conn.execute(text(stmt))
        logger.info(f"Full-text search trigger installed ({len(statements)} statements)")


async def close_db():
    """Close database connections on app shutdown."""
    global _engine, _redis
    if _engine:
        await _engine.dispose()
        logger.info("PostgreSQL connections closed")
    if _redis:
        await _redis.aclose()
        logger.info("Redis connections closed")


# ── Cache helpers ─────────────────────────────────────────────────────────────
class CacheManager:
    """
    Simple cache wrapper with automatic serialization.
    Use this instead of calling Redis directly.
    """

    def __init__(self, redis_client: aioredis.Redis, prefix: str = "pkv"):
        self.redis = redis_client
        self.prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> str | None:
        return await self.redis.get(self._key(key))

    async def set(self, key: str, value: str, ttl: int = 300) -> None:
        await self.redis.setex(self._key(key), ttl, value)

    async def delete(self, key: str) -> None:
        await self.redis.delete(self._key(key))

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern. Use sparingly."""
        keys = await self.redis.keys(self._key(pattern))
        if keys:
            return await self.redis.delete(*keys)
        return 0

    async def increment(self, key: str, ttl: int = 60) -> int:
        """Atomic increment — used for rate limiting."""
        pipe = self.redis.pipeline()
        full_key = self._key(key)
        await pipe.incr(full_key)
        await pipe.expire(full_key, ttl)
        results = await pipe.execute()
        return results[0]
