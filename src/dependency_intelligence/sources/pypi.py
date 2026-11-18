"""PyPI package-metadata adapter — student implementation seam."""

from __future__ import annotations

from dependency_intelligence.domain import DependencyCoordinate, PackageMetadata, ServiceName
from dependency_intelligence.http import JsonHttpClient


class PyPIClient:
    service_name = ServiceName.PYPI

    def __init__(self, http: JsonHttpClient, *, base_url: str = "https://pypi.org") -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    async def fetch_metadata(self, coordinate: DependencyCoordinate) -> PackageMetadata:
        """Implement SPEC 4.1 and AC-02 without weakening source validation."""
        raise NotImplementedError("TODO: implement the PyPI adapter")
