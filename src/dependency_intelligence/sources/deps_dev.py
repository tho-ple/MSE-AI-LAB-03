"""deps.dev supply-chain adapter — student implementation seam."""

from __future__ import annotations

import asyncio
from urllib.parse import quote

from packaging.version import Version

from dependency_intelligence.domain import (
    DependencyCoordinate,
    FailureKind,
    ServiceName,
    SupplyChainInformation,
)
from dependency_intelligence.errors import SourceRequestError
from dependency_intelligence.http import JsonHttpClient
from dependency_intelligence.upstream_models import (
    DepsGraph,
    DepsMetadata,
    VersionKey,
    parse_response,
)


class DepsDevClient:
    service_name = ServiceName.DEPS_DEV

    def __init__(self, http: JsonHttpClient, *, base_url: str = "https://api.deps.dev") -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")

    async def fetch_supply_chain(self, coordinate: DependencyCoordinate) -> SupplyChainInformation:
        base_path = (
            f"{self._base_url}/v3/systems/PYPI/packages/{quote(coordinate.name, safe='')}"
            f"/versions/{quote(coordinate.version, safe='')}"
        )

        try:
            async with asyncio.TaskGroup() as task_group:
                metadata_task = task_group.create_task(
                    self._http.request_json(self.service_name, "GET", base_path)
                )
                graph_task = task_group.create_task(
                    self._http.request_json(self.service_name, "GET", f"{base_path}:dependencies")
                )
        except ExceptionGroup as group:
            source_error = next(
                (error for error in group.exceptions if isinstance(error, SourceRequestError)),
                None,
            )
            if source_error is None:
                raise
            raise source_error from group

        metadata = parse_response(DepsMetadata, metadata_task.result(), self.service_name)
        graph = parse_response(DepsGraph, graph_task.result(), self.service_name)
        root = graph.nodes[0]
        if not _matches_coordinate(metadata.version_key, coordinate) or not _matches_coordinate(
            root.version_key, coordinate
        ):
            raise SourceRequestError(
                self.service_name,
                FailureKind.INVALID_RESPONSE,
                "response package identity did not match the requested coordinate",
                retryable=False,
            )

        return SupplyChainInformation(
            licenses=tuple(metadata.licenses),
            direct_dependency_count=sum(node.relation == "DIRECT" for node in graph.nodes),
            published_at=metadata.published_at,
        )


def _matches_coordinate(key: VersionKey, coordinate: DependencyCoordinate) -> bool:
    try:
        returned = key.coordinate()
    except ValueError:
        return False
    return returned.name == coordinate.name and Version(returned.version) == Version(
        coordinate.version
    )
