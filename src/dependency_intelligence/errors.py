"""Typed errors crossing input and source boundaries."""

from __future__ import annotations

from dataclasses import dataclass

from .domain import FailureKind, ServiceName, SourceFailure


@dataclass(frozen=True, slots=True)
class ManifestIssue:
    line_number: int
    line: str
    reason: str


class ManifestValidationError(ValueError):
    def __init__(self, issues: tuple[ManifestIssue, ...]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"line {issue.line_number}: {issue.reason}" for issue in issues))


class SourceRequestError(RuntimeError):
    def __init__(
        self,
        service: ServiceName,
        kind: FailureKind,
        detail: str,
        *,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        self.failure = SourceFailure(service, kind, retryable, detail, status_code)
        super().__init__(f"{service}: {detail}")
