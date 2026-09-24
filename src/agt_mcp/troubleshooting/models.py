"""Hypotheses, evidence requirements and bounded inspection plans."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from agt_mcp.core.models import Confidence, Identifier, Model, Provenance, ResourceKind, Text
from agt_mcp.correlation.models import CorrelationQuery, CorrelationResult, TimeWindow


class EvaluationStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    SUPPORTED = "SUPPORTED"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED_BY_MISSING_EVIDENCE"


class SafetyClass(StrEnum):
    READ_ONLY_INSPECTION = "READ_ONLY_INSPECTION"
    PASSIVE_PROBE = "PASSIVE_PROBE"
    ACTIVE_PROBE = "ACTIVE_PROBE"
    WRITE_OPERATION = "WRITE_OPERATION"


class RuleKind(StrEnum):
    PROBE_TLS = "probe_tls"
    PROBE_TCP = "probe_tcp"
    AVAILABILITY = "availability"
    ENDPOINT = "endpoint"
    ROUTING = "routing"
    CRASH_LOOP = "crash_loop"
    PVC = "pvc"
    EXTERNAL = "external"
    REFERENCE = "reference"


class EvidenceRequirement(Model):
    id: Identifier
    description: Text
    purpose: Literal["support_or_reject", "strengthen"] = "support_or_reject"
    required_capability: Identifier
    safety_class: SafetyClass = SafetyClass.READ_ONLY_INSPECTION
    optional: bool = False


class HypothesisDefinition(Model):
    id: Identifier
    name: Text
    description: Text
    scope: Literal["resource", "component"] = "resource"
    applicable_resource_types: tuple[ResourceKind, ...] = ()
    applicable_component_types: tuple[Identifier, ...] = ()
    rule: RuleKind
    required_evidence: tuple[EvidenceRequirement, ...]
    optional_evidence: tuple[EvidenceRequirement, ...] = ()
    gateway_constraints: tuple[Identifier, ...] = ()
    version_constraints: tuple[Identifier, ...] = ()
    priority: int = Field(default=50, ge=0, le=100)


class ReportedSymptom(Model):
    text: Text
    origin: Literal["user_reported", "runtime_observed", "unspecified"]
    evidence_ids: tuple[Identifier, ...] = ()


class TroubleshootingContext(Model):
    environment_id: Identifier
    subject: Identifier
    symptom: ReportedSymptom
    time_window: TimeWindow
    correlation_id: Identifier
    engine_version: Literal["1.0.0"] = "1.0.0"


class HypothesisEvaluation(Model):
    hypothesis_id: Identifier
    status: EvaluationStatus
    supporting_evidence: tuple[Identifier, ...] = ()
    contradicting_evidence: tuple[Identifier, ...] = ()
    missing_evidence: tuple[EvidenceRequirement, ...] = ()
    topology_refs: tuple[Identifier, ...] = ()
    confidence: Confidence
    reason_codes: tuple[Identifier, ...]
    provenance: tuple[Provenance, ...]


class HypothesisInstance(Model):
    id: Identifier
    definition_id: Identifier
    subject: Identifier
    component_id: Identifier | None = None
    resources: tuple[Identifier, ...]
    statement: Text
    generated_because: tuple[Identifier, ...]
    version_compatible: bool | None = None
    evaluation: HypothesisEvaluation
    knowledge_refs: tuple[Identifier, ...] = ()
    historical_refs: tuple[Identifier, ...] = ()


class RootCauseCandidate(Model):
    id: Identifier
    hypothesis_id: Identifier
    subject: Identifier
    summary: Text
    supporting_evidence: tuple[Identifier, ...] = Field(min_length=1)
    contradicting_evidence: tuple[Identifier, ...] = ()
    missing_evidence: tuple[EvidenceRequirement, ...] = ()
    confidence: Confidence
    status: Literal["SUPPORTED_CANDIDATE"] = "SUPPORTED_CANDIDATE"
    scope: Literal["observed_condition"] = "observed_condition"
    provenance: tuple[Provenance, ...]
    related_candidate_ids: tuple[Identifier, ...] = ()


class TroubleshootingStep(Model):
    id: Identifier
    description: Text
    purpose: Text
    required_capability: Identifier
    target: Identifier
    expected_evidence: tuple[Identifier, ...]
    hypothesis_ids: tuple[Identifier, ...]
    safety_class: SafetyClass
    status: Literal["PLANNED", "CAPABILITY_UNAVAILABLE"]
    executable: Literal[False] = False


class TroubleshootingPlan(Model):
    steps: tuple[TroubleshootingStep, ...]
    executed: Literal[False] = False


class TroubleshootingResult(Model):
    id: Identifier
    context: TroubleshootingContext
    correlation_result: CorrelationResult
    hypotheses: tuple[HypothesisInstance, ...]
    root_cause_candidates: tuple[RootCauseCandidate, ...]
    troubleshooting_plan: TroubleshootingPlan
    warnings: tuple[Identifier, ...]
    missing_capabilities: tuple[Identifier, ...]
    provenance: tuple[Provenance, ...]
    status: Literal["COMPLETE", "PARTIAL", "LIMITED"]

    @model_validator(mode="after")
    def lineage(self) -> Self:
        correlation = self.correlation_result
        env = self.context.environment_id
        if (
            env != correlation.context.environment_id
            or self.context.correlation_id != correlation.id
        ):
            raise ValueError("invalid correlation scope")
        if (
            self.context.subject != correlation.context.subject
            or self.context.time_window != correlation.context.time_window
        ):
            raise ValueError("invalid troubleshooting context")
        evidence = {e.id for group in correlation.evidence_sets for e in group.evidence}
        if not set(self.context.symptom.evidence_ids) <= evidence or (
            self.context.symptom.origin == "user_reported" and self.context.symptom.evidence_ids
        ):
            raise ValueError("invalid symptom attribution")
        nodes = {n.id for n in correlation.topology_context.nodes}
        components = {c.id for c in correlation.component_context}
        links = {e.id for e in correlation.topology_context.edges} | {
            e.id for e in correlation.semantic_links
        }
        hypotheses = {h.id: h for h in self.hypotheses}
        if len(hypotheses) != len(self.hypotheses):
            raise ValueError("duplicate hypothesis")
        for h in self.hypotheses:
            evaluation = h.evaluation
            if h.subject not in nodes | components or not set(h.resources) <= nodes:
                raise ValueError("invalid hypothesis scope")
            if (
                evaluation.hypothesis_id != h.id
                or not set((*evaluation.supporting_evidence, *evaluation.contradicting_evidence))
                <= evidence
            ):
                raise ValueError("invalid hypothesis evidence")
            if not set(evaluation.topology_refs) <= links or any(
                p.environment_id != env for p in evaluation.provenance
            ):
                raise ValueError("invalid hypothesis provenance")
            if (
                evaluation.confidence.supporting_evidence != evaluation.supporting_evidence
                or evaluation.confidence.contradicting_evidence != evaluation.contradicting_evidence
            ):
                raise ValueError("invalid confidence lineage")
            if evaluation.status == EvaluationStatus.SUPPORTED and (
                not evaluation.supporting_evidence
                or evaluation.contradicting_evidence
                or evaluation.missing_evidence
            ):
                raise ValueError("unsupported promotion")
        candidates = {c.id for c in self.root_cause_candidates}
        for candidate in self.root_cause_candidates:
            hypothesis = hypotheses.get(candidate.hypothesis_id)
            if hypothesis is None or hypothesis.evaluation.status != EvaluationStatus.SUPPORTED:
                raise ValueError("candidate requires supported hypothesis")
            if (
                candidate.supporting_evidence != hypothesis.evaluation.supporting_evidence
                or candidate.confidence != hypothesis.evaluation.confidence
                or not set(candidate.related_candidate_ids) <= candidates
            ):
                raise ValueError("invalid candidate lineage")
            if (
                candidate.subject != hypothesis.subject
                or candidate.contradicting_evidence
                or candidate.missing_evidence
                or candidate.provenance != hypothesis.evaluation.provenance
            ):
                raise ValueError("invalid supported candidate")
        for step in self.troubleshooting_plan.steps:
            if not set(step.hypothesis_ids) <= hypotheses.keys() or step.safety_class not in {
                SafetyClass.READ_ONLY_INSPECTION,
                SafetyClass.PASSIVE_PROBE,
            }:
                raise ValueError("invalid plan")
        return self


class TroubleshootingOperation(Model):
    query: CorrelationQuery | None = None
    result_id: Identifier | None = None
    hypothesis_id: Identifier | None = None
