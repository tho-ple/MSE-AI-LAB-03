"""OSV vulnerability adapter (SPEC 4.2, design.md §3.2)."""

from __future__ import annotations

from typing import Any

from dependency_intelligence.advisories import merge_advisories
from dependency_intelligence.domain import DependencyCoordinate, ServiceName, Vulnerability
from dependency_intelligence.http import JsonHttpClient
from dependency_intelligence.upstream_models import OSVResponse, parse_response


class OSVClient:
    service_name = ServiceName.OSV

    def __init__(self, http: JsonHttpClient, *, base_url: str = "https://api.osv.dev") -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    async def fetch_vulnerabilities(
        self, coordinate: DependencyCoordinate
    ) -> tuple[Vulnerability, ...]:
        """Return the merged advisories recorded for one exact coordinate.

        An omitted ``vulns`` field validates to an empty list, so ``()`` is a
        successful "no advisories" answer (REQ-OSV-02), not a failure. A ``vulns``
        value of the wrong type is an ``invalid_response`` (REQ-OSV-04).
        """
        # REQ-OSV-01: the coordinate travels in the JSON body, so no URL encoding
        # is needed here (Decision 8).
        body: dict[str, Any] = {
            "package": {"name": coordinate.name, "ecosystem": "PyPI"},
            "version": coordinate.version,
        }
        data = await self._http.request_json(
            self.service_name, "POST", f"{self._base_url}/v1/query", json=body
        )
        response = parse_response(OSVResponse, data, self.service_name)
        # REQ-OSV-03: merge_advisories joins records linked by aliases, including
        # chains such as A-B, B-C, and keeps every alias and an available summary.
        return merge_advisories(
            [
                Vulnerability(
                    identifier=entry.id,
                    aliases=tuple(entry.aliases),
                    summary=entry.summary,
                )
                for entry in response.vulns
            ]
        )
