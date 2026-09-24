"""Structural relationships and probe observations remain independent."""

from typing import Literal, Self

from pydantic import Field, model_validator

from agt_mcp.core.models import Identifier, Model, Provenance
from agt_mcp.correlation.models import CorrelationQuery, ObservedState
from agt_mcp.probes.models import ProbeEvidence


class TraceRelationship(Model):
    id: Identifier
    source: Identifier
    target: Identifier
    relationship: Identifier
    provenance: Provenance


class TraceHop(Model):
    reference: Identifier
    kind: Literal["resource", "component", "dependency"]
    depth: int = Field(ge=0)
    structural_status: Literal["RESOLVED", "UNRESOLVED"]
    runtime_observations: tuple[ObservedState, ...] = ()
    probe_status: tuple[Identifier, ...] = ()
    evidence_refs: tuple[Identifier, ...] = ()
    warnings: tuple[Identifier, ...] = ()
    provenance: tuple[Provenance, ...] = ()


class VirtualTrace(Model):
    id: Identifier
    environment_id: Identifier
    subject: Identifier
    correlation_id: Identifier
    trace_type: Literal["STRUCTURAL_TRACE", "PROBED_TRACE"] = "STRUCTURAL_TRACE"
    direction: Literal["outgoing", "incoming", "both"] = "outgoing"
    hops: tuple[TraceHop, ...] = Field(max_length=200)
    relationships: tuple[TraceRelationship, ...] = Field(max_length=6400)
    warnings: tuple[Identifier, ...] = ()
    probes: tuple[ProbeEvidence, ...] = Field(default=(), max_length=100)
    communication_verified: Literal[False] = False

    @model_validator(mode="after")
    def lineage(self) -> Self:
        refs = {h.reference for h in self.hops}
        if len(refs) != len(self.hops) or self.subject not in refs:
            raise ValueError("invalid trace origin")
        if any(
            r.source not in refs
            or r.target not in refs
            or r.provenance.environment_id != self.environment_id
            for r in self.relationships
        ):
            raise ValueError("invalid trace relationship")
        if any(p.environment_id != self.environment_id for h in self.hops for p in h.provenance):
            raise ValueError("invalid hop provenance")
        if any(
            p.result.target.resource_id not in refs
            or p.evidence.environment_id != self.environment_id
            for p in self.probes
        ):
            raise ValueError("invalid probe attachment")
        return self


class TraceOperation(Model):
    query: CorrelationQuery | None = None
    trace_id: Identifier | None = None
    troubleshooting_id: Identifier | None = None
    plan_id: Identifier | None = None
    direction: Literal["outgoing", "incoming", "both"] = "outgoing"
    max_depth: int | None = Field(default=None, ge=0, le=3)
