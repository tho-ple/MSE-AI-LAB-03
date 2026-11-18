"""Task C — DependencyScanner behaviour beyond the public contract tests."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from dependency_intelligence.cache import AsyncTTLCache
from dependency_intelligence.domain import (
    CacheStatus,
    DependencyCoordinate,
    FailureKind,
    PackageAssessment,
    PackageMetadata,
    ScanStatus,
    ServiceName,
    SupplyChainInformation,
    Vulnerability,
)
from dependency_intelligence.ports import (
    PackageMetadataSource,
    SupplyChainSource,
    VulnerabilitySource,
)
from dependency_intelligence.service import DependencyScanner

from .fakes import (
    FakeClock,
    FakeMetadataSource,
    FakeSupplyChainSource,
    FakeVulnerabilitySource,
    MemoryCache,
    StartGate,
    source_failure,
)

pytestmark = pytest.mark.orchestration

DEMO = DependencyCoordinate("demo", "1.0")


def build_scanner(
    metadata: PackageMetadataSource | None = None,
    vulnerabilities: VulnerabilitySource | None = None,
    supply_chain: SupplyChainSource | None = None,
    *,
    cache: MemoryCache | AsyncTTLCache[str, PackageAssessment] | None = None,
    max_concurrent_packages: int = 8,
) -> DependencyScanner:
    return DependencyScanner(
        metadata_source=metadata or FakeMetadataSource(),
        vulnerability_source=vulnerabilities or FakeVulnerabilitySource(),
        supply_chain_source=supply_chain or FakeSupplyChainSource(),
        cache=cache or MemoryCache(),
        max_concurrent_packages=max_concurrent_packages,
    )


async def settle(condition: Callable[[], bool], attempts: int = 20) -> None:
    """Yield to the event loop until ``condition()`` holds (no wall-clock sleeps)."""
    for _ in range(attempts):
        if condition():
            return
        await asyncio.sleep(0)


class ExplodingVulnerabilitySource:
    """Raises a non-source error whose message must never reach a report."""

    service_name = ServiceName.OSV

    async def fetch_vulnerabilities(
        self, coordinate: DependencyCoordinate
    ) -> tuple[Vulnerability, ...]:
        raise RuntimeError("secret-body from upstream")


class TrackingMetadataSource:
    """Counts how many packages are inside a source call at the same time."""

    service_name = ServiceName.PYPI

    def __init__(self) -> None:
        self.calls = 0
        self.active = 0
        self.max_active = 0
        self.release = asyncio.Event()

    async def fetch_metadata(self, coordinate: DependencyCoordinate) -> PackageMetadata:
        self.calls += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await self.release.wait()
        finally:
            self.active -= 1
        return PackageMetadata("2.0.0", None)


async def test_all_sources_failed_has_no_assessment() -> None:
    """S1 — Decision 1 and 7: no useful data → assessment None, ordered failures."""
    scanner = build_scanner(
        FakeMetadataSource(failure=source_failure(ServiceName.PYPI)),
        FakeVulnerabilitySource(failure=source_failure(ServiceName.OSV)),
        FakeSupplyChainSource(failure=source_failure(ServiceName.DEPS_DEV)),
    )

    report = await scanner.scan([DEMO])

    result = report.results[0]
    assert result.assessment is None
    assert [failure.service for failure in result.failures] == [
        ServiceName.PYPI,
        ServiceName.OSV,
        ServiceName.DEPS_DEV,
    ]
    assert report.status is ScanStatus.FAILED


async def test_empty_answer_is_kept_distinct_from_failure() -> None:
    """S2 — REQ-ASM-01: () means 'answered, nothing found'; None means 'failed'."""
    scanner = build_scanner(metadata=FakeMetadataSource(failure=source_failure(ServiceName.PYPI)))

    result = await scanner.assess(DEMO)

    assert result.assessment is not None
    assert result.assessment.metadata is None
    assert result.assessment.vulnerabilities == ()
    assert result.assessment.supply_chain is not None
    assert not result.complete


async def test_unexpected_exception_is_attributed_without_leaking_message() -> None:
    """S3 — Decision 3: unexpected errors become safe, attributed failures."""
    scanner = build_scanner(vulnerabilities=ExplodingVulnerabilitySource())

    result = await scanner.assess(DEMO)

    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.service is ServiceName.OSV
    assert failure.kind is FailureKind.UNEXPECTED
    assert not failure.retryable
    assert "secret-body" not in failure.detail
    assert failure.detail == "unexpected RuntimeError"
    assert result.assessment is not None
    assert result.assessment.vulnerabilities is None


async def test_failure_order_ignores_completion_order() -> None:
    """S4 — Decision 7: failures are ordered PyPI → OSV → deps.dev."""
    gates = {service: StartGate(1) for service in ServiceName}
    metadata = FakeMetadataSource(
        gate=gates[ServiceName.PYPI], failure=source_failure(ServiceName.PYPI)
    )
    vulnerabilities = FakeVulnerabilitySource(
        gate=gates[ServiceName.OSV], failure=source_failure(ServiceName.OSV)
    )
    supply_chain = FakeSupplyChainSource(
        gate=gates[ServiceName.DEPS_DEV], failure=source_failure(ServiceName.DEPS_DEV)
    )
    scanner = build_scanner(metadata, vulnerabilities, supply_chain)
    task = asyncio.create_task(scanner.assess(DEMO))
    await settle(lambda: all(gate.all_started.is_set() for gate in gates.values()))

    for service in (ServiceName.DEPS_DEV, ServiceName.OSV, ServiceName.PYPI):
        gates[service].release.set()
        for _ in range(3):
            await asyncio.sleep(0)

    result = await task
    assert [failure.service for failure in result.failures] == [
        ServiceName.PYPI,
        ServiceName.OSV,
        ServiceName.DEPS_DEV,
    ]


async def test_cancelling_scan_cancels_all_source_calls() -> None:
    """S5 — REQ-CON-05 / AC-08: a cancelled scan cancels every outstanding source call."""
    gate = StartGate(6)
    scanner = build_scanner(
        FakeMetadataSource(gate=gate),
        FakeVulnerabilitySource(gate=gate),
        FakeSupplyChainSource(gate=gate),
    )
    task = asyncio.create_task(
        scanner.scan([DependencyCoordinate("a", "1.0"), DependencyCoordinate("b", "1.0")])
    )
    await asyncio.wait_for(gate.all_started.wait(), timeout=1)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    await settle(lambda: gate.cancelled == 6)

    assert gate.cancelled == 6


async def test_cancelled_waiter_does_not_cancel_shared_load() -> None:
    """S6 — REQ-CON-07: the load survives while another waiter still needs it."""
    gate = StartGate(3)
    scanner = build_scanner(
        FakeMetadataSource(gate=gate),
        FakeVulnerabilitySource(gate=gate),
        FakeSupplyChainSource(gate=gate),
    )
    first = asyncio.create_task(scanner.assess(DEMO))
    second = asyncio.create_task(scanner.assess(DEMO))
    await asyncio.wait_for(gate.all_started.wait(), timeout=1)

    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    gate.release.set()
    result = await second

    assert result.complete
    assert result.cache_status is CacheStatus.COALESCED
    assert gate.cancelled == 0


async def test_package_limit_is_shared_by_concurrent_scans() -> None:
    """S7 — Decision 11: one limit per scanner, across concurrent scan() calls."""
    metadata = TrackingMetadataSource()
    scanner = build_scanner(metadata=metadata, max_concurrent_packages=2)
    scans = [
        asyncio.create_task(
            scanner.scan([DependencyCoordinate(f"{prefix}-{n}", "1.0") for n in range(2)])
        )
        for prefix in ("left", "right")
    ]
    await settle(lambda: metadata.calls >= 2)
    for _ in range(5):
        await asyncio.sleep(0)

    assert metadata.calls == 2
    metadata.release.set()
    reports = await asyncio.gather(*scans)

    assert metadata.max_active == 2
    assert metadata.calls == 4
    assert all(report.status is ScanStatus.COMPLETE for report in reports)


async def test_expired_cache_entry_is_loaded_again() -> None:
    """S8 — REQ-CACHE-10: hit within the TTL, a new miss and new calls after it."""
    clock = FakeClock()
    metadata = FakeMetadataSource()
    cache = AsyncTTLCache[str, PackageAssessment](ttl_seconds=60, max_entries=10, clock=clock)
    scanner = build_scanner(metadata=metadata, cache=cache)

    first = await scanner.assess(DEMO)
    second = await scanner.assess(DEMO)
    clock.advance(60)
    third = await scanner.assess(DEMO)

    assert [first.cache_status, second.cache_status, third.cache_status] == [
        CacheStatus.MISS,
        CacheStatus.HIT,
        CacheStatus.MISS,
    ]
    assert metadata.calls == 2


async def test_coalesced_waiters_share_a_partial_result_without_caching() -> None:
    """Decision 6: joined waiters report coalesced even for a partial result."""
    gate = StartGate(3)
    cache = MemoryCache()
    scanner = build_scanner(
        FakeMetadataSource(gate=gate),
        FakeVulnerabilitySource(gate=gate, failure=source_failure(ServiceName.OSV)),
        FakeSupplyChainSource(gate=gate),
        cache=cache,
    )
    callers = [asyncio.create_task(scanner.assess(DEMO)) for _ in range(3)]
    await asyncio.wait_for(gate.all_started.wait(), timeout=1)
    gate.release.set()

    results = await asyncio.gather(*callers)

    assert sorted(result.cache_status.value for result in results) == [
        "coalesced",
        "coalesced",
        "miss",
    ]
    assert all(not result.complete for result in results)
    assert cache.entries == {}


class CancellingSupplyChainSource:
    """Raises CancelledError on its own, without the caller being cancelled."""

    service_name = ServiceName.DEPS_DEV

    async def fetch_supply_chain(self, coordinate: DependencyCoordinate) -> SupplyChainInformation:
        raise asyncio.CancelledError


async def test_cancellation_is_never_reported_as_a_failure() -> None:
    """REQ-FAIL-05: a CancelledError from a source propagates instead of becoming a failure."""
    scanner = build_scanner(supply_chain=CancellingSupplyChainSource())

    with pytest.raises(asyncio.CancelledError):
        await scanner.assess(DEMO)


async def test_failure_is_attributed_to_the_calling_source() -> None:
    """REQ-FAIL-02: attribution comes from the source the scanner called."""
    mislabelled = source_failure(ServiceName.PYPI, FailureKind.UNAVAILABLE)
    scanner = build_scanner(vulnerabilities=FakeVulnerabilitySource(failure=mislabelled))

    result = await scanner.assess(DEMO)

    assert [failure.service for failure in result.failures] == [ServiceName.OSV]
    assert result.failures[0].kind is FailureKind.UNAVAILABLE
    assert result.failures[0].retryable
