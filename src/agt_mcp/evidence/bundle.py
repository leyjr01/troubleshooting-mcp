"""Validated in-memory evidence bundle; no filesystem exporter in Sprint 0."""

from typing import Literal, Self

from pydantic import AwareDatetime, model_validator

from agt_mcp.core.models import (
    Confidence,
    Environment,
    Evidence,
    Finding,
    Hypothesis,
    Identifier,
    Incident,
    Model,
    Recommendation,
    Text,
)
from agt_mcp.correlation.models import CorrelationResult
from agt_mcp.topology.models import Topology
from agt_mcp.troubleshooting.models import TroubleshootingResult


class TimelineEntry(Model):
    timestamp: AwareDatetime
    description: Text
    evidence_ids: tuple[Identifier, ...] = ()


class IncidentBundle(Model):
    schema_version: Literal["1.0.0"] = "1.0.0"
    environment: Environment
    incident: Incident
    topology: Topology
    evidence: tuple[Evidence, ...] = ()
    hypotheses: tuple[Hypothesis, ...] = ()
    findings: tuple[Finding, ...] = ()
    recommendations: tuple[Recommendation, ...] = ()
    timeline: tuple[TimelineEntry, ...] = ()
    correlations: tuple[CorrelationResult, ...] = ()
    troubleshooting: tuple[TroubleshootingResult, ...] = ()

    @model_validator(mode="after")
    def validate_lineage(self) -> Self:
        environment = self.environment.id
        if any(r.context.environment_id != environment for r in self.troubleshooting):
            raise ValueError("cross-environment troubleshooting")
        if any(result.context.environment_id != environment for result in self.correlations):
            raise ValueError("cross-environment correlation")
        items: tuple[Evidence | Hypothesis | Finding | Recommendation, ...] = (
            *self.evidence,
            *self.hypotheses,
            *self.findings,
            *self.recommendations,
        )
        if (
            self.incident.environment_id != environment
            or self.topology.environment_id != environment
        ):
            raise ValueError("cross-environment bundle")
        if self.incident.source.environment_id != environment:
            raise ValueError("cross-environment incident source")
        if any(item.environment_id != environment for item in items):
            raise ValueError("cross-environment record")
        groups = (self.evidence, self.hypotheses, self.findings, self.recommendations)
        for group in groups:
            if len({item.id for item in group}) != len(group):
                raise ValueError("duplicate record identifiers")
        evidence_ids = {item.id for item in self.evidence}
        finding_ids = {item.id for item in self.findings}
        recommendation_ids = {item.id for item in self.recommendations}
        node_ids = {node.id for node in self.topology.nodes}

        def require(refs: tuple[str, ...], known: set[str]) -> None:
            if not set(refs) <= known:
                raise ValueError("unresolved reference")

        def confidence_refs(confidence: Confidence) -> None:
            require(confidence.supporting_evidence, evidence_ids)
            require(confidence.contradicting_evidence, evidence_ids)

        for item in self.evidence:
            if item.source.environment_id != environment or item.resource_id not in node_ids:
                raise ValueError("invalid evidence scope")
            confidence_refs(item.confidence)
        for edge in self.topology.edges:
            confidence_refs(edge.confidence)
        for finding in self.findings:
            require(finding.evidence_ids, evidence_ids)
            confidence_refs(finding.confidence)
        for hypothesis in self.hypotheses:
            require(hypothesis.supporting_evidence, evidence_ids)
            require(hypothesis.contradicting_evidence, evidence_ids)
            confidence_refs(hypothesis.confidence)
            if hypothesis.status == "supported" and not hypothesis.supporting_evidence:
                raise ValueError("supported hypothesis requires evidence")
            if hypothesis.status == "rejected" and not hypothesis.contradicting_evidence:
                raise ValueError("rejected hypothesis requires evidence")
        for recommendation in self.recommendations:
            require(recommendation.finding_ids, finding_ids)
            require(recommendation.evidence_ids, evidence_ids)
        require(self.incident.evidence_ids, evidence_ids)
        require(self.incident.services + self.incident.components, node_ids)
        require(self.incident.remediation_recommendation_ids, recommendation_ids)
        if self.incident.root_cause_finding_id is not None:
            require((self.incident.root_cause_finding_id,), finding_ids)
        for entry in self.timeline:
            require(entry.evidence_ids, evidence_ids)
        return self
