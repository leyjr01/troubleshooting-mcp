"""Deterministic bounded traversal, not a claim of a working network path."""

from typing import Literal

from agt_mcp.configuration.probes import TraceLimits
from agt_mcp.core.errors import ResourceNotFound
from agt_mcp.correlation.models import CorrelationResult
from agt_mcp.correlation.rules import identity
from agt_mcp.probes.models import ProbeEvidence
from agt_mcp.trace.models import TraceHop, TraceRelationship, VirtualTrace


class VirtualTraceBuilder:
    def __init__(self, limits: TraceLimits) -> None:
        self.limits = limits

    def build(
        self,
        result: CorrelationResult,
        direction: Literal["outgoing", "incoming", "both"] = "outgoing",
        max_depth: int | None = None,
    ) -> VirtualTrace:
        result = CorrelationResult.model_validate(result.model_dump())
        root = result.context.subject
        nodes = {n.id for n in result.topology_context.nodes}
        components = {c.id: c for c in result.component_context}
        if root not in nodes | components.keys():
            raise ResourceNotFound()
        edges = [
            TraceRelationship(
                id=e.id,
                source=e.source,
                target=e.target,
                relationship=e.relationship.value,
                provenance=e.source_of_information,
            )
            for e in result.topology_context.edges
        ]
        edges.extend(
            TraceRelationship(
                id=e.id,
                source=e.source,
                target=e.target,
                relationship=e.relation,
                provenance=e.provenance,
            )
            for e in result.semantic_links
        )
        for c in components.values():
            if c.provenance:
                for r in c.resources:
                    edges.append(
                        TraceRelationship(
                            id=identity("membership", r, c.id),
                            source=r,
                            target=c.id,
                            relationship="member_of",
                            provenance=c.provenance[0],
                        )
                    )
                    if root == c.id:
                        edges.append(
                            TraceRelationship(
                                id=identity("contains", c.id, r),
                                source=c.id,
                                target=r,
                                relationship="contains",
                                provenance=c.provenance[0],
                            )
                        )
        edges = sorted({e.id: e for e in edges}.values(), key=lambda e: (e.source, e.target, e.id))
        depths = {root: 0}
        selected: dict[str, TraceRelationship] = {}
        warnings = {w.code for w in result.warnings}
        if any(
            e.relation.startswith("unresolved_") and e.target_kind == "Service"
            for e in result.semantic_links
        ):
            warnings.add("routing_target_unresolved")
        depth_limit = min(
            self.limits.max_depth, max_depth if max_depth is not None else self.limits.max_depth
        )
        for depth in range(depth_limit + 1):
            for node in sorted(n for n, d in depths.items() if d == depth):
                adjacent = [
                    (e, e.target if e.source == node else e.source)
                    for e in edges
                    if (direction in {"outgoing", "both"} and e.source == node)
                    or (direction in {"incoming", "both"} and e.target == node)
                ]
                if depth == depth_limit:
                    if any(n not in depths for _, n in adjacent):
                        warnings.add("trace_depth_limit")
                    continue
                if len(adjacent) > self.limits.max_branches:
                    warnings.add("trace_branch_limit")
                for edge, target in adjacent[: self.limits.max_branches]:
                    if target not in depths and len(depths) >= min(
                        self.limits.max_nodes, self.limits.max_hops
                    ):
                        warnings.add("trace_node_limit")
                        continue
                    depths.setdefault(target, depth + 1)
                    selected[edge.id] = edge
        evidence = {e.id: e for s in result.evidence_sets for e in s.evidence}
        hops = []
        for node, depth in sorted(depths.items(), key=lambda item: (item[1], item[0])):
            refs = tuple(sorted(e.id for e in evidence.values() if e.resource_id == node))
            provenance = [evidence[r].source for r in refs]
            provenance.extend(
                e.provenance for e in selected.values() if node in {e.source, e.target}
            )
            if node in components:
                provenance.extend(components[node].provenance)
            unresolved = node not in nodes | components.keys()
            hops.append(
                TraceHop(
                    reference=node,
                    kind="component"
                    if node in components
                    else "dependency"
                    if unresolved
                    else "resource",
                    depth=depth,
                    structural_status="UNRESOLVED" if unresolved else "RESOLVED",
                    runtime_observations=tuple(
                        s for s in result.observed_states if s.evidence_id in refs
                    ),
                    evidence_refs=refs,
                    warnings=("target_unresolved",) if unresolved else (),
                    provenance=tuple({p.model_dump_json(): p for p in provenance}.values()),
                )
            )
        return VirtualTrace(
            id=identity(
                "trace", result.id, direction, str(depth_limit), self.limits.model_dump_json()
            ),
            environment_id=result.context.environment_id,
            subject=root,
            correlation_id=result.id,
            direction=direction,
            hops=tuple(hops),
            relationships=tuple(sorted(selected.values(), key=lambda e: e.id)),
            warnings=tuple(sorted(warnings)),
        )

    def attach(self, trace: VirtualTrace, evidence: tuple[ProbeEvidence, ...]) -> VirtualTrace:
        hops = tuple(
            h.model_copy(
                update={
                    "probe_status": tuple(
                        f"{p.result.probe_type.value}:{p.result.status.value}"
                        for p in evidence
                        if p.result.target.resource_id == h.reference
                    ),
                    "evidence_refs": (
                        *h.evidence_refs,
                        *(
                            p.evidence.id
                            for p in evidence
                            if p.result.target.resource_id == h.reference
                        ),
                    ),
                }
            )
            for h in trace.hops
        )
        executed = any(p.result.status.value in {"PASS", "FAILED", "CANCELLED"} for p in evidence)
        return VirtualTrace.model_validate(
            trace.model_copy(
                update={
                    "hops": hops,
                    "probes": evidence,
                    "trace_type": "PROBED_TRACE" if executed else "STRUCTURAL_TRACE",
                }
            ).model_dump()
        )
