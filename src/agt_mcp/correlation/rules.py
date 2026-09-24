"""Small deterministic relation rules; no free-text diagnosis or command evaluation."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from agt_mcp.core.models import Confidence, ConfidenceLevel, Provenance
from agt_mcp.correlation.models import (
    ComponentContext,
    CorrelationCandidate,
    CorrelationContext,
    CorrelationLink,
    EvidenceAtom,
    RelationType,
)


def identity(prefix: str, *values: str) -> str:
    return prefix + "-" + hashlib.sha256("\0".join(values).encode()).hexdigest()[:40]


@dataclass(frozen=True)
class RuleContext:
    context: CorrelationContext
    atoms: tuple[EvidenceAtom, ...]
    distances: dict[str, int]
    components: tuple[ComponentContext, ...]
    links: tuple[CorrelationLink, ...]
    proximity: int


def candidate(
    data: RuleContext,
    relation: RelationType,
    mechanism: str,
    support: tuple[EvidenceAtom, ...] = (),
    contradictions: tuple[EvidenceAtom, ...] = (),
    links: tuple[CorrelationLink, ...] = (),
    reason: str = "observed structural relation",
    temporal_distance: float | None = None,
) -> CorrelationCandidate:
    refs = tuple(sorted({a.evidence.id for a in support}))
    contra = tuple(sorted({a.evidence.id for a in contradictions}))
    topology = tuple(sorted(e.id for e in links))
    distance = max((data.distances[a.evidence.resource_id] for a in support), default=0)
    independent = {a.evidence.source.source_id for a in support}
    high = (
        len(independent) >= 2
        and len({a.origin for a in support}) >= 2
        and distance <= 1
        and all(a.evidence.confidence.level == ConfidenceLevel.HIGH for a in support)
    )
    level = (
        ConfidenceLevel.LOW
        if contra or distance > 1
        else ConfidenceLevel.HIGH
        if high
        else ConfidenceLevel.MEDIUM
    )
    confidence = Confidence(
        level=level,
        rationale=reason,
        source_reliability="Provider provenance; mirrored facts are not independent sources",
        temporal_relevance="Known supporting timestamps fall within the requested window",
        topological_relevance=f"bounded topology distance {distance}",
        historical_similarity="Never contributes runtime support or causal confidence",
        supporting_evidence=refs,
        contradicting_evidence=contra,
    )
    provenance: dict[str, Provenance] = {}
    for source in [
        *(a.evidence.source for a in (*support, *contradictions)),
        *(e.provenance for e in links),
    ]:
        provenance[source.model_dump_json()] = source
    return CorrelationCandidate(
        id=identity(
            "candidate", data.context.subject, relation, mechanism, *refs, *contra, *topology
        ),
        subject=data.context.subject,
        relation_type=relation,
        source_items=refs or topology,
        supporting_evidence=refs,
        contradicting_evidence=contra,
        topology_refs=topology,
        topology_distance=distance,
        temporal_distance_seconds=temporal_distance,
        confidence=confidence,
        status="INCONCLUSIVE" if contra else "SUPPORTED" if refs or topology else "CANDIDATE",
        mechanism=mechanism,
        reasons=(reason,),
        provenance=tuple(provenance[k] for k in sorted(provenance)),
    )


def resource_event_rule(data: RuleContext) -> tuple[CorrelationCandidate, ...]:
    result = []
    for atom in data.atoms:
        if data.distances[atom.evidence.resource_id] == 0:
            result.append(
                candidate(
                    data,
                    RelationType.RESOURCE,
                    "same-resource",
                    (atom,),
                    reason="same resource or selected component member",
                )
            )
        if atom.kind == "event":
            result.append(
                candidate(
                    data,
                    RelationType.EVENT,
                    "related-event",
                    (atom,),
                    reason="scoped runtime event observed",
                )
            )
    return tuple(result)


def temporal_rule(data: RuleContext) -> tuple[CorrelationCandidate, ...]:
    anchors = [a for a in data.atoms if data.distances[a.evidence.resource_id] == 0]
    result = []
    seen = set()
    for atom in data.atoms:
        for anchor in anchors:
            pair = tuple(sorted((atom.evidence.id, anchor.evidence.id)))
            if (
                pair in seen
                or atom.origin == anchor.origin
                or atom.occurred_at is None
                or anchor.occurred_at is None
            ):
                continue
            seen.add(pair)
            seconds = abs((atom.occurred_at - anchor.occurred_at).total_seconds())
            if seconds <= data.proximity:
                result.append(
                    candidate(
                        data,
                        RelationType.TEMPORAL,
                        "temporal-proximity",
                        (atom, anchor),
                        reason=f"observations within {seconds:g} seconds; no causal ordering",
                        temporal_distance=seconds,
                    )
                )
    return tuple(result)


def topology_rule(data: RuleContext) -> tuple[CorrelationCandidate, ...]:
    result = []
    for atom in data.atoms:
        if data.distances[atom.evidence.resource_id] > 0:
            links = tuple(
                e for e in data.links if atom.evidence.resource_id in {e.source, e.target}
            )
            if links:
                result.append(
                    candidate(
                        data,
                        RelationType.TOPOLOGICAL,
                        "topology-neighbor",
                        (atom,),
                        links=links,
                        reason="resource connected in observed bounded topology",
                    )
                )
    for link in data.links:
        configuration = link.relation in {
            "references_secret",
            "references_configmap",
            "configured_by",
            "describes_connection_to",
        }
        result.append(
            candidate(
                data,
                RelationType.CONFIGURATION_REFERENCE if configuration else RelationType.DEPENDENCY,
                "observed-reference",
                links=(link,),
                reason="observed reference; connectivity not tested",
            )
        )
    return tuple(result)


def component_rule(data: RuleContext) -> tuple[CorrelationCandidate, ...]:
    result = []
    for component in data.components:
        support = tuple(a for a in data.atoms if a.evidence.resource_id in component.resources)
        if support:
            c = candidate(
                data,
                RelationType.COMPONENT,
                "component-membership",
                support,
                reason="runtime observations belong to the same semantic component",
            )
            result.append(
                c.model_copy(
                    update={
                        "id": identity("candidate", c.id, component.id),
                        "source_items": (*c.source_items, component.id),
                        "provenance": (*c.provenance, *component.provenance),
                    }
                )
            )
    return tuple(result)


def contradiction_rule(data: RuleContext) -> tuple[CorrelationCandidate, ...]:
    result = []
    for atom in data.atoms:
        if atom.state != "unavailable":
            continue
        resource = atom.evidence.resource_id
        # Only same-resource observations or a Service's explicit endpoint chain may contradict.
        endpoint_targets = {
            e.target
            for e in data.links
            if e.source == resource and e.relation in {"has_endpoint", "has_endpointslice"}
        }
        contradictions = tuple(
            a
            for a in data.atoms
            if a.state == "ready" and a.evidence.resource_id in {resource, *endpoint_targets}
        )
        result.append(
            candidate(
                data,
                RelationType.STATUS,
                "availability-contradiction",
                (atom,),
                contradictions,
                reason="unavailable observation; preserve conflicting ready observations",
            )
        )
    return tuple(result)


CorrelationRule = Callable[[RuleContext], tuple[CorrelationCandidate, ...]]
RULES: tuple[CorrelationRule, ...] = (
    resource_event_rule,
    temporal_rule,
    topology_rule,
    component_rule,
    contradiction_rule,
)
