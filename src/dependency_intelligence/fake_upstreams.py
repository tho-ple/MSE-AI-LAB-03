"""Deterministic local substitutes for PyPI, OSV, and deps.dev."""

from __future__ import annotations

import asyncio
from collections import Counter
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request

app = FastAPI(title="Dependency Intelligence Lab Fixtures")
_calls: Counter[str] = Counter()
_lock = asyncio.Lock()


async def _record(service: str) -> None:
    async with _lock:
        _calls[service] += 1


async def _scenario(package_name: str, service: str) -> None:
    await _record(service)
    if package_name.startswith("slow-"):
        await asyncio.sleep(2)
    if package_name.startswith("missing-"):
        raise HTTPException(status_code=404, detail="package not found")
    if package_name.startswith(f"unavailable-{service}-"):
        raise HTTPException(status_code=503, detail="simulated service failure")


@app.get("/pypi/{package_name}/json")
async def pypi(package_name: str) -> dict[str, Any]:
    await _scenario(package_name, "pypi")
    if package_name.startswith("broken-pypi-"):
        return {"unexpected": True}
    latest = {"fastapi": "0.156.0", "jinja2": "3.1.6"}.get(package_name, "2.0.0")
    return {"info": {"name": package_name, "version": latest, "requires_python": ">=3.10"}}


@app.post("/v1/query")
async def osv(request: Request) -> dict[str, Any]:
    body = await request.json()
    package_name = str(body.get("package", {}).get("name", ""))
    version = str(body.get("version", ""))
    await _scenario(package_name, "osv")
    if package_name.startswith("broken-osv-"):
        return {"vulns": "invalid"}
    if package_name == "jinja2" and version == "2.4.1":
        return {
            "vulns": [
                {
                    "id": "GHSA-demo-0001",
                    "aliases": ["CVE-COURSE-0001"],
                    "summary": "Deterministic course vulnerability fixture",
                }
            ]
        }
    return {}


@app.get("/v3/systems/PYPI/packages/{package_name}/versions/{version}:dependencies")
async def deps_dev_graph(package_name: str, version: str) -> dict[str, Any]:
    await _scenario(package_name, "deps_graph")
    return {
        "nodes": [
            {
                "versionKey": {"system": "PYPI", "name": package_name, "version": version},
                "relation": "SELF",
            },
            {
                "versionKey": {"system": "PYPI", "name": "example-direct", "version": "1.0"},
                "relation": "DIRECT",
            },
        ],
        "error": "",
    }


@app.get("/v3/systems/PYPI/packages/{package_name}/versions/{version}")
async def deps_dev_metadata(package_name: str, version: str) -> dict[str, Any]:
    await _scenario(package_name, "deps")
    if package_name.startswith("broken-deps-"):
        return {"licenses": "invalid"}
    return {
        "versionKey": {"system": "PYPI", "name": package_name, "version": version},
        "publishedAt": "2024-09-17T19:18:10Z",
        "licenses": ["MIT"],
    }


@app.get("/_admin/calls")
async def calls() -> dict[str, int]:
    async with _lock:
        return dict(_calls)


@app.post("/_admin/reset")
async def reset() -> dict[str, str]:
    async with _lock:
        _calls.clear()
    return {"status": "reset"}


def main() -> None:
    uvicorn.run(
        "dependency_intelligence.fake_upstreams:app",
        host="127.0.0.1",
        port=8090,
    )
