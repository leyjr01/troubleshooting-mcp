"""Instantiate only catalog definitions applicable to the bounded canonical context."""

from agt_mcp.core.models import Confidence
from agt_mcp.correlation.models import CorrelationResult
from agt_mcp.correlation.rules import identity
from agt_mcp.troubleshooting.catalog import HypothesisCatalog
from agt_mcp.troubleshooting.models import (
    EvaluationStatus,
    HypothesisEvaluation,
    HypothesisInstance,
    RuleKind,
)


def initial_confidence() -> Confidence:
    return Confidence(
        level="low",
        rationale="Testable explanation awaiting runtime evaluation",
        source_reliability="Only scoped canonical evidence is eligible",
        temporal_relevance="Only relevant correlation observations are eligible",
        topological_relevance="Bounded observed topology",
        historical_similarity="References cannot support or confirm a current cause",
    )


class HypothesisGenerator:
    def __init__(self, catalog: HypothesisCatalog) -> None:
        self.catalog = catalog

    def generate(
        self, result: CorrelationResult, max_components: int
    ) -> tuple[HypothesisInstance, ...]:
        generated = []
        components = sorted(result.component_context, key=lambda c: c.id)[:max_components]
        disabled = {
            r
            for c in components
            if c.expected is False or c.presence in {"DISABLED", "ABSENT_OPTIONAL"}
            for r in c.resources
        }
        for definition in self.catalog.definitions:
            if (
                definition.gateway_constraints
                and result.gateway_type not in definition.gateway_constraints
            ):
                continue
            version = (
                ".".join(result.version.split(".")[:2])
                if result.version and result.version != "UNKNOWN"
                else None
            )
            compatible = (
                (version in definition.version_constraints)
                if version and definition.version_constraints
                else None
            )
            if compatible is False:
                continue
            matching = [
                c
                for c in components
                if c.type in definition.applicable_component_types
                and c.expected is not False
                and c.presence not in {"DISABLED", "ABSENT_OPTIONAL"}
            ]
            targets: list[tuple[str, tuple[str, ...], str | None]] = []
            if definition.scope == "component":
                targets = [(c.id, c.resources, c.id) for c in matching]
            else:
                for node in sorted(result.topology_context.nodes, key=lambda n: n.id):
                    if node.kind not in definition.applicable_resource_types or node.id in disabled:
                        continue
                    owners = [c for c in matching if node.id in c.resources]
                    if definition.applicable_component_types and not owners:
                        continue
                    targets.append((node.id, (node.id,), owners[0].id if owners else None))
            for subject, resources, component in targets:
                if definition.rule == RuleKind.REFERENCE and not any(
                    e.source in resources and e.relation.startswith("unresolved_")
                    for e in result.semantic_links
                ):
                    continue
                identifier = identity("hypothesis", result.id, definition.id, subject)
                generated.append(
                    HypothesisInstance(
                        id=identifier,
                        definition_id=definition.id,
                        subject=subject,
                        resources=resources,
                        component_id=component,
                        statement=definition.description,
                        generated_because=("catalog_scope_match",),
                        version_compatible=compatible,
                        evaluation=HypothesisEvaluation(
                            hypothesis_id=identifier,
                            status=EvaluationStatus.CANDIDATE,
                            confidence=initial_confidence(),
                            reason_codes=("awaiting_evaluation",),
                            provenance=(),
                        ),
                        knowledge_refs=tuple(k.id for k in result.knowledge),
                        historical_refs=tuple(h.id for h in result.historical_matches),
                    )
                )
        focus = (
            {result.context.request.resource_id}
            if result.context.request.resource_id
            else {
                r
                for c in components
                if c.id == result.context.request.component_id
                for r in c.resources
            }
        )
        return tuple(
            sorted(
                generated,
                key=lambda h: (
                    not (h.subject == result.context.subject or bool(set(h.resources) & focus)),
                    self.catalog.by_id[h.definition_id].priority,
                    h.definition_id,
                    h.subject,
                ),
            )
        )
