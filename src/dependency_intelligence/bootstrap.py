"""Composition root for live or deterministic source base URLs."""

from __future__ import annotations

import math
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
import uvicorn
from fastapi import FastAPI

from .api import create_app
from .cache import AsyncTTLCache
from .domain import PackageAssessment
from .http import JsonHttpClient
from .service import DependencyScanner
from .sources import DepsDevClient, OSVClient, PyPIClient


@dataclass(frozen=True, slots=True)
class Settings:
    pypi_base_url: str = "https://pypi.org"
    osv_base_url: str = "https://api.osv.dev"
    deps_dev_base_url: str = "https://api.deps.dev"
    request_timeout_seconds: float = 10.0
    scan_timeout_seconds: float = 30.0
    max_concurrent_packages: int = 8
    max_http_connections: int = 24
    cache_ttl_seconds: float = 900.0
    cache_max_entries: int = 2_000

    def __post_init__(self) -> None:
        positive_numbers = (
            self.request_timeout_seconds,
            self.scan_timeout_seconds,
            self.max_concurrent_packages,
            self.max_http_connections,
            self.cache_ttl_seconds,
            self.cache_max_entries,
        )
        if any(not math.isfinite(float(value)) or value <= 0 for value in positive_numbers):
            raise ValueError("timeouts, limits, and cache settings must be finite and positive")

    @classmethod
    def from_environment(cls) -> Settings:
        defaults = cls()
        return cls(
            pypi_base_url=os.getenv("PYPI_BASE_URL", defaults.pypi_base_url),
            osv_base_url=os.getenv("OSV_BASE_URL", defaults.osv_base_url),
            deps_dev_base_url=os.getenv("DEPS_DEV_BASE_URL", defaults.deps_dev_base_url),
            request_timeout_seconds=float(
                os.getenv("REQUEST_TIMEOUT_SECONDS", defaults.request_timeout_seconds)
            ),
            scan_timeout_seconds=float(
                os.getenv("SCAN_TIMEOUT_SECONDS", defaults.scan_timeout_seconds)
            ),
            max_concurrent_packages=int(
                os.getenv("MAX_CONCURRENT_PACKAGES", defaults.max_concurrent_packages)
            ),
            max_http_connections=int(
                os.getenv("MAX_HTTP_CONNECTIONS", defaults.max_http_connections)
            ),
            cache_ttl_seconds=float(os.getenv("CACHE_TTL_SECONDS", defaults.cache_ttl_seconds)),
            cache_max_entries=int(os.getenv("CACHE_MAX_ENTRIES", defaults.cache_max_entries)),
        )


def build_scanner(client: httpx.AsyncClient, settings: Settings) -> DependencyScanner:
    http = JsonHttpClient(client)
    cache: AsyncTTLCache[str, PackageAssessment] = AsyncTTLCache(
        ttl_seconds=settings.cache_ttl_seconds,
        max_entries=settings.cache_max_entries,
    )
    return DependencyScanner(
        metadata_source=PyPIClient(http, base_url=settings.pypi_base_url),
        vulnerability_source=OSVClient(http, base_url=settings.osv_base_url),
        supply_chain_source=DepsDevClient(http, base_url=settings.deps_dev_base_url),
        cache=cache,
        max_concurrent_packages=settings.max_concurrent_packages,
    )


def build_app() -> FastAPI:
    settings = Settings.from_environment()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        limits = httpx.Limits(
            max_connections=settings.max_http_connections,
            max_keepalive_connections=settings.max_http_connections,
        )
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.request_timeout_seconds),
            limits=limits,
            headers={"User-Agent": "dependency-intelligence-lab/1.0"},
        ) as client:
            app.state.scanner = build_scanner(client, settings)
            yield

    return create_app(scan_timeout_seconds=settings.scan_timeout_seconds, lifespan=lifespan)


def main() -> None:
    uvicorn.run(
        "dependency_intelligence.bootstrap:build_app",
        factory=True,
        host="127.0.0.1",
        port=8000,
    )
