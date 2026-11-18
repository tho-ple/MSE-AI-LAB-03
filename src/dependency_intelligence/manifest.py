"""Supplied deterministic requirements.lock parser."""

from __future__ import annotations

from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

from .domain import DependencyCoordinate
from .errors import ManifestIssue, ManifestValidationError


class RequirementsLockParser:
    def __init__(self, *, max_bytes: int = 64_000, max_dependencies: int = 200) -> None:
        self._max_bytes = max_bytes
        self._max_dependencies = max_dependencies

    def parse_file(self, path: Path) -> tuple[DependencyCoordinate, ...]:
        with path.open("rb") as stream:
            raw = stream.read(self._max_bytes + 1)
        if len(raw) > self._max_bytes:
            raise ManifestValidationError(
                (ManifestIssue(0, path.name, f"manifest exceeds {self._max_bytes} bytes"),)
            )
        try:
            content = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ManifestValidationError(
                (ManifestIssue(0, path.name, "manifest is not valid UTF-8"),)
            ) from error
        return self.parse(content)

    def parse(self, content: str) -> tuple[DependencyCoordinate, ...]:
        dependencies: list[DependencyCoordinate] = []
        issues: list[ManifestIssue] = []
        seen: set[str] = set()
        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            line = raw_line.partition("#")[0].strip()
            if not line:
                continue
            try:
                requirement = Requirement(line)
            except InvalidRequirement:
                issues.append(ManifestIssue(line_number, raw_line, "invalid requirement syntax"))
                continue
            specifiers = list(requirement.specifier)
            if requirement.url is not None:
                reason = "URL dependencies are unsupported"
            elif requirement.marker is not None:
                reason = "environment markers are unsupported"
            elif requirement.extras:
                reason = "extras are unsupported"
            elif len(specifiers) != 1 or specifiers[0].operator != "==":
                reason = "dependency must use one exact == version"
            elif "*" in specifiers[0].version:
                reason = "wildcard versions are unsupported"
            else:
                reason = ""
            if reason:
                issues.append(ManifestIssue(line_number, raw_line, reason))
                continue
            try:
                coordinate = DependencyCoordinate(requirement.name, specifiers[0].version)
            except ValueError as error:
                issues.append(ManifestIssue(line_number, raw_line, str(error)))
                continue
            if coordinate.name in seen:
                issues.append(
                    ManifestIssue(line_number, raw_line, "duplicate normalized package name")
                )
                continue
            seen.add(coordinate.name)
            dependencies.append(coordinate)
        if len(dependencies) > self._max_dependencies:
            issues.append(
                ManifestIssue(
                    0, "", f"manifest contains more than {self._max_dependencies} dependencies"
                )
            )
        if not dependencies and not issues:
            issues.append(ManifestIssue(0, "", "manifest contains no dependencies"))
        if issues:
            raise ManifestValidationError(tuple(issues))
        return tuple(dependencies)
