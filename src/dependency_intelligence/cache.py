"""Async TTL/LRU cache — student implementation seam."""

from __future__ import annotations

import time
from collections.abc import Callable


class AsyncTTLCache[K, V]:
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

    async def get(self, key: K) -> V | None:
        """Implement concurrency-safe hit, expiry, and LRU access behavior."""
        raise NotImplementedError("TODO: implement cache reads")

    async def put(self, key: K, value: V) -> None:
        """Implement insertion-time TTL and bounded LRU eviction."""
        raise NotImplementedError("TODO: implement cache writes")

    async def size(self) -> int:
        """Return the number of live entries after removing expired entries."""
        raise NotImplementedError("TODO: implement cache size")
