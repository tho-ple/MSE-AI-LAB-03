"""Task A: PyPI and OSV adapter tests (spec/task-A.md §4, cases A1-A10).

Every case runs against ``httpx.MockTransport``, so no network is used. The
``JsonHttpClient`` gets ``no_sleep`` so retry back-off costs no wall-clock time.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest

from dependency_intelligence.domain import (
    DependencyCoordinate,
    FailureKind,
    PackageMetadata,
    ServiceName,
    SourceFailure,
    Vulnerability,
)
from dependency_intelligence.errors import SourceRequestError
from dependency_intelligence.http import JsonHttpClient
from dependency_intelligence.sources import OSVClient, PyPIClient

pytestmark = pytest.mark.sources

BASE_URL = "https://fixture"
COORDINATE = DependencyCoordinate("demo", "1.0")

Handler = Callable[[httpx.Request], httpx.Response]


async def no_sleep(_: float) -> None:
    """Skip the retry back-off delay."""


async def fetch_metadata(handler: Handler) -> PackageMetadata:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = PyPIClient(JsonHttpClient(client, sleep=no_sleep), base_url=BASE_URL)
        return await adapter.fetch_metadata(COORDINATE)


async def fetch_vulnerabilities(handler: Handler) -> tuple[Vulnerability, ...]:
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = OSVClient(JsonHttpClient(client, sleep=no_sleep), base_url=BASE_URL)
        return await adapter.fetch_vulnerabilities(COORDINATE)


async def pypi_failure(handler: Handler) -> SourceFailure:
    with pytest.raises(SourceRequestError) as captured:
        await fetch_metadata(handler)
    return captured.value.failure


async def osv_failure(handler: Handler) -> SourceFailure:
    with pytest.raises(SourceRequestError) as captured:
        await fetch_vulnerabilities(handler)
    return captured.value.failure


def respond(status: int, payload: object = None) -> Handler:
    """Build a handler that always answers with the same status and JSON body."""
    return lambda request: httpx.Response(status, json=payload)


# --- PyPI -------------------------------------------------------------------


async def test_a1_pypi_happy_path_uses_get_on_the_package_json_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert str(request.url) == f"{BASE_URL}/pypi/demo/json"
        return httpx.Response(200, json={"info": {"version": "2.0", "requires_python": ">=3.10"}})

    assert await fetch_metadata(handler) == PackageMetadata("2.0", ">=3.10")


async def test_a2_pypi_missing_requires_python_is_none() -> None:
    metadata = await fetch_metadata(respond(200, {"info": {"version": "2.0"}}))

    assert metadata.latest_version == "2.0"
    assert metadata.requires_python is None


async def test_a3_pypi_unparseable_version_is_invalid_response() -> None:
    failure = await pypi_failure(respond(200, {"info": {"version": "banana"}}))

    assert failure.service is ServiceName.PYPI
    assert failure.kind is FailureKind.INVALID_RESPONSE
    assert failure.retryable is False


async def test_a4_pypi_body_without_info_is_invalid_response() -> None:
    failure = await pypi_failure(respond(200, {"unexpected": True}))

    assert failure.service is ServiceName.PYPI
    assert failure.kind is FailureKind.INVALID_RESPONSE
    assert failure.retryable is False


async def test_a5_pypi_404_is_not_found() -> None:
    failure = await pypi_failure(respond(404, {"message": "Not Found"}))

    assert failure.service is ServiceName.PYPI
    assert failure.kind is FailureKind.NOT_FOUND
    assert failure.retryable is False
    assert failure.status_code == 404


# --- OSV --------------------------------------------------------------------


async def test_a6_osv_posts_the_exact_coordinate() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == f"{BASE_URL}/v1/query"
        assert json.loads(request.content) == {
            "package": {"name": "demo", "ecosystem": "PyPI"},
            "version": "1.0",
        }
        return httpx.Response(200, json={"vulns": []})

    assert await fetch_vulnerabilities(handler) == ()


async def test_a7_osv_omitted_vulns_is_a_successful_empty_answer() -> None:
    assert await fetch_vulnerabilities(respond(200, {})) == ()


async def test_a8_osv_merges_transitive_aliases() -> None:
    payload = {
        "vulns": [
            {"id": "GHSA-1", "aliases": ["CVE-1"], "summary": "fixture"},
            {"id": "PYSEC-1", "aliases": ["CVE-1", "CVE-2"]},
            {"id": "PYSEC-2", "aliases": ["CVE-2"]},
        ]
    }

    advisories = await fetch_vulnerabilities(respond(200, payload))

    assert advisories == (
        Vulnerability(
            identifier="GHSA-1",
            aliases=("CVE-1", "CVE-2", "PYSEC-1", "PYSEC-2"),
            summary="fixture",
        ),
    )


async def test_a9_osv_vulns_of_wrong_type_is_invalid_response() -> None:
    failure = await osv_failure(respond(200, {"vulns": "invalid"}))

    assert failure.service is ServiceName.OSV
    assert failure.kind is FailureKind.INVALID_RESPONSE
    assert failure.retryable is False


async def test_a10_osv_503_twice_is_retryable_unavailable() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503)

    failure = await osv_failure(handler)

    assert calls == 2
    assert failure.service is ServiceName.OSV
    assert failure.kind is FailureKind.UNAVAILABLE
    assert failure.retryable is True
    assert failure.status_code == 503
