"""OSV vulnerability adapter — student implementation seam."""

from __future__ import annotations

from dependency_intelligence.domain import DependencyCoordinate, ServiceName, Vulnerability
from dependency_intelligence.http import JsonHttpClient


class OSVClient:
    service_name = ServiceName.OSV

    def __init__(self, http: JsonHttpClient, *, base_url: str = "https://api.osv.dev") -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    async def fetch_vulnerabilities(
        self, coordinate: DependencyCoordinate
    ) -> tuple[Vulnerability, ...]:
        """Implement SPEC 4.2 and AC-02, including transitive alias merging."""
        raise NotImplementedError("TODO: implement the OSV adapter")
