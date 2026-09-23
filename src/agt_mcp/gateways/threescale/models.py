"""Product semantic models; transport and Kubernetes SDK independent."""

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field, JsonValue

from agt_mcp.core.models import Confidence, Evidence, Identifier, Model, Provenance
from agt_mcp.core.runtime import RuntimeName, RuntimeSnapshot


class ComponentType(StrEnum):
    APIMANAGER = "APIMANAGER"
    APICAST_STAGING = "APICAST_STAGING"
    APICAST_PRODUCTION = "APICAST_PRODUCTION"
    SYSTEM_APP = "SYSTEM_APP"
    SYSTEM_SIDEKIQ = "SYSTEM_SIDEKIQ"
    BACKEND_LISTENER = "BACKEND_LISTENER"
    BACKEND_WORKER = "BACKEND_WORKER"
    BACKEND_CRON = "BACKEND_CRON"
    ZYNC = "ZYNC"
    ZYNC_QUE = "ZYNC_QUE"
    SYSTEM_DATABASE = "SYSTEM_DATABASE"
    ZYNC_DATABASE = "ZYNC_DATABASE"
    BACKEND_REDIS_STORAGE = "BACKEND_REDIS_STORAGE"
    BACKEND_REDIS_QUEUES = "BACKEND_REDIS_QUEUES"
    SYSTEM_REDIS = "SYSTEM_REDIS"
    SYSTEM_MEMCACHE = "SYSTEM_MEMCACHE"
    UNKNOWN = "UNKNOWN_THREESCALE_COMPONENT"


class Presence(StrEnum):
    PRESENT = "PRESENT"
    ABSENT_EXPECTED = "ABSENT_EXPECTED"
    ABSENT_OPTIONAL = "ABSENT_OPTIONAL"
    EXTERNAL = "EXTERNAL"
    DISABLED = "DISABLED"
    UNKNOWN = "UNKNOWN"


class DetectionEvidence(Model):
    id: Identifier
    resource_id: Identifier
    signal: Identifier
    observation: str
    provenance: Provenance
    confidence: Confidence


class SemanticRelation(StrEnum):
    MANAGES = "manages"
    COMPONENT_OF = "component_of"
    CONFIGURED_BY = "configured_by"
    DEPENDS_ON = "depends_on"
    EXPOSES = "exposes"
    ROUTES_TO = "routes_to"
    USES_STORAGE = "uses_storage"
    USES_QUEUE = "uses_queue"
    DESCRIBES_CONNECTION_TO = "describes_connection_to"


class SemanticEdge(Model):
    id: Identifier
    source: Identifier
    target: Identifier
    relationship: SemanticRelation
    mechanism: Identifier
    provenance: Provenance
    confidence: Confidence


class Component(Model):
    id: Identifier
    type: ComponentType
    role: Identifier
    runtime_resources: tuple[Identifier, ...] = ()
    status: Presence
    runtime_status: Literal["OBSERVED", "DEGRADED", "UNKNOWN"] = "UNKNOWN"
    expected: bool | None = None
    external: bool = False
    evidence: tuple[DetectionEvidence, ...]
    confidence: Confidence
    dependencies: tuple[Identifier, ...] = ()


class ExternalDependency(Model):
    id: Identifier
    type: ComponentType
    endpoint_status: Literal["unresolved"] = "unresolved"
    secret_references: tuple[Identifier, ...] = ()
    evidence: tuple[DetectionEvidence, ...]
    mapping_reference: None = None


class SemanticWarning(Model):
    code: Literal[
        "expected_component_not_observed",
        "ambiguous_classification",
        "external_dependency_unresolved",
        "version_unknown",
        "unsupported_version_profile",
        "runtime_resource_forbidden",
        "partial_topology",
        "configuration_conflict",
    ]
    resource_id: Identifier | None = None


class Installation(Model):
    id: Identifier
    environment_id: Identifier
    namespace: Identifier
    version: str
    version_profile: str
    configuration_summary: dict[str, JsonValue]
    operator_managed: bool
    operator_observation: Literal["observed", "not_observed", "access_unavailable"]
    apimanager: Identifier | None
    observed_at: AwareDatetime
    components: tuple[Component, ...]
    dependencies: tuple[ExternalDependency, ...]
    relationships: tuple[SemanticEdge, ...]
    runtime_resources: tuple[Identifier, ...]
    runtime_evidence: tuple[Evidence, ...]
    evidence: tuple[DetectionEvidence, ...]
    warnings: tuple[SemanticWarning, ...]
    partial: bool


class GatewayQuery(Model):
    gateway_id: Identifier | None = None
    namespace: RuntimeName | None = None
    gateway_type: Literal["threescale"] | None = None
    component_id: Identifier | None = None
    depth: int = Field(default=2, ge=1, le=3)
    limit: int = Field(default=50, ge=1, le=200)


class GatewayDiscovery(Model):
    installations: tuple[Installation, ...]
    snapshot: RuntimeSnapshot
