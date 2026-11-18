"""Supplied per-key work coalescing used by the scanner ticket."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class _Flight[V]:
    task: asyncio.Task[V]
    waiters: int


class SingleFlight[K, V]:
    def __init__(self) -> None:
        self._flights: dict[K, _Flight[V]] = {}
        self._lock = asyncio.Lock()

    async def run(self, key: K, factory: Callable[[], Coroutine[Any, Any, V]]) -> tuple[V, bool]:
        async with self._lock:
            flight = self._flights.get(key)
            shared = flight is not None
            if flight is None:
                flight = _Flight(task=asyncio.create_task(factory()), waiters=0)
                self._flights[key] = flight
            flight.waiters += 1
        try:
            return await asyncio.shield(flight.task), shared
        finally:
            await self._release(key, flight)

    async def _release(self, key: K, flight: _Flight[V]) -> None:
        async with self._lock:
            if self._flights.get(key) is not flight:
                return
            flight.waiters -= 1
            if flight.waiters == 0:
                if not flight.task.done():
                    flight.task.cancel()
                del self._flights[key]
