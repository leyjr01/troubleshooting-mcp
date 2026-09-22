"""Canonical runtime discovery port. No SDK models or raw resource payloads."""

from abc import ABC, abstractmethod
from typing import Annotated, Literal

from pydantic import AwareDatetime, Field, StringConstraints

from agt_mcp.core.execution import ExecutionContext
from agt_mcp.core.models import Evidence, Identifier, Model, ResourceReference
from agt_mcp.topology.models import Relationship, Topology

RuntimeName = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]([a-z0-9.-]{0,125}[a-z0-9])?$")]


class RuntimeQuery(Model):
    namespace: RuntimeName | None = None
    kind: Identifier | None = None
    name: RuntimeName | None = None
    api_version: Identifier | None = None
    depth: int = Field(default=1, ge=1, le=3)
    limit: int = Field(default=50, ge=1, le=200)
    relationship: Relationship | None = None
    direction: Literal["both", "dependencies", "dependents"] = "both"
    since: AwareDatetime | None = None


class DiscoveryWarning(Model):
    code: Literal[
        "missing_target",
        "ambiguous_selector",
        "no_endpoints",
        "forbidden_resource",
        "unsupported_api",
        "truncated_discovery",
        "unavailable",
        "invalid_resource",
    ]
    namespace: Identifier | None = None
    kind: Identifier | None = None
    resource_id: Identifier | None = None


class UnresolvedRelationship(Model):
    source: Identifier
    target: ResourceReference
    relationship: Relationship
    resolution: Literal["not_found", "not_observed", "forbidden", "ambiguous"]
    mechanism: Identifier


class CategoryResult(Model):
    namespace: Identifier | None
    kind: Identifier
    status: Literal["completed", "forbidden", "unsupported", "truncated", "unavailable"]
    count: int = 0


class RuntimeHealth(Model):
    api_accessible: bool
    authorized_namespaces: tuple[Identifier, ...]
    partial: bool


class RuntimeEvents(Model):
    evidence: tuple[Evidence, ...]
    limit: int
    truncated: bool


class RuntimeSnapshot(Model):
    environment_id: Identifier
    cluster: Identifier
    provider: Literal["kubernetes", "openshift"]
    observed_at: AwareDatetime
    namespaces: tuple[Identifier, ...]
    capabilities: tuple[Identifier, ...]
    topology: Topology
    evidence: tuple[Evidence, ...] = ()
    warnings: tuple[DiscoveryWarning, ...] = ()
    unresolved: tuple[UnresolvedRelationship, ...] = ()
    categories: tuple[CategoryResult, ...] = ()

    def connection_health(self) -> RuntimeHealth:
        return RuntimeHealth(
            api_accessible=bool(self.capabilities),
            authorized_namespaces=tuple(
                sorted(
                    {
                        c.namespace
                        for c in self.categories
                        if c.namespace and c.status == "completed"
                    }
                )
            ),
            partial=any(c.status != "completed" for c in self.categories),
        )


class RuntimeAdapter(ABC):
    @abstractmethod
    async def discover(self, context: ExecutionContext, query: RuntimeQuery) -> RuntimeSnapshot: ...

    @abstractmethod
    async def inspect(self, context: ExecutionContext, query: RuntimeQuery) -> RuntimeSnapshot: ...

    @abstractmethod
    async def events(self, context: ExecutionContext, query: RuntimeQuery) -> RuntimeEvents: ...

    @abstractmethod
    async def close(self) -> None: ...
