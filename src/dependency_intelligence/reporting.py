"""Stable JSON-compatible report projection supplied to all transports."""

from __future__ import annotations

from typing import Any

from .domain import ProjectScanReport


def report_to_dict(report: ProjectScanReport) -> dict[str, Any]:
    dependencies: list[dict[str, Any]] = []
    all_failures: list[dict[str, Any]] = []
    for result in report.results:
        assessment = result.assessment
        failures = [
            {
                "dependency": result.coordinate.display_name,
                "service": failure.service.value,
                "kind": failure.kind.value,
                "retryable": failure.retryable,
                "detail": failure.detail,
                "status_code": failure.status_code,
            }
            for failure in result.failures
        ]
        all_failures.extend(failures)
        dependencies.append(
            {
                "name": result.coordinate.name,
                "installed_version": result.coordinate.version,
                "ecosystem": result.coordinate.ecosystem,
                "latest_version": assessment.metadata.latest_version
                if assessment and assessment.metadata
                else None,
                "requires_python": assessment.metadata.requires_python
                if assessment and assessment.metadata
                else None,
                "update_status": assessment.update_status.value if assessment else "unknown",
                "licenses": list(assessment.supply_chain.licenses)
                if assessment and assessment.supply_chain
                else None,
                "direct_dependency_count": assessment.supply_chain.direct_dependency_count
                if assessment and assessment.supply_chain
                else None,
                "published_at": assessment.supply_chain.published_at
                if assessment and assessment.supply_chain
                else None,
                "vulnerabilities": [
                    {
                        "id": vulnerability.identifier,
                        "aliases": list(vulnerability.aliases),
                        "summary": vulnerability.summary,
                    }
                    for vulnerability in assessment.vulnerabilities
                ]
                if assessment and assessment.vulnerabilities is not None
                else None,
                "cache_status": result.cache_status.value,
                "complete": result.complete,
                "failures": failures,
            }
        )
    return {
        "status": report.status.value,
        "summary": {
            "total_dependencies": report.total_dependencies,
            "vulnerable_dependencies": report.vulnerable_dependencies,
            "outdated_dependencies": report.outdated_dependencies,
            "failure_count": len(all_failures),
        },
        "dependencies": dependencies,
        "failures": all_failures,
    }
