"""Supplied bounded HTTP and retry policy shared by all source adapters."""

from __future__ import annotations

import asyncio
import json as json_module
import math
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from .domain import FailureKind, ServiceName
from .errors import SourceRequestError

Sleep = Callable[[float], Awaitable[None]]


class JsonHttpClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        max_attempts: int = 2,
        backoff_seconds: float = 0.05,
        max_response_bytes: int = 1_000_000,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        if max_attempts <= 0 or max_response_bytes <= 0 or backoff_seconds < 0:
            raise ValueError("HTTP bounds are invalid")
        self._client = client
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._max_response_bytes = max_response_bytes
        self._sleep = sleep

    async def request_json(
        self,
        service: ServiceName,
        method: str,
        url: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> Any:
        for attempt in range(1, self._max_attempts + 1):
            try:
                async with self._client.stream(
                    method, url, json=json, headers={"Accept-Encoding": "identity"}
                ) as response:
                    if (
                        response.status_code in {429, 500, 502, 503, 504}
                        and attempt < self._max_attempts
                    ):
                        retry_delay = self._retry_delay(response, attempt)
                    else:
                        self._raise_for_status(service, response)
                        return await self._read_json(service, response)
                await self._sleep(retry_delay)
            except httpx.TimeoutException as error:
                if attempt < self._max_attempts:
                    await self._sleep(self._backoff_seconds * attempt)
                    continue
                raise SourceRequestError(
                    service, FailureKind.TIMEOUT, "request timed out", retryable=True
                ) from error
            except httpx.RequestError as error:
                if attempt < self._max_attempts:
                    await self._sleep(self._backoff_seconds * attempt)
                    continue
                raise SourceRequestError(
                    service,
                    FailureKind.UNAVAILABLE,
                    "service could not be reached",
                    retryable=True,
                ) from error
        raise AssertionError("retry loop exhausted")

    async def _read_json(self, service: ServiceName, response: httpx.Response) -> Any:
        if response.headers.get("content-encoding", "identity").lower() != "identity":
            raise SourceRequestError(
                service,
                FailureKind.INVALID_RESPONSE,
                "compressed responses are unsupported",
                retryable=False,
            )
        content = bytearray()
        async for chunk in response.aiter_bytes():
            if len(content) + len(chunk) > self._max_response_bytes:
                raise SourceRequestError(
                    service,
                    FailureKind.INVALID_RESPONSE,
                    "response exceeded the configured size limit",
                    retryable=False,
                )
            content.extend(chunk)
        try:
            return json_module.loads(content)
        except (ValueError, UnicodeDecodeError) as error:
            raise SourceRequestError(
                service,
                FailureKind.INVALID_RESPONSE,
                "response was not valid JSON",
                retryable=False,
            ) from error

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                delay = float(retry_after)
                if math.isfinite(delay) and delay >= 0:
                    return min(delay, 2.0)
            except ValueError:
                pass
        return self._backoff_seconds * attempt

    @staticmethod
    def _raise_for_status(service: ServiceName, response: httpx.Response) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        if status == 404:
            kind, retryable = FailureKind.NOT_FOUND, False
        elif status == 429:
            kind, retryable = FailureKind.RATE_LIMITED, True
        elif status >= 500:
            kind, retryable = FailureKind.UNAVAILABLE, True
        else:
            kind, retryable = FailureKind.INVALID_RESPONSE, False
        raise SourceRequestError(
            service,
            kind,
            f"service returned HTTP {status}",
            retryable=retryable,
            status_code=status,
        )
