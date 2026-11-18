"""Strict external schemas supplied so adapter tickets focus on translation."""

from __future__ import annotations

from typing import Any, Literal

from packaging.version import Version
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .domain import DependencyCoordinate, FailureKind, ServiceName
from .errors import SourceRequestError


class _ResponseModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore", populate_by_name=True)


class PyPIInfo(_ResponseModel):
    version: str = Field(min_length=1)
    requires_python: str | None = None

    @field_validator("version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        Version(value)
        return value


class PyPIResponse(_ResponseModel):
    info: PyPIInfo


class OSVEntry(_ResponseModel):
    id: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    summary: str | None = None

    @field_validator("aliases")
    @classmethod
    def nonempty_aliases(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("aliases must not be empty")
        return values


class OSVResponse(_ResponseModel):
    vulns: list[OSVEntry] = Field(default_factory=list)


class VersionKey(_ResponseModel):
    system: Literal["PYPI"]
    name: str
    version: str

    def coordinate(self) -> DependencyCoordinate:
        return DependencyCoordinate(self.name, self.version)


class DepsMetadata(_ResponseModel):
    version_key: VersionKey = Field(alias="versionKey")
    licenses: list[str] = Field(default_factory=list)
    published_at: str | None = Field(default=None, alias="publishedAt")


class DependencyNode(_ResponseModel):
    version_key: VersionKey = Field(alias="versionKey")
    relation: Literal["SELF", "DIRECT", "INDIRECT"]
    errors: list[str] = Field(default_factory=list)


class DepsGraph(_ResponseModel):
    nodes: list[DependencyNode] = Field(min_length=1)
    error: str = ""

    @model_validator(mode="after")
    def complete_graph(self) -> DepsGraph:
        if self.nodes[0].relation != "SELF":
            raise ValueError("dependency graph must start with its root")
        if any(node.relation == "SELF" for node in self.nodes[1:]):
            raise ValueError("dependency graph must have one root")
        if self.error or any(node.errors for node in self.nodes):
            raise ValueError("dependency graph is incomplete")
        return self


def parse_response[T: BaseModel](model: type[T], data: Any, service: ServiceName) -> T:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        raise SourceRequestError(
            service,
            FailureKind.INVALID_RESPONSE,
            "response did not match the expected source schema",
            retryable=False,
        ) from error
