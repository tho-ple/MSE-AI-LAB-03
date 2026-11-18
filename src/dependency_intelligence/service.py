"""Dependency scan orchestration — student implementation seam."""

from __future__ import annotations

from .domain import DependencyCoordinate, DependencyScanResult, ProjectScanReport
from .ports import AssessmentCache, PackageMetadataSource, SupplyChainSource, VulnerabilitySource


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

    async def scan(
        self, dependencies: tuple[DependencyCoordinate, ...] | list[DependencyCoordinate]
    ) -> ProjectScanReport:
        """Implement bounded package concurrency, cancellation, and stable order."""
        raise NotImplementedError("TODO: implement project scanning")

    async def assess(self, coordinate: DependencyCoordinate) -> DependencyScanResult:
        """Implement cache/single-flight and concurrent source aggregation."""
        raise NotImplementedError("TODO: implement one package assessment")
