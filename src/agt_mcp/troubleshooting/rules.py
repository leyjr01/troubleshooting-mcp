"""Small factual rules over typed observations; never interpret free-form document text."""

from collections.abc import Callable
from dataclasses import dataclass

from agt_mcp.correlation.models import CorrelationResult, SignalCode
from agt_mcp.troubleshooting.models import HypothesisInstance, RuleKind


@dataclass(frozen=True)
class Assessment:
    support: tuple[str, ...] = ()
    contradiction: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()
    topology: tuple[str, ...] = ()
    decisive: bool = False


class EvidenceView:
    def __init__(self, result: CorrelationResult) -> None:
        self.result = result
        self.evidence = {e.id: e for s in result.evidence_sets for e in s.evidence}
        self.fresh = {t.evidence_id for t in result.timeline if t.relevant}
        self.states = {
            s.evidence_id: s for s in result.observed_states if s.evidence_id in self.fresh
        }
        self.nodes = {n.id: n for n in result.topology_context.nodes}
        self.structure_current = "snapshot_outside_window" not in {w.code for w in result.warnings}

    def select(
        self, resources: tuple[str, ...], state: str | None = None, signal: SignalCode | None = None
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                i
                for i, s in self.states.items()
                if self.evidence[i].resource_id in resources
                and (state is None or s.state == state)
                and (signal is None or signal in s.signals)
            )
        )

    def complete(self, kind: str, resources: tuple[str, ...]) -> bool:
        namespaces = {self.nodes[r].namespace for r in resources if r in self.nodes}
        coverage = [c for c in self.result.coverage if c.kind == kind and c.namespace in namespaces]
        return (
            self.structure_current
            and not {"topology_limit_reached", "evidence_truncated"}
            & {w.code for w in self.result.warnings}
            and bool(coverage)
            and all(c.status == "completed" for c in coverage)
        )


def availability(view: EvidenceView, h: HypothesisInstance) -> Assessment:
    support, contra = view.select(h.resources, "unavailable"), view.select(h.resources, "ready")
    return Assessment(support, contra, () if support or contra else ("runtime_state",))


def endpoint(view: EvidenceView, h: HypothesisInstance) -> Assessment:
    edges = (
        tuple(
            e
            for e in view.result.topology_context.edges
            if e.source in h.resources
            and e.relationship.value in {"has_endpointslice", "has_endpoint"}
        )
        if view.structure_current
        else ()
    )
    targets = tuple(e.target for e in edges)
    contra = view.select(targets, "ready")
    support = tuple(
        sorted(
            set(view.select(targets, "unavailable"))
            | set(view.select(targets, signal=SignalCode.ENDPOINTS_EMPTY))
        )
    )
    missing = []
    if not edges:
        missing.append("service_topology")
    observed = {view.evidence[i].resource_id for i in (*support, *contra)}
    if (
        not targets
        or not set(targets) <= observed
        or not view.complete("EndpointSlice", h.resources)
    ):
        missing.append("endpoint_readiness")
    # A positive ready observation rejects the universal 'no ready endpoints' claim.
    return Assessment(
        support, contra, tuple(missing), tuple(e.id for e in edges), bool(support and not missing)
    )


def routing(view: EvidenceView, h: HypothesisInstance) -> Assessment:
    unresolved = (
        tuple(
            e
            for e in view.result.semantic_links
            if e.source in h.resources
            and e.relation == "unresolved_not_found"
            and e.target_kind == "Service"
        )
        if view.structure_current
        else ()
    )
    resolved = (
        tuple(
            e
            for e in view.result.topology_context.edges
            if e.source in h.resources and e.relationship.value == "routes_to"
        )
        if view.structure_current
        else ()
    )
    direct = view.select(h.resources)
    complete = view.complete("Service", h.resources)
    support = direct if unresolved and complete else ()
    contra = direct if resolved else ()
    return Assessment(
        support,
        contra,
        () if support or contra else ("target_resolution",),
        (*tuple(e.id for e in unresolved), *tuple(e.id for e in resolved)),
        bool(support),
    )


def crash_loop(view: EvidenceView, h: HypothesisInstance) -> Assessment:
    support = view.select(h.resources, signal=SignalCode.CRASH_LOOP)
    contra = view.select(h.resources, "ready")
    return Assessment(support, contra, () if support or contra else ("container_lifecycle",))


def pvc(view: EvidenceView, h: HypothesisInstance) -> Assessment:
    support = view.select(h.resources, signal=SignalCode.PVC_NOT_BOUND)
    contra = view.select(h.resources, signal=SignalCode.PVC_BOUND)
    return Assessment(support, contra, () if support or contra else ("volume_binding",))


def external(view: EvidenceView, h: HypothesisInstance) -> Assessment:
    # Degradation may motivate this hypothesis; it does not demonstrate dependency failure.
    support = view.select(h.resources, "unavailable")
    contra = view.select(h.resources, "ready")
    links = tuple(
        e.id
        for e in view.result.semantic_links
        if e.source in {*h.resources, h.component_id}
        and e.relation
        in {"uses_storage", "uses_queue", "depends_on", "describes_connection_to", "configured_by"}
    )
    return Assessment(support, contra, ("dependency_connectivity",), links)


def reference(view: EvidenceView, h: HypothesisInstance) -> Assessment:
    links = (
        tuple(
            e.id
            for e in view.result.semantic_links
            if e.source in h.resources and e.relation.startswith("unresolved_")
        )
        if view.structure_current
        else ()
    )
    return Assessment(
        view.select(h.resources) if links else (), missing=("dependency_reference",), topology=links
    )


Rule = Callable[[EvidenceView, HypothesisInstance], Assessment]


def probe_tls(view: EvidenceView, h: HypothesisInstance) -> Assessment:
    support = view.select(h.resources, signal=SignalCode.PROBE_TLS_FAILED)
    contra = view.select(h.resources, signal=SignalCode.PROBE_TLS_VERIFIED)
    return Assessment(support, contra, () if support or contra else ("tls_verification",))


def probe_tcp(view: EvidenceView, h: HypothesisInstance) -> Assessment:
    support = view.select(h.resources, signal=SignalCode.PROBE_TCP_FAILED)
    contra = view.select(h.resources, signal=SignalCode.PROBE_TCP_CONNECTED)
    return Assessment(support, contra, () if support or contra else ("tcp_connectivity",))


RULES: dict[RuleKind, Rule] = {
    RuleKind.PROBE_TLS: probe_tls,
    RuleKind.PROBE_TCP: probe_tcp,
    RuleKind.AVAILABILITY: availability,
    RuleKind.ENDPOINT: endpoint,
    RuleKind.ROUTING: routing,
    RuleKind.CRASH_LOOP: crash_loop,
    RuleKind.PVC: pvc,
    RuleKind.EXTERNAL: external,
    RuleKind.REFERENCE: reference,
}
