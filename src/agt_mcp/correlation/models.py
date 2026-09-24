"""Correlation references never substitute knowledge/history for runtime Evidence."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from agt_mcp.core.models import Confidence, Evidence, Identifier, Incident, Model, Provenance, Text
from agt_mcp.core.runtime import CategoryResult, RuntimeName
from agt_mcp.rag.contracts import KnowledgeResult
from agt_mcp.topology.models import Topology


class TimeWindow(Model):
    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.start >= self.end:
            raise ValueError("invalid time window")
        return self


class CorrelationQuery(Model):
    resource_id: Identifier | None = None
    gateway_id: Identifier | None = None
    component_id: Identifier | None = None
    namespace: RuntimeName | None = None
    symptom: Text | None = None
    time_window: TimeWindow | None = None
    topology_depth: int = Field(default=2, ge=0, le=3)
    include_knowledge: bool = True
    include_history: bool = True

    @model_validator(mode="after")
    def subject_required(self) -> Self:
        if not any((self.resource_id, self.gateway_id, self.component_id)):
            raise ValueError("correlation subject required")
        return self


class CorrelationContext(Model):
    environment_id: Identifier
    subject: Identifier
    request: CorrelationQuery
    time_window: TimeWindow
    correlated_at: AwareDatetime
    engine_version: Literal["1.0.0"] = "1.0.0"


class CorrelationOperation(Model):
    query: CorrelationQuery | None = None
    result_id: Identifier | None = None
    candidate_id: Identifier | None = None


class CorrelationWarning(Model):
    code: Identifier
    item_id: Identifier | None = None


class RelationType(StrEnum):
    TEMPORAL = "TEMPORAL"
    TOPOLOGICAL = "TOPOLOGICAL"
    RESOURCE = "RESOURCE"
    COMPONENT = "COMPONENT"
    EVENT = "EVENT"
    STATUS = "STATUS"
    KNOWLEDGE = "KNOWLEDGE"
    HISTORICAL_SIMILARITY = "HISTORICAL_SIMILARITY"
    CONFIGURATION_REFERENCE = "CONFIGURATION_REFERENCE"
    DEPENDENCY = "DEPENDENCY"


class SignalCode(StrEnum):
    PROBE_TLS_FAILED = "probe_tls_failed"
    PROBE_TLS_VERIFIED = "probe_tls_verified"
    PROBE_TCP_FAILED = "probe_tcp_failed"
    PROBE_TCP_CONNECTED = "probe_tcp_connected"
    CRASH_LOOP = "crash_loop"
    PVC_NOT_BOUND = "pvc_not_bound"
    PVC_BOUND = "pvc_bound"
    ENDPOINTS_EMPTY = "endpoints_empty"


class ObservedState(Model):
    evidence_id: Identifier
    state: Literal["unavailable", "ready", "unknown"]
    origin: Identifier
    signals: tuple[SignalCode, ...] = ()


class EvidenceAtom(Model):
    evidence: Evidence
    occurred_at: AwareDatetime | None
    kind: Literal["event", "status", "observation", "log", "metric", "trace", "probe"] = Field(
        default="observation"
    )
    state: Literal["unavailable", "ready", "unknown"] = "unknown"
    # Provider groups mirrored observations from the same resource/source conservatively.
    origin: Identifier
    signals: tuple[SignalCode, ...] = ()


class ComponentContext(Model):
    id: Identifier
    installation_id: Identifier
    type: Identifier
    resources: tuple[Identifier, ...]
    provenance: tuple[Provenance, ...]
    expected: bool | None = None
    external: bool = False
    presence: Identifier = "UNKNOWN"
    dependencies: tuple[Identifier, ...] = ()


class CorrelationLink(Model):
    id: Identifier
    source: Identifier
    target: Identifier
    relation: Identifier
    provenance: Provenance
    target_kind: Identifier | None = None


class CorrelationSnapshot(Model):
    environment_id: Identifier
    observed_at: AwareDatetime
    topology: Topology
    evidence: tuple[EvidenceAtom, ...]
    components: tuple[ComponentContext, ...] = ()
    links: tuple[CorrelationLink, ...] = ()
    warnings: tuple[CorrelationWarning, ...] = ()
    installation_id: Identifier | None = None
    gateway_type: Identifier | None = None
    version: Identifier | None = None
    coverage: tuple[CategoryResult, ...] = ()


class CorrelatedKnowledge(Model):
    id: Identifier
    reference: KnowledgeResult
    version_compatible: bool | None = None


class HistoricalSimilarity(Model):
    id: Identifier
    reference: KnowledgeResult
    incident: Incident | None = None
    relation: Literal["historical similarity"] = "historical similarity"
    similar_symptoms: Text
    similar_components: tuple[Identifier, ...] = ()
    similar_topology: Literal["unknown"] = "unknown"
    runtime_support: Literal[False] = False


class CorrelationCandidate(Model):
    id: Identifier
    subject: Identifier
    relation_type: RelationType
    source_items: tuple[Identifier, ...]
    supporting_evidence: tuple[Identifier, ...] = ()
    contradicting_evidence: tuple[Identifier, ...] = ()
    knowledge_refs: tuple[Identifier, ...] = ()
    historical_refs: tuple[Identifier, ...] = ()
    topology_refs: tuple[Identifier, ...] = ()
    topology_distance: int | None = None
    temporal_distance_seconds: float | None = None
    confidence: Confidence
    status: Literal["CANDIDATE", "SUPPORTED", "CONTRADICTED", "INCONCLUSIVE"]
    mechanism: Identifier
    reasons: tuple[Text, ...]
    provenance: tuple[Provenance, ...]


class TimelineItem(Model):
    evidence_id: Identifier
    timestamp: AwareDatetime | None
    resource_id: Identifier
    components: tuple[Identifier, ...]
    event_type: Identifier
    observation: Text
    provenance: Provenance
    relevant: bool


class EvidenceSet(Model):
    id: Identifier
    subject: Identifier
    environment_id: Identifier
    time_window: TimeWindow
    evidence: tuple[Evidence, ...]
    resources: tuple[Identifier, ...]
    components: tuple[Identifier, ...]
    provenance: tuple[Provenance, ...]
    knowledge_refs: tuple[Identifier, ...] = ()
    historical_refs: tuple[Identifier, ...] = ()


class CorrelationResult(Model):
    id: Identifier
    context: CorrelationContext
    status: Literal["COMPLETE", "PARTIAL"]
    evidence_sets: tuple[EvidenceSet, ...]
    candidates: tuple[CorrelationCandidate, ...]
    timeline: tuple[TimelineItem, ...]
    knowledge: tuple[CorrelatedKnowledge, ...]
    historical_matches: tuple[HistoricalSimilarity, ...]
    topology_context: Topology
    semantic_links: tuple[CorrelationLink, ...] = ()
    warnings: tuple[CorrelationWarning, ...]
    provenance: tuple[Provenance, ...]
    observed_states: tuple[ObservedState, ...] = ()
    component_context: tuple[ComponentContext, ...] = ()
    installation_id: Identifier | None = None
    gateway_type: Identifier | None = None
    version: Identifier | None = None
    coverage: tuple[CategoryResult, ...] = ()

    @model_validator(mode="after")
    def lineage(self) -> Self:
        env = self.context.environment_id
        nodes = {n.id for n in self.topology_context.nodes}
        evidence = {e.id: e for s in self.evidence_sets for e in s.evidence}
        if any(s.evidence_id not in evidence for s in self.observed_states):
            raise ValueError("unresolved observed state")
        if any(c.installation_id != self.installation_id for c in self.component_context):
            raise ValueError("cross-installation component context")
        if any(
            not set(c.resources) <= nodes or any(p.environment_id != env for p in c.provenance)
            for c in self.component_context
        ):
            raise ValueError("invalid semantic context scope")
        if any(e.provenance.environment_id != env for e in self.semantic_links):
            raise ValueError("invalid semantic link scope")
        known = {k.id for k in self.knowledge}
        history = {h.id for h in self.historical_matches}
        links = {e.id for e in self.topology_context.edges} | {e.id for e in self.semantic_links}
        references: tuple[CorrelatedKnowledge | HistoricalSimilarity, ...] = (
            *self.knowledge,
            *self.historical_matches,
        )
        for reference in references:
            chunk = reference.reference.chunk
            if (
                chunk.environment_id not in {env, "global"}
                or chunk.source.environment_id != chunk.environment_id
            ):
                raise ValueError("invalid enrichment scope")
        if self.topology_context.environment_id != env:
            raise ValueError("cross-environment correlation topology")
        for group in self.evidence_sets:
            if group.environment_id != env or not set(group.resources) <= nodes:
                raise ValueError("invalid evidence set scope")
            if not set(group.knowledge_refs) <= known or not set(group.historical_refs) <= history:
                raise ValueError("unresolved enrichment reference")
        for item in evidence.values():
            if (
                item.environment_id != env
                or item.source.environment_id != env
                or item.resource_id not in nodes
            ):
                raise ValueError("invalid runtime evidence scope")
        for candidate in self.candidates:
            if (
                not set((*candidate.supporting_evidence, *candidate.contradicting_evidence))
                <= evidence.keys()
            ):
                raise ValueError("unresolved runtime evidence")
            if (
                not set(candidate.knowledge_refs) <= known
                or not set(candidate.historical_refs) <= history
                or not set(candidate.topology_refs) <= links
            ):
                raise ValueError("unresolved candidate reference")
            if (
                candidate.confidence.supporting_evidence != candidate.supporting_evidence
                or candidate.confidence.contradicting_evidence != candidate.contradicting_evidence
            ):
                raise ValueError("inconsistent confidence lineage")
        if any(t.evidence_id not in evidence for t in self.timeline):
            raise ValueError("unresolved timeline evidence")
        return self
