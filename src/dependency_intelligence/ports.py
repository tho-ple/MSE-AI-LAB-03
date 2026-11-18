"""Stable interfaces enabling independent adapter and orchestration tickets."""

from __future__ import annotations

from typing import Protocol

from .domain import (
    DependencyCoordinate,
    PackageAssessment,
    PackageMetadata,
    ServiceName,
    SupplyChainInformation,
    Vulnerability,
)


class PackageMetadataSource(Protocol):
    service_name: ServiceName

    async def fetch_metadata(self, coordinate: DependencyCoordinate) -> PackageMetadata: ...


class VulnerabilitySource(Protocol):
    service_name: ServiceName

    async def fetch_vulnerabilities(
        self, coordinate: DependencyCoordinate
    ) -> tuple[Vulnerability, ...]: ...


class SupplyChainSource(Protocol):
    service_name: ServiceName

    async def fetch_supply_chain(
        self, coordinate: DependencyCoordinate
    ) -> SupplyChainInformation: ...


class AssessmentCache(Protocol):
    async def get(self, key: str) -> PackageAssessment | None: ...

    async def put(self, key: str, value: PackageAssessment) -> None: ...
