"""PyPI package-metadata adapter (SPEC 4.1, design.md §3.1)."""

from __future__ import annotations

from urllib.parse import quote

from dependency_intelligence.domain import DependencyCoordinate, PackageMetadata, ServiceName
from dependency_intelligence.http import JsonHttpClient
from dependency_intelligence.upstream_models import PyPIResponse, parse_response


class PyPIClient:
    service_name = ServiceName.PYPI

    def __init__(self, http: JsonHttpClient, *, base_url: str = "https://pypi.org") -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    async def fetch_metadata(self, coordinate: DependencyCoordinate) -> PackageMetadata:
        """Return the latest version and Python requirement for one package.

        Every failure leaves this method as a ``SourceRequestError`` attributed to
        PyPI: HTTP and JSON problems come from ``JsonHttpClient`` (REQ-FAIL-03), and
        schema problems, such as a missing or unparseable ``info.version``
        (REQ-PYPI-03), come from ``parse_response`` (REQ-SRC-02).
        """
        # Decision 8: percent-encode the path segment. The coordinate name is
        # already normalized, so this only matters for unexpected characters.
        url = f"{self._base_url}/pypi/{quote(coordinate.name, safe='')}/json"
        data = await self._http.request_json(self.service_name, "GET", url)
        response = parse_response(PyPIResponse, data, self.service_name)
        return PackageMetadata(
            latest_version=response.info.version,
            requires_python=response.info.requires_python,
        )
