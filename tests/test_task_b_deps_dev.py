from __future__ import annotations

import asyncio
from typing import Any, cast
from urllib.parse import urlsplit

import httpx
import pytest

from dependency_intelligence.domain import (
    DependencyCoordinate,
    FailureKind,
    ServiceName,
    SupplyChainInformation,
)
from dependency_intelligence.errors import SourceRequestError
from dependency_intelligence.http import JsonHttpClient
from dependency_intelligence.sources.deps_dev import DepsDevClient

pytestmark = pytest.mark.sources


def _metadata(
    *,
    name: str = "demo",
    version: str = "1.0",
    licenses: list[str] | str | None = None,
    published_at: str | None = "2024-01-01T00:00:00Z",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "versionKey": {"system": "PYPI", "name": name, "version": version},
    }
    if licenses is not None:
        result["licenses"] = licenses
    if published_at is not None:
        result["publishedAt"] = published_at
    return result


def _graph(
    *,
    name: str = "demo",
    version: str = "1.0",
    extra_nodes: list[dict[str, Any]] | None = None,
    error: str = "",
) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "versionKey": {"system": "PYPI", "name": name, "version": version},
                "relation": "SELF",
            },
            {
                "versionKey": {"system": "PYPI", "name": "child", "version": "2.0"},
                "relation": "DIRECT",
            },
            *(extra_nodes or []),
        ],
        "error": error,
    }


async def _fetch_responses(
    metadata: Any,
    graph: Any,
    *,
    coordinate: DependencyCoordinate | None = None,
    metadata_status: int = 200,
    graph_status: int = 200,
) -> tuple[SupplyChainInformation, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith(":dependencies"):
            return httpx.Response(graph_status, json=graph)
        return httpx.Response(metadata_status, json=metadata)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        source = DepsDevClient(JsonHttpClient(client), base_url="https://fixture/")
        result = await source.fetch_supply_chain(coordinate or DependencyCoordinate("demo", "1.0"))
    return result, requests


async def test_happy_path_maps_values_and_requests_both_endpoints() -> None:
    result, requests = await _fetch_responses(_metadata(licenses=["MIT"]), _graph())

    assert result == SupplyChainInformation(("MIT",), 1, "2024-01-01T00:00:00Z")
    assert {urlsplit(str(request.url)).path for request in requests} == {
        "/v3/systems/PYPI/packages/demo/versions/1.0",
        "/v3/systems/PYPI/packages/demo/versions/1.0:dependencies",
    }


async def test_missing_optional_metadata_fields_are_empty() -> None:
    result, _ = await _fetch_responses(_metadata(published_at=None), _graph())

    assert result.licenses == ()
    assert result.published_at is None


@pytest.mark.parametrize(
    "graph",
    [
        {},
        {"nodes": []},
        _graph(
            extra_nodes=[
                {
                    "versionKey": {"system": "PYPI", "name": "other", "version": "1.0"},
                    "relation": "SELF",
                }
            ]
        ),
        {
            "nodes": [
                {
                    "versionKey": {"system": "PYPI", "name": "child", "version": "1.0"},
                    "relation": "DIRECT",
                }
            ]
        },
        _graph(error="incomplete"),
        _graph(
            extra_nodes=[
                {
                    "versionKey": {"system": "PYPI", "name": "child", "version": "2.0"},
                    "relation": "DIRECT",
                    "errors": ["missing"],
                }
            ]
        ),
    ],
)
async def test_invalid_graphs_raise_invalid_response(graph: dict[str, Any]) -> None:
    with pytest.raises(SourceRequestError) as error:
        await _fetch_responses(_metadata(licenses=[]), graph)

    assert error.value.failure.service is ServiceName.DEPS_DEV
    assert error.value.failure.kind is FailureKind.INVALID_RESPONSE
    assert not error.value.failure.retryable


async def test_metadata_for_a_different_package_is_rejected() -> None:
    with pytest.raises(SourceRequestError) as error:
        await _fetch_responses(_metadata(name="other"), _graph())

    assert error.value.failure.kind is FailureKind.INVALID_RESPONSE


async def test_graph_for_a_different_version_is_rejected() -> None:
    with pytest.raises(SourceRequestError) as error:
        await _fetch_responses(_metadata(), _graph(version="2.0"))

    assert error.value.failure.kind is FailureKind.INVALID_RESPONSE


async def test_equivalent_version_spellings_match() -> None:
    result, _ = await _fetch_responses(_metadata(version="1.0.0"), _graph(version="1.0.0"))

    assert result.direct_dependency_count == 1


async def test_local_version_is_percent_encoded_in_both_paths() -> None:
    coordinate = DependencyCoordinate("demo", "1.0+local")
    _, requests = await _fetch_responses(
        _metadata(version="1.0+local"),
        _graph(version="1.0+local"),
        coordinate=coordinate,
    )

    assert {request.url.raw_path.decode() for request in requests} == {
        "/v3/systems/PYPI/packages/demo/versions/1.0%2Blocal",
        "/v3/systems/PYPI/packages/demo/versions/1.0%2Blocal:dependencies",
    }


class FailingMetadataHttp:
    def __init__(self) -> None:
        self.graph_started = asyncio.Event()
        self.graph_cancelled = asyncio.Event()

    async def request_json(
        self,
        service: ServiceName,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> Any:
        if url.endswith(":dependencies"):
            self.graph_started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.graph_cancelled.set()
                raise
        await self.graph_started.wait()
        raise SourceRequestError(
            service, FailureKind.UNAVAILABLE, "service unavailable", retryable=True
        )


async def test_endpoint_failure_cancels_the_sibling_and_is_unwrapped() -> None:
    http = FailingMetadataHttp()
    source = DepsDevClient(cast(JsonHttpClient, http), base_url="https://fixture")

    with pytest.raises(SourceRequestError) as error:
        await source.fetch_supply_chain(DependencyCoordinate("demo", "1.0"))

    assert error.value.failure.service is ServiceName.DEPS_DEV
    assert error.value.failure.kind is FailureKind.UNAVAILABLE
    assert http.graph_cancelled.is_set()


async def test_two_not_found_responses_produce_one_source_error() -> None:
    with pytest.raises(SourceRequestError) as error:
        await _fetch_responses({}, {}, metadata_status=404, graph_status=404)

    assert error.value.failure.service is ServiceName.DEPS_DEV
    assert error.value.failure.kind is FailureKind.NOT_FOUND


async def test_invalid_license_shape_is_rejected() -> None:
    with pytest.raises(SourceRequestError) as error:
        await _fetch_responses(_metadata(licenses="invalid"), _graph())

    assert error.value.failure.kind is FailureKind.INVALID_RESPONSE
