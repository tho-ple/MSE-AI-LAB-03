"""deps.dev supply-chain adapter — student implementation seam."""

from __future__ import annotations

from dependency_intelligence.domain import (
    DependencyCoordinate,
    ServiceName,
    SupplyChainInformation,
)
from dependency_intelligence.http import JsonHttpClient


class DepsDevClient:
    service_name = ServiceName.DEPS_DEV

    def __init__(self, http: JsonHttpClient, *, base_url: str = "https://api.deps.dev") -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    async def fetch_supply_chain(self, coordinate: DependencyCoordinate) -> SupplyChainInformation:
        """Implement SPEC 4.3 and AC-02/03 with concurrent endpoint calls."""
        raise NotImplementedError("TODO: implement the deps.dev adapter")
