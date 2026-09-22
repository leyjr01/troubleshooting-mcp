"""Canonical entities. Opaque IDs are scoped by environment, never by vendor."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StringConstraints

Identifier = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")]
Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=16384)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class InformationType(StrEnum):
    FACT = "fact"
    OBSERVATION = "observation"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    FINDING = "finding"
    RECOMMENDATION = "recommendation"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Confidence(Model):
    level: ConfidenceLevel
    rationale: Text
    source_reliability: Text
    temporal_relevance: Text
    topological_relevance: Text
    historical_similarity: Text
    supporting_evidence: tuple[Identifier, ...] = ()
    contradicting_evidence: tuple[Identifier, ...] = ()


class Environment(Model):
    id: Identifier
    name: Text
    type: Literal["development", "test", "staging", "production"]
    cluster: Identifier
    namespace: Identifier | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ResourceKind(StrEnum):
    DEPLOYMENT = "deployment"
    REPLICASET = "replicaset"
    STATEFULSET = "statefulset"
    DAEMONSET = "daemonset"
    ENDPOINTSLICE = "endpointslice"
    ENDPOINT = "endpoint"
    CONFIGMAP = "configmap"
    PVC = "persistentvolumeclaim"
    PV = "persistentvolume"
    SERVICE_ACCOUNT = "serviceaccount"
    EVENT = "event"
    INGRESS = "ingress"
    NETWORK_POLICY = "networkpolicy"
    NAMESPACE = "namespace"
    CRD = "customresourcedefinition"
    CUSTOM_RESOURCE = "customresource"
    # This enum value is a resource kind, not a credential.
    SECRET_REFERENCE = "secret_reference"  # nosec B105
    GATEWAY = "gateway"
    API = "api"
    PRODUCT = "product"
    BACKEND = "backend"
    ROUTE = "route"
    SERVICE = "service"
    POD = "pod"
    DATABASE = "database"
    CERTIFICATE = "certificate"
    # Resource kind, never a credential value.
    SECRET = "secret"  # nosec B105
    EXTERNAL_SERVICE = "external_service"
    QUEUE = "queue"
    DNS = "dns"
    NETWORK = "network"


class ResourceReference(Model):
    environment_id: Identifier
    cluster: Identifier
    namespace: Identifier | None = None
    api_version: Identifier
    kind: Identifier
    name: Identifier
    uid: Identifier | None = None


class Resource(Model):
    id: Identifier
    environment_id: Identifier
    kind: ResourceKind
    name: Text
    namespace: Identifier | None = None
    provider: Identifier
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    status: Text = "unknown"
    metadata: dict[str, str] = Field(default_factory=dict)
    reference: ResourceReference | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)


class API(Resource):
    kind: Literal[ResourceKind.API] = ResourceKind.API
    version: Text
    gateway_id: Identifier


class Gateway(Resource):
    kind: Literal[ResourceKind.GATEWAY] = ResourceKind.GATEWAY
    version: Text
    endpoint_reference: Identifier


class Provenance(Model):
    source_id: Identifier
    environment_id: Identifier
    retrieved_at: AwareDatetime
    source_reference: Text
    content_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class Evidence(Model):
    id: Identifier
    environment_id: Identifier
    timestamp: AwareDatetime
    source: Provenance
    type: Literal[InformationType.FACT, InformationType.OBSERVATION]
    resource_id: Identifier
    observation: Text
    raw_reference: Text
    confidence: Confidence
    metadata: dict[str, str] = Field(default_factory=dict)


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Finding(Model):
    id: Identifier
    environment_id: Identifier
    title: Text
    description: Text
    severity: Severity
    evidence_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    confidence: Confidence
    status: Literal["supported", "inconclusive", "retracted"]


class Hypothesis(Model):
    id: Identifier
    environment_id: Identifier
    statement: Text
    supporting_evidence: tuple[Identifier, ...] = ()
    contradicting_evidence: tuple[Identifier, ...] = ()
    confidence: Confidence
    status: Literal["candidate", "supported", "rejected", "inconclusive"]


class Recommendation(Model):
    id: Identifier
    environment_id: Identifier
    description: Text
    finding_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    evidence_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    requires_human_approval: Literal[True] = True
    executable: Literal[False] = False


class Incident(Model):
    id: Identifier
    timestamp: AwareDatetime
    environment_id: Identifier
    services: tuple[Identifier, ...] = ()
    components: tuple[Identifier, ...] = ()
    symptom: Text
    error: Text | None = None
    root_cause_finding_id: Identifier | None = None
    remediation_recommendation_ids: tuple[Identifier, ...] = ()
    evidence_ids: tuple[Identifier, ...] = ()
    tags: tuple[Identifier, ...] = ()
    source: Provenance
