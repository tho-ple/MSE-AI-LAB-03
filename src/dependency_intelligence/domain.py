"""Validated domain records shared by every transport and source adapter."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from packaging.utils import canonicalize_name
from packaging.version import InvalidVersion, Version


class ServiceName(StrEnum):
    PYPI = "pypi"
    OSV = "osv"
    DEPS_DEV = "deps.dev"


class FailureKind(StrEnum):
    NOT_FOUND = "not_found"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"
    UNEXPECTED = "unexpected"


class CacheStatus(StrEnum):
    HIT = "hit"
    MISS = "miss"
    COALESCED = "coalesced"


class UpdateStatus(StrEnum):
    CURRENT = "current"
    OUTDATED = "outdated"
    AHEAD = "ahead"
    UNKNOWN = "unknown"


class ScanStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class DependencyCoordinate:
    name: str
    version: str
    ecosystem: str = "PyPI"

    def __post_init__(self) -> None:
        normalized_name = canonicalize_name(self.name.strip(), validate=True)
        version = self.version.strip()
        if not version:
            raise ValueError("dependency version must not be empty")
        Version(version)
        if self.ecosystem.casefold() != "pypi":
            raise ValueError("only the PyPI ecosystem is supported")
        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "ecosystem", "PyPI")

    @property
    def cache_key(self) -> str:
        return f"{self.ecosystem.casefold()}:{self.name}:{self.version}"

    @property
    def display_name(self) -> str:
        return f"{self.name}=={self.version}"


@dataclass(frozen=True, slots=True)
class PackageMetadata:
    latest_version: str
    requires_python: str | None


@dataclass(frozen=True, slots=True)
class Vulnerability:
    identifier: str
    aliases: tuple[str, ...]
    summary: str | None


@dataclass(frozen=True, slots=True)
class SupplyChainInformation:
    licenses: tuple[str, ...]
    direct_dependency_count: int
    published_at: str | None


@dataclass(frozen=True, slots=True)
class SourceFailure:
    service: ServiceName
    kind: FailureKind
    retryable: bool
    detail: str
    status_code: int | None = None


@dataclass(frozen=True, slots=True)
class PackageAssessment:
    coordinate: DependencyCoordinate
    metadata: PackageMetadata | None
    vulnerabilities: tuple[Vulnerability, ...] | None
    supply_chain: SupplyChainInformation | None

    @property
    def complete(self) -> bool:
        return all(
            value is not None for value in (self.metadata, self.vulnerabilities, self.supply_chain)
        )

    @property
    def update_status(self) -> UpdateStatus:
        if self.metadata is None:
            return UpdateStatus.UNKNOWN
        try:
            installed = Version(self.coordinate.version)
            latest = Version(self.metadata.latest_version)
        except InvalidVersion:
            return UpdateStatus.UNKNOWN
        if installed < latest:
            return UpdateStatus.OUTDATED
        if installed > latest:
            return UpdateStatus.AHEAD
        return UpdateStatus.CURRENT


@dataclass(frozen=True, slots=True)
class DependencyScanResult:
    coordinate: DependencyCoordinate
    assessment: PackageAssessment | None
    failures: tuple[SourceFailure, ...]
    cache_status: CacheStatus

    @property
    def complete(self) -> bool:
        return self.assessment is not None and self.assessment.complete and not self.failures

    @property
    def useful(self) -> bool:
        return self.assessment is not None


@dataclass(frozen=True, slots=True)
class ProjectScanReport:
    results: tuple[DependencyScanResult, ...]

    @property
    def status(self) -> ScanStatus:
        if all(result.complete for result in self.results):
            return ScanStatus.COMPLETE
        if any(result.useful for result in self.results):
            return ScanStatus.PARTIAL
        return ScanStatus.FAILED

    @property
    def total_dependencies(self) -> int:
        return len(self.results)

    @property
    def vulnerable_dependencies(self) -> int:
        return sum(
            1 for result in self.results if result.assessment and result.assessment.vulnerabilities
        )

    @property
    def outdated_dependencies(self) -> int:
        return sum(
            1
            for result in self.results
            if result.assessment and result.assessment.update_status is UpdateStatus.OUTDATED
        )
