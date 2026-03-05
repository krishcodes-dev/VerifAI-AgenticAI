"""
app/services/redis_client.py

Centralized Redis client factory.

• Single connection pool shared across the process lifetime.
• Provides a lazy-initialised async-compatible client (redis-py 5.x sync client
  is used here for simplicity — the sync client works fine in FastAPI endpoints
  when called from thread-pool-backed sync deps, or invoked directly from async
  code with proper awaiting via `asyncio.to_thread` if needed).
• Graceful degradation: if Redis is unavailable, methods log a warning and fall
  back to no-op behaviour so the rest of the app keeps running.
"""

import logging
from functools import lru_cache
from typing import Optional

import redis
from redis import Redis

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_redis_client() -> Optional[Redis]:
    """
    Return a singleton Redis client connected to the URL from settings.
    Returns None if the connection cannot be established (graceful degradation).
    """
    settings = get_settings()
    try:
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=False,
        )
        client.ping()   # Verify the connection early
        logger.info("✅ Redis connected at %s", settings.REDIS_URL)
        return client
    except Exception as exc:
        logger.error(
            "❌ Redis unavailable at %s: %s — falling back to in-memory only",
            settings.REDIS_URL, exc,
        )
        return None


def redis_set(key: str, value: str, ex: int | None = None) -> bool:
    """
    SET a key in Redis with optional TTL (seconds).
    Returns True on success, False if Redis is unavailable.
    """
    client = get_redis_client()
    if client is None:
        return False
    try:
        client.set(key, value, ex=ex)
        return True
    except Exception as exc:
        logger.error("Redis SET failed for key=%s: %s", key, exc)
        return False


def redis_get(key: str) -> Optional[str]:
    """GET a key from Redis. Returns None if Redis is unavailable or key missing."""
    client = get_redis_client()
    if client is None:
        return None
    try:
        return client.get(key)
    except Exception as exc:
        logger.error("Redis GET failed for key=%s: %s", key, exc)
        return None


def redis_exists(key: str) -> bool:
    """Returns True if the key exists in Redis."""
    client = get_redis_client()
    if client is None:
        return False
    try:
        return bool(client.exists(key))
    except Exception as exc:
        logger.error("Redis EXISTS failed for key=%s: %s", key, exc)
        return False


def redis_delete(key: str) -> bool:
    """DELETE a key from Redis. Returns True on success."""
    client = get_redis_client()
    if client is None:
        return False
    try:
        client.delete(key)
        return True
    except Exception as exc:
        logger.error("Redis DELETE failed for key=%s: %s", key, exc)
        return False


def redis_lpush_bounded(key: str, value: str, max_len: int, ttl: int) -> bool:
    """
    Prepend a value to a Redis list, trim it to max_len, and set a TTL.
    Used for storing bounded transaction history per user.
    """
    client = get_redis_client()
    if client is None:
        return False
    try:
        pipe = client.pipeline()
        pipe.lpush(key, value)
        pipe.ltrim(key, 0, max_len - 1)
        pipe.expire(key, ttl)
        pipe.execute()
        return True
    except Exception as exc:
        logger.error("Redis LPUSH_BOUNDED failed for key=%s: %s", key, exc)
        return False


def redis_lrange(key: str, start: int = 0, end: int = -1) -> list[str]:
    """Return elements from a Redis list."""
    client = get_redis_client()
    if client is None:
        return []
    try:
        return client.lrange(key, start, end)
    except Exception as exc:
        logger.error("Redis LRANGE failed for key=%s: %s", key, exc)
        return []
