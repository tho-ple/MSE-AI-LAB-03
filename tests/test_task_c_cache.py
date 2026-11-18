"""Task C — AsyncTTLCache behaviour beyond the public contract test (REQ-CACHE-*)."""

from __future__ import annotations

import asyncio

import pytest

from dependency_intelligence.cache import AsyncTTLCache

from .fakes import FakeClock

pytestmark = pytest.mark.cache


async def test_get_refreshes_lru_position() -> None:
    """C1 — a successful read makes the entry most recently used (REQ-CACHE-05)."""
    cache = AsyncTTLCache[str, str](ttl_seconds=10, max_entries=2, clock=FakeClock())
    await cache.put("a", "A")
    await cache.put("b", "B")
    assert await cache.get("a") == "A"

    await cache.put("c", "C")

    assert await cache.get("b") is None
    assert await cache.get("a") == "A"
    assert await cache.get("c") == "C"


async def test_get_does_not_extend_expiry() -> None:
    """C2 — expiry is fixed at insertion (REQ-CACHE-04, Decision 2)."""
    clock = FakeClock()
    cache = AsyncTTLCache[str, str](ttl_seconds=10, max_entries=5, clock=clock)
    await cache.put("a", "A")

    clock.advance(9)
    assert await cache.get("a") == "A"
    clock.advance(1)

    assert await cache.get("a") is None


async def test_put_overwrites_value_and_resets_expiry() -> None:
    """C3 — re-inserting a key stores the new value with a new deadline."""
    clock = FakeClock()
    cache = AsyncTTLCache[str, str](ttl_seconds=10, max_entries=5, clock=clock)
    await cache.put("a", "old")
    clock.advance(5)
    await cache.put("a", "new")

    clock.advance(9)
    assert await cache.get("a") == "new"
    clock.advance(1)
    assert await cache.get("a") is None


async def test_size_counts_only_live_entries() -> None:
    """C4 — size() purges expired entries (REQ-CACHE-06)."""
    clock = FakeClock()
    cache = AsyncTTLCache[str, str](ttl_seconds=10, max_entries=5, clock=clock)
    await cache.put("a", "A")
    clock.advance(5)
    await cache.put("b", "B")
    assert await cache.size() == 2

    clock.advance(5)

    assert await cache.size() == 1
    assert await cache.get("b") == "B"


async def test_expired_entries_are_evicted_before_live_ones() -> None:
    """At capacity, a dead entry makes room before any live LRU entry is dropped."""
    clock = FakeClock()
    cache = AsyncTTLCache[str, str](ttl_seconds=10, max_entries=2, clock=clock)
    await cache.put("live", "L")
    clock.advance(5)
    await cache.put("dying", "D")
    assert await cache.get("live") == "L"
    clock.advance(6)
    # "live" expired at t=10, "dying" at t=15; at t=11 only "dying" is alive.
    await cache.put("new", "N")

    assert await cache.get("dying") == "D"
    assert await cache.get("new") == "N"
    assert await cache.size() == 2


async def test_concurrent_access_keeps_capacity_bound() -> None:
    """C5 — concurrent writers and readers never exceed max_entries (REQ-CACHE-01)."""
    cache = AsyncTTLCache[int, int](ttl_seconds=60, max_entries=10, clock=FakeClock())

    async def writer(index: int) -> None:
        await cache.put(index, index)

    async def reader(index: int) -> int | None:
        return await cache.get(index)

    await asyncio.gather(*(writer(i) for i in range(50)), *(reader(i) for i in range(50)))

    assert await cache.size() <= 10
    assert await cache.get(49) == 49


def test_rejects_non_positive_bounds() -> None:
    """REQ-CACHE-03 — TTL and capacity must be positive."""
    with pytest.raises(ValueError, match="ttl_seconds must be positive"):
        AsyncTTLCache[str, str](ttl_seconds=0, max_entries=1)
    with pytest.raises(ValueError, match="max_entries must be positive"):
        AsyncTTLCache[str, str](ttl_seconds=1, max_entries=0)
