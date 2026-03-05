"""
app/services/history_store.py

User transaction history cache with Redis backend and in-memory fallback.

Architecture:
  • Primary: Redis LPUSH list per user, key = verifai:history:{user_id}
    - Bounded to MAX_HISTORY_PER_USER entries via LTRIM
    - TTL of HISTORY_TTL_SECONDS (7 days) so stale users auto-expire
    - Survives server restarts and works across multiple server instances
  • Fallback: asyncio-lock-guarded in-memory dict
    - Used automatically when Redis is unavailable
    - Bounded to MAX_HISTORY_PER_USER with the same cap
    - Lost on restart (same behaviour as before this sprint)

The calling code (agent.py) is unchanged — it still calls
  await store.add_transaction(user_id, tx)
  await store.get_user_history(user_id)
"""

import asyncio
import json
import logging
from collections import defaultdict

from app.services.redis_client import redis_lpush_bounded, redis_lrange, redis_delete

logger = logging.getLogger(__name__)

MAX_HISTORY_PER_USER = 200
HISTORY_TTL_SECONDS = 7 * 24 * 3600  # 7 days
_REDIS_KEY_PREFIX = "verifai:history:"


class UserTransactionHistory:
    """
    Thread-safe transaction history store backed by Redis (with in-memory fallback).
    """

    def __init__(self):
        # In-memory fallback (used when Redis is unavailable)
        self._memory: dict[str, list[dict]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def _redis_key(self, user_id: str) -> str:
        return f"{_REDIS_KEY_PREFIX}{user_id}"

    async def add_transaction(self, user_id: str, transaction: dict) -> None:
        """Prepend a transaction to the user's history (Redis-first, memory fallback)."""
        serialized = json.dumps(transaction, default=str)

        # Try Redis first
        success = redis_lpush_bounded(
            key=self._redis_key(user_id),
            value=serialized,
            max_len=MAX_HISTORY_PER_USER,
            ttl=HISTORY_TTL_SECONDS,
        )
        if success:
            return

        # Fallback: in-memory
        async with self._lock:
            history = self._memory[user_id]
            history.insert(0, transaction)
            if len(history) > MAX_HISTORY_PER_USER:
                self._memory[user_id] = history[:MAX_HISTORY_PER_USER]
            logger.debug("[history_store] Stored in-memory for user=%s (Redis unavailable)", user_id)

    async def get_user_history(self, user_id: str) -> list[dict]:
        """Return up to MAX_HISTORY_PER_USER transactions for the user."""
        # Try Redis first
        raw_list = redis_lrange(self._redis_key(user_id), 0, MAX_HISTORY_PER_USER - 1)
        if raw_list:
            try:
                return [json.loads(item) for item in raw_list]
            except json.JSONDecodeError as exc:
                logger.error("[history_store] Failed to decode history for user=%s: %s", user_id, exc)
                return []

        # Fallback: in-memory
        async with self._lock:
            return list(self._memory.get(user_id, []))

    async def clear_user_history(self, user_id: str) -> None:
        """Remove all history for a user (e.g. on account deletion)."""
        redis_delete(self._redis_key(user_id))
        async with self._lock:
            self._memory.pop(user_id, None)

    def total_users_in_memory(self) -> int:
        return len(self._memory)
