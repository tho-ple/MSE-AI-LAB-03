"""Dependency scan orchestration: concurrency, single-flight, caching (SPEC 5–7)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from .domain import (
    CacheStatus,
    DependencyCoordinate,
    DependencyScanResult,
    FailureKind,
    PackageAssessment,
    ProjectScanReport,
    ServiceName,
    SourceFailure,
)
from .errors import SourceRequestError
from .ports import AssessmentCache, PackageMetadataSource, SupplyChainSource, VulnerabilitySource
from .singleflight import SingleFlight


@dataclass(frozen=True, slots=True)
class _Outcome:
    """Result of one shared package load, before a caller adds its cache status."""

    assessment: PackageAssessment | None
    failures: tuple[SourceFailure, ...]


class DependencyScanner:
    def __init__(
        self,
        *,
        metadata_source: PackageMetadataSource,
        vulnerability_source: VulnerabilitySource,
        supply_chain_source: SupplyChainSource,
        cache: AssessmentCache,
        max_concurrent_packages: int = 8,
    ) -> None:
        if max_concurrent_packages <= 0:
            raise ValueError("max_concurrent_packages must be positive")
        self._metadata_source = metadata_source
        self._vulnerability_source = vulnerability_source
        self._supply_chain_source = supply_chain_source
        self._cache = cache
        self._max_concurrent_packages = max_concurrent_packages
        # Decision 11: one limit per scanner, shared by every concurrent scan().
        self._package_limit = asyncio.Semaphore(max_concurrent_packages)
        self._flights: SingleFlight[str, _Outcome] = SingleFlight()

    async def scan(
        self, dependencies: tuple[DependencyCoordinate, ...] | list[DependencyCoordinate]
    ) -> ProjectScanReport:
        """Assess packages concurrently within the limit and keep the input order.

        Cancelling the scan cancels and awaits every child task (TaskGroup).
        """
        async with asyncio.TaskGroup() as group:
            tasks = [
                group.create_task(self._assess_within_limit(coordinate))
                for coordinate in dependencies
            ]
        return ProjectScanReport(tuple(task.result() for task in tasks))

    async def assess(self, coordinate: DependencyCoordinate) -> DependencyScanResult:
        """Serve one package from the cache, a shared in-flight load, or a new load.

        Decision 6: cache hit → ``hit``; this caller started the load → ``miss``;
        this caller joined another caller's load → ``coalesced``.
        """
        key = coordinate.cache_key
        cached = await self._cache.get(key)
        if cached is not None:
            return DependencyScanResult(coordinate, cached, (), CacheStatus.HIT)
        outcome, shared = await self._flights.run(key, lambda: self._load(coordinate))
        return DependencyScanResult(
            coordinate,
            outcome.assessment,
            outcome.failures,
            CacheStatus.COALESCED if shared else CacheStatus.MISS,
        )

    async def _assess_within_limit(self, coordinate: DependencyCoordinate) -> DependencyScanResult:
        # Decision 10: the slot covers the whole assess(), including cache lookups.
        async with self._package_limit:
            return await self.assess(coordinate)

    async def _load(self, coordinate: DependencyCoordinate) -> _Outcome:
        """Query all three sources concurrently and cache the result only if complete.

        Runs as the SingleFlight task: when the last waiter leaves, this task is
        cancelled and the TaskGroup cancels and awaits the three source calls.
        """
        metadata_source = self._metadata_source
        vulnerability_source = self._vulnerability_source
        supply_chain_source = self._supply_chain_source
        async with asyncio.TaskGroup() as group:
            metadata_task = group.create_task(
                _capture(
                    metadata_source.service_name,
                    lambda: metadata_source.fetch_metadata(coordinate),
                )
            )
            vulnerability_task = group.create_task(
                _capture(
                    vulnerability_source.service_name,
                    lambda: vulnerability_source.fetch_vulnerabilities(coordinate),
                )
            )
            supply_chain_task = group.create_task(
                _capture(
                    supply_chain_source.service_name,
                    lambda: supply_chain_source.fetch_supply_chain(coordinate),
                )
            )
        metadata, metadata_failure = metadata_task.result()
        vulnerabilities, vulnerability_failure = vulnerability_task.result()
        supply_chain, supply_chain_failure = supply_chain_task.result()

        # Decision 7: fixed order PyPI → OSV → deps.dev, independent of completion order.
        failures = tuple(
            failure
            for failure in (metadata_failure, vulnerability_failure, supply_chain_failure)
            if failure is not None
        )
        # Decision 1: no successful source at all → no assessment (status "failed").
        # Otherwise None marks only a failed source; an empty () answer stays ().
        if metadata is None and vulnerabilities is None and supply_chain is None:
            return _Outcome(None, failures)
        assessment = PackageAssessment(coordinate, metadata, vulnerabilities, supply_chain)
        if assessment.complete and not failures:
            await self._cache.put(coordinate.cache_key, assessment)
        return _Outcome(assessment, failures)


async def _capture[T](
    service: ServiceName, operation: Callable[[], Awaitable[T]]
) -> tuple[T | None, SourceFailure | None]:
    """Turn one source call into a value or an attributed failure.

    ``CancelledError`` is a ``BaseException`` and deliberately passes through
    (REQ-FAIL-05). The operation is a factory so that a task cancelled before it
    starts never leaves an un-awaited coroutine behind.
    """
    try:
        return await operation(), None
    except SourceRequestError as error:
        return None, error.failure
    except Exception as error:
        # Decision 3: never expose the exception message; it may carry upstream data.
        return None, SourceFailure(
            service,
            FailureKind.UNEXPECTED,
            retryable=False,
            detail=f"unexpected {type(error).__name__}",
        )
