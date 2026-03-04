"""
history_store.py — In-Process User Transaction History Cache

IMPORTANT LIMITATIONS:
  - This store lives in memory within a single process. All data is
    lost when the application restarts or redeploys.
  - It does NOT scale horizontally — different server instances will
    have independent, inconsistent history stores.

PRODUCTION RECOMMENDATION:
  Replace this with one of:
  (a) Database queries against the Transaction table (already persisted by the router)
  (b) Redis RPUSH/LRANGE with per-user TTL for fast, shared cache

For the current MVP, this store provides same-session behavioural baseline
calculation which is sufficient for single-instance development use.

Each user's history is capped at MAX_HISTORY_PER_USER to prevent memory leaks.
"""

import asyncio
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# Maximum number of transactions kept per user. Oldest entries are dropped
# when this limit is exceeded to prevent unbounded memory growth.
MAX_HISTORY_PER_USER = 200


class UserTransactionHistory:
    """
    Thread-safe, in-memory store for user transaction history.
    Used by FeatureEngineer to compute behavioural baselines per user.
    """

    def __init__(self):
        self._history: dict[str, list[dict]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def add_transaction(self, user_id: str, transaction: dict) -> None:
        """
        Append a transaction to the user's in-memory history.
        Trims to MAX_HISTORY_PER_USER to prevent unbounded growth.
        """
        async with self._lock:
            history = self._history[user_id]
            history.append(transaction)

            # Enforce memory cap — keep only the most recent entries
            if len(history) > MAX_HISTORY_PER_USER:
                self._history[user_id] = history[-MAX_HISTORY_PER_USER:]
                logger.debug(
                    "Trimmed history for user=%s to %d entries",
                    user_id, MAX_HISTORY_PER_USER,
                )

    async def get_user_history(self, user_id: str) -> list[dict]:
        """Return a copy of the user's transaction history (safe for concurrent reads)."""
        async with self._lock:
            # Return a shallow copy so callers can't mutate the internal list
            return list(self._history.get(user_id, []))

    async def clear_user_history(self, user_id: str) -> None:
        """Remove all stored history for a user (e.g. on account deletion)."""
        async with self._lock:
            self._history.pop(user_id, None)

    def total_users_in_cache(self) -> int:
        """Return the number of users currently holding history in memory."""
        return len(self._history)
