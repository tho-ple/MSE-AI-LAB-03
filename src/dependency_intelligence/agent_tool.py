"""Supplied workspace-bounded adapter for agent harness registration."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .errors import ManifestValidationError
from .manifest import RequirementsLockParser
from .reporting import report_to_dict
from .service import DependencyScanner


class DependencyScanTool:
    name = "scan_project_dependencies"
    description = (
        "Scan exact Python dependencies from an allowed requirements.lock file and return "
        "version, vulnerability, supply-chain, cache, and source-failure data."
    )
    input_schema: dict[str, Any] = {
        "type": "object",
        "properties": {
            "manifest_path": {
                "type": "string",
                "default": "requirements.lock",
                "description": "Workspace-relative path to requirements.lock.",
            }
        },
        "additionalProperties": False,
    }

    def __init__(
        self,
        *,
        workspace_root: Path,
        scanner: DependencyScanner,
        scan_timeout_seconds: float = 30.0,
    ) -> None:
        self._workspace_root = workspace_root.resolve(strict=True)
        self._scanner = scanner
        self._timeout = scan_timeout_seconds
        self._parser = RequirementsLockParser()

    async def execute(self, manifest_path: str = "requirements.lock") -> dict[str, Any]:
        try:
            path = self._resolve_manifest(manifest_path)
            dependencies = self._parser.parse_file(path)
        except ManifestValidationError as error:
            return {
                "status": "invalid_manifest",
                "issues": [
                    {
                        "line_number": issue.line_number,
                        "line": issue.line,
                        "reason": issue.reason,
                    }
                    for issue in error.issues
                ],
            }
        except (OSError, ValueError) as error:
            return {"status": "invalid_manifest_path", "message": str(error)}
        try:
            async with asyncio.timeout(self._timeout):
                return report_to_dict(await self._scanner.scan(dependencies))
        except TimeoutError:
            return {
                "status": "failed",
                "code": "scan_timeout",
                "message": "The dependency scan exceeded its deadline.",
            }

    def _resolve_manifest(self, requested_path: str) -> Path:
        relative = Path(requested_path)
        if relative.is_absolute():
            raise ValueError("manifest path must be relative to the workspace")
        if any(part.startswith(".") for part in relative.parts):
            raise ValueError("hidden and parent path components are not allowed")
        if relative.name != "requirements.lock":
            raise ValueError("manifest filename is not allowed")
        target = (self._workspace_root / relative).resolve(strict=True)
        try:
            target.relative_to(self._workspace_root)
        except ValueError as error:
            raise ValueError("manifest escapes the allowed workspace") from error
        if not target.is_file():
            raise ValueError("manifest path is not a regular file")
        return target
