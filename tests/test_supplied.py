from __future__ import annotations

import httpx
import pytest

from dependency_intelligence.advisories import merge_advisories
from dependency_intelligence.domain import (
    DependencyCoordinate,
    FailureKind,
    ServiceName,
    Vulnerability,
)
from dependency_intelligence.errors import ManifestValidationError, SourceRequestError
from dependency_intelligence.http import JsonHttpClient
from dependency_intelligence.manifest import RequirementsLockParser


@pytest.mark.supplied
def test_coordinate_and_manifest_validation() -> None:
    coordinate = DependencyCoordinate("Demo_Package", "1.0")
    assert coordinate.name == "demo-package"
    with pytest.raises(ValueError):
        DependencyCoordinate("not a package", "1.0")
    with pytest.raises(ManifestValidationError):
        RequirementsLockParser().parse("demo>=1.0")
    with pytest.raises(ManifestValidationError):
        RequirementsLockParser().parse("demo[extra]==1.0")


@pytest.mark.supplied
def test_transitive_advisory_aliases_are_merged() -> None:
    merged = merge_advisories(
        [
            Vulnerability("GHSA-1", ("CVE-1",), "summary"),
            Vulnerability("PYSEC-1", ("CVE-1", "CVE-2"), None),
            Vulnerability("PYSEC-2", ("CVE-2",), None),
        ]
    )
    assert len(merged) == 1
    assert merged[0].identifier == "GHSA-1"
    assert set(merged[0].aliases) == {"CVE-1", "CVE-2", "PYSEC-1", "PYSEC-2"}


async def no_sleep(seconds: float) -> None:
    return None


@pytest.mark.supplied
async def test_http_policy_retries_and_maps_status() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await JsonHttpClient(client, sleep=no_sleep).request_json(
            ServiceName.PYPI, "GET", "https://fixture/value"
        )
    assert result == {"ok": True}
    assert calls == 2

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(404))
    ) as client:
        with pytest.raises(SourceRequestError) as captured:
            await JsonHttpClient(client, max_attempts=1).request_json(
                ServiceName.OSV, "GET", "https://fixture/value"
            )
    assert captured.value.failure.kind is FailureKind.NOT_FOUND
    assert not captured.value.failure.retryable


@pytest.mark.supplied
async def test_http_policy_enforces_streamed_size_limit() -> None:
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b"12345"))
    ) as client:
        with pytest.raises(SourceRequestError) as captured:
            await JsonHttpClient(client, max_response_bytes=4).request_json(
                ServiceName.PYPI, "GET", "https://fixture/value"
            )
    assert captured.value.failure.kind is FailureKind.INVALID_RESPONSE
