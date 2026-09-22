"""Directed graph without vendor-specific nodes."""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from agt_mcp.core.models import Confidence, Identifier, Model, Provenance, Resource


class Relationship(StrEnum):
    OWNS = "owns"
    HAS_ENDPOINTSLICE = "has_endpointslice"
    HAS_ENDPOINT = "has_endpoint"
    TARGETS = "targets"
    REFERENCES_CONFIGMAP = "references_configmap"
    # This enum value is a relationship label, not a credential.
    REFERENCES_SECRET = "references_secret"  # nosec B105
    MOUNTS = "mounts"
    BOUND_TO = "bound_to"
    USES_SERVICE_ACCOUNT = "uses_service_account"
    CALLS = "calls"
    ROUTES_TO = "routes_to"
    DEPENDS_ON = "depends_on"
    USES = "uses"
    CONTAINS = "contains"
    SELECTS = "selects"
    AUTHENTICATES_WITH = "authenticates_with"
    SECURED_BY = "secured_by"
    STORES_IN = "stores_in"
    READS_FROM = "reads_from"
    WRITES_TO = "writes_to"
    MANAGED_BY = "managed_by"


class Dependency(Model):
    id: Identifier
    source: Identifier
    target: Identifier
    relationship: Relationship
    source_of_information: Provenance
    confidence: Confidence
    metadata: dict[str, str] = Field(default_factory=dict)


class Topology(Model):
    environment_id: Identifier
    nodes: tuple[Resource, ...]
    edges: tuple[Dependency, ...] = ()

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        ids = {node.id for node in self.nodes}
        if len(ids) != len(self.nodes) or len({edge.id for edge in self.edges}) != len(self.edges):
            raise ValueError("duplicate graph identifiers")
        if any(node.environment_id != self.environment_id for node in self.nodes):
            raise ValueError("cross-environment node")
        for edge in self.edges:
            if edge.source not in ids or edge.target not in ids:
                raise ValueError("dangling dependency")
            if edge.source_of_information.environment_id != self.environment_id:
                raise ValueError("cross-environment edge")
        return self
