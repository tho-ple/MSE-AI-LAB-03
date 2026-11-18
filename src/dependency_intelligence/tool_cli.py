"""Command adapter exposing the bounded agent tool for classroom evidence."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

from .agent_tool import DependencyScanTool
from .bootstrap import Settings, build_scanner


async def _run(workspace: Path, manifest: str) -> dict[str, Any]:
    settings = Settings.from_environment()
    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        tool = DependencyScanTool(
            workspace_root=workspace,
            scanner=build_scanner(client, settings),
            scan_timeout_seconds=settings.scan_timeout_seconds,
        )
        return await tool.execute(manifest)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the dependency scanner agent tool")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--manifest", default="requirements.lock")
    arguments = parser.parse_args()
    try:
        result = asyncio.run(_run(arguments.workspace, arguments.manifest))
    except (OSError, ValueError) as error:
        result = {"status": "invalid_configuration", "message": str(error)}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result.get("status") in {"complete", "partial"} else 2)
