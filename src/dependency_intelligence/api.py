"""Supplied FastAPI transport; orchestration remains in DependencyScanner."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .domain import DependencyCoordinate, ScanStatus
from .reporting import report_to_dict
from .service import DependencyScanner


class DependencyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=1, max_length=200)]
    version: Annotated[str, Field(min_length=1, max_length=100)]
    ecosystem: str = "PyPI"


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dependencies: Annotated[list[DependencyInput], Field(min_length=1, max_length=200)]

    @model_validator(mode="after")
    def reject_duplicate_names(self) -> ScanRequest:
        coordinates = [
            DependencyCoordinate(item.name, item.version, item.ecosystem)
            for item in self.dependencies
        ]
        names = [coordinate.name for coordinate in coordinates]
        if len(names) != len(set(names)):
            raise ValueError("dependencies must have unique normalized package names")
        return self


def create_app(
    *,
    scanner: DependencyScanner | None = None,
    scan_timeout_seconds: float = 30.0,
    lifespan: Any | None = None,
) -> FastAPI:
    app = FastAPI(title="Dependency Intelligence API", version="1.0.0", lifespan=lifespan)
    if scanner is not None:
        app.state.scanner = scanner

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/v1/scans")
    async def scan(request_body: ScanRequest, request: Request) -> JSONResponse:
        coordinates = tuple(
            DependencyCoordinate(item.name, item.version, item.ecosystem)
            for item in request_body.dependencies
        )
        scanner_service: DependencyScanner = request.app.state.scanner
        try:
            async with asyncio.timeout(scan_timeout_seconds):
                report = await scanner_service.scan(coordinates)
        except TimeoutError:
            return JSONResponse(
                status_code=504,
                content={
                    "status": "failed",
                    "code": "scan_timeout",
                    "message": "The dependency scan exceeded its deadline.",
                },
            )
        status_code = 503 if report.status is ScanStatus.FAILED else 200
        return JSONResponse(status_code=status_code, content=report_to_dict(report))

    return app
