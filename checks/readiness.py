"""Offline readiness check run when students receive the lab in class."""

from __future__ import annotations

import sys
from pathlib import Path

import fastapi
import httpx
import pydantic

from dependency_intelligence.domain import DependencyCoordinate
from dependency_intelligence.manifest import RequirementsLockParser


def main() -> None:
    if sys.version_info < (3, 12):  # noqa: UP036 - readiness should fail explicitly.
        raise SystemExit("FAIL: Python 3.12 or newer is required")
    root = Path(__file__).resolve().parents[1]
    dependencies = RequirementsLockParser().parse_file(
        root / "sample-project" / "requirements.lock"
    )
    assert dependencies[0] == DependencyCoordinate("fastapi", "0.115.0")
    print(f"PASS: Python {sys.version.split()[0]}")
    print(
        "PASS: imports "
        f"fastapi={fastapi.__version__} httpx={httpx.__version__} pydantic={pydantic.__version__}"
    )
    print(f"PASS: parsed {len(dependencies)} exact sample dependencies")
    print("READY: the implementation starter may still have expected failing tests")


if __name__ == "__main__":
    main()
