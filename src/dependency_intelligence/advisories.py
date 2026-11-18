"""Merge advisory records linked by direct or transitive aliases."""

from __future__ import annotations

from .domain import Vulnerability


def merge_advisories(candidates: list[Vulnerability]) -> tuple[Vulnerability, ...]:
    parents: dict[str, str] = {}

    def root(identifier: str) -> str:
        parents.setdefault(identifier, identifier)
        while parents[identifier] != identifier:
            parents[identifier] = parents[parents[identifier]]
            identifier = parents[identifier]
        return identifier

    for candidate in candidates:
        for alias in candidate.aliases:
            parents[root(alias)] = root(candidate.identifier)
        root(candidate.identifier)

    groups: dict[str, list[Vulnerability]] = {}
    for candidate in candidates:
        groups.setdefault(root(candidate.identifier), []).append(candidate)

    merged: list[Vulnerability] = []
    for group in groups.values():
        ordered = sorted(group, key=lambda item: (_preference(item.identifier), item.identifier))
        representative = ordered[0]
        identifiers = {
            identifier for item in group for identifier in (item.identifier, *item.aliases)
        }
        merged.append(
            Vulnerability(
                identifier=representative.identifier,
                aliases=tuple(sorted(identifiers - {representative.identifier})),
                summary=next((item.summary for item in ordered if item.summary), None),
            )
        )
    return tuple(sorted(merged, key=lambda item: (_preference(item.identifier), item.identifier)))


def _preference(identifier: str) -> int:
    if identifier.startswith(("GHSA-", "OSV-")):
        return 0
    if identifier.startswith("CVE-"):
        return 1
    if identifier.startswith("PYSEC-"):
        return 3
    return 2
