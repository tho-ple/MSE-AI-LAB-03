"""Async TTL/LRU cache — process-local, concurrency-safe (SPEC 6)."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Callable


class AsyncTTLCache[K, V]:
    """Bounded cache with insertion-time expiry and least-recently-used eviction.

    The ``OrderedDict`` order is the recency order: the last entry is the most
    recently used one. Each entry stores its fixed expiry deadline next to the
    value (Decision 2: expired when ``now >= deadline``; reads never extend it).
    """

    def __init__(
        self,
        *,
        ttl_seconds: float,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._clock = clock
        self._entries: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: K) -> V | None:
        """Return a live value and mark it as most recently used, else ``None``."""
        async with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            deadline, value = entry
            if self._clock() >= deadline:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return value

    async def put(self, key: K, value: V) -> None:
        """Store a value with a fresh insertion-time deadline, then enforce capacity."""
        async with self._lock:
            now = self._clock()
            self._entries[key] = (now + self._ttl_seconds, value)
            self._entries.move_to_end(key)
            if len(self._entries) > self._max_entries:
                # Drop dead entries first so a live entry is never evicted in their place.
                self._purge_expired(now)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    async def size(self) -> int:
        """Return the number of live entries after removing expired entries."""
        async with self._lock:
            self._purge_expired(self._clock())
            return len(self._entries)

    def _purge_expired(self, now: float) -> None:
        expired = [key for key, (deadline, _) in self._entries.items() if now >= deadline]
        for key in expired:
            del self._entries[key]
