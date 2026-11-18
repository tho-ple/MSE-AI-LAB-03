from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from dependency_intelligence.domain import (
    DependencyCoordinate,
    FailureKind,
    PackageAssessment,
    PackageMetadata,
    ServiceName,
    SupplyChainInformation,
    Vulnerability,
)
from dependency_intelligence.errors import SourceRequestError


class StartGate:
    def __init__(self, expected_starts: int) -> None:
        self.expected_starts = expected_starts
        self.starts = 0
        self.all_started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancelled = 0

    async def wait(self) -> None:
        self.starts += 1
        if self.starts >= self.expected_starts:
            self.all_started.set()
        try:
            await self.release.wait()
        except asyncio.CancelledError:
            self.cancelled += 1
            raise


@dataclass
class FakeMetadataSource:
    gate: StartGate | None = None
    failure: SourceRequestError | None = None
    latest_version: str = "2.0.0"
    calls: int = 0

    service_name = ServiceName.PYPI

    async def fetch_metadata(self, coordinate: DependencyCoordinate) -> PackageMetadata:
        self.calls += 1
        if self.gate:
            await self.gate.wait()
        if self.failure:
            raise self.failure
        return PackageMetadata(self.latest_version, ">=3.10")


@dataclass
class FakeVulnerabilitySource:
    gate: StartGate | None = None
    failure: SourceRequestError | None = None
    vulnerabilities: tuple[Vulnerability, ...] = ()
    calls: int = 0

    service_name = ServiceName.OSV

    async def fetch_vulnerabilities(
        self, coordinate: DependencyCoordinate
    ) -> tuple[Vulnerability, ...]:
        self.calls += 1
        if self.gate:
            await self.gate.wait()
        if self.failure:
            raise self.failure
        return self.vulnerabilities


@dataclass
class FakeSupplyChainSource:
    gate: StartGate | None = None
    failure: SourceRequestError | None = None
    calls: int = 0

    service_name = ServiceName.DEPS_DEV

    async def fetch_supply_chain(self, coordinate: DependencyCoordinate) -> SupplyChainInformation:
        self.calls += 1
        if self.gate:
            await self.gate.wait()
        if self.failure:
            raise self.failure
        return SupplyChainInformation(("MIT",), 2, "2024-01-01T00:00:00Z")


@dataclass
class MemoryCache:
    entries: dict[str, PackageAssessment] = field(default_factory=dict)

    async def get(self, key: str) -> PackageAssessment | None:
        return self.entries.get(key)

    async def put(self, key: str, value: PackageAssessment) -> None:
        self.entries[key] = value


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


def source_failure(
    service: ServiceName, kind: FailureKind = FailureKind.TIMEOUT
) -> SourceRequestError:
    return SourceRequestError(
        service,
        kind,
        f"simulated {kind.value}",
        retryable=kind in {FailureKind.TIMEOUT, FailureKind.UNAVAILABLE},
    )
