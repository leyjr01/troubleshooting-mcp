"""Deterministic statuses and qualitative confidence, with explicit missing evidence."""

from agt_mcp.core.models import ConfidenceLevel
from agt_mcp.troubleshooting.catalog import HypothesisCatalog
from agt_mcp.troubleshooting.generator import initial_confidence
from agt_mcp.troubleshooting.models import (
    EvaluationStatus,
    HypothesisEvaluation,
    HypothesisInstance,
    RuleKind,
)
from agt_mcp.troubleshooting.rules import RULES, EvidenceView


class HypothesisEvaluator:
    def __init__(self, catalog: HypothesisCatalog, max_evidence: int) -> None:
        self.catalog, self.max_evidence = catalog, max_evidence

    def evaluate(self, h: HypothesisInstance, view: EvidenceView) -> HypothesisInstance:
        definition = self.catalog.by_id[h.definition_id]
        result = RULES[definition.rule](view, h)
        support = tuple(sorted(set(result.support)))
        contra = tuple(sorted(set(result.contradiction)))
        missing = tuple(r for r in definition.required_evidence if r.id in result.missing)
        reasons = ["deterministic_runtime_evaluation"]
        limited = len(support) + len(contra) > self.max_evidence
        # Never silently discard contradictory evidence in order to promote a candidate.
        contra = contra[: self.max_evidence]
        support = support[: max(0, self.max_evidence - len(contra))]
        incompatible = bool(definition.version_constraints and h.version_compatible is not True)
        if incompatible:
            reasons.append("version_compatibility_unconfirmed")
        if limited:
            reasons.append("evidence_limit_reached")
        if definition.rule == RuleKind.EXTERNAL:
            status = EvaluationStatus.INCONCLUSIVE
            reasons.append("external_connectivity_unverified")
        elif limited or incompatible:
            status = EvaluationStatus.INCONCLUSIVE
            reasons.append("conflicting_or_limited_evidence")
        elif contra and not support:
            status = EvaluationStatus.REJECTED
            reasons.append("direct_runtime_rejection")
        elif contra:
            status = EvaluationStatus.INCONCLUSIVE
            reasons.append("conflicting_or_limited_evidence")
        elif missing:
            status = EvaluationStatus.BLOCKED
            reasons.append("required_evidence_missing")
        elif support:
            status = EvaluationStatus.SUPPORTED
            reasons.append("required_runtime_conditions_observed")
        else:
            status = EvaluationStatus.INCONCLUSIVE
            reasons.append("no_decisive_runtime_evidence")
        if h.historical_refs or h.knowledge_refs:
            reasons.append("references_are_not_runtime_support")
        sources = {view.evidence[i].source.source_id for i in support}
        origins = {view.states[i].origin for i in support}
        independent = len(sources) > 1 and len(origins) > 1
        high = status == EvaluationStatus.SUPPORTED and (result.decisive or independent)
        level = (
            ConfidenceLevel.HIGH
            if high
            else ConfidenceLevel.MEDIUM
            if status == EvaluationStatus.SUPPORTED
            else ConfidenceLevel.LOW
        )
        if high:
            reasons.append(
                "bounded_structural_proof" if result.decisive else "independent_runtime_support"
            )
        confidence = initial_confidence().model_copy(
            update={
                "level": level,
                "rationale": "; ".join(reasons),
                "supporting_evidence": support,
                "contradicting_evidence": contra,
                "source_reliability": "Distinct runtime facts; topology plus completed lookup "
                "can prove a bounded structural condition",
                "temporal_relevance": "Only observations marked relevant by correlation",
                "topological_relevance": "Direct resources or endpoint/routing links; "
                "no causal chain inferred",
            }
        )
        provenance = [view.evidence[i].source for i in (*support, *contra)]
        provenance.extend(
            e.source_of_information
            for e in view.result.topology_context.edges
            if e.id in result.topology
        )
        provenance.extend(
            e.provenance for e in view.result.semantic_links if e.id in result.topology
        )
        unique = {p.model_dump_json(): p for p in provenance}
        evaluation = HypothesisEvaluation(
            hypothesis_id=h.id,
            status=status,
            supporting_evidence=support,
            contradicting_evidence=contra,
            missing_evidence=missing,
            topology_refs=result.topology,
            confidence=confidence,
            reason_codes=tuple(reasons),
            provenance=tuple(unique[k] for k in sorted(unique)),
        )
        return h.model_copy(update={"evaluation": evaluation})
