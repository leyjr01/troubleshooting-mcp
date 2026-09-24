"""Compose correlation, generation, evaluation, candidate extraction and safe planning."""

from agt_mcp.configuration.troubleshooting import TroubleshootingConfig
from agt_mcp.core.errors import AuthorizationError
from agt_mcp.core.execution import ExecutionContext
from agt_mcp.correlation.engine import EvidenceCorrelationEngine
from agt_mcp.correlation.models import CorrelationQuery, CorrelationResult
from agt_mcp.correlation.rules import identity
from agt_mcp.troubleshooting.catalog import HypothesisCatalog
from agt_mcp.troubleshooting.evaluator import HypothesisEvaluator
from agt_mcp.troubleshooting.generator import HypothesisGenerator
from agt_mcp.troubleshooting.models import (
    EvaluationStatus,
    ReportedSymptom,
    RootCauseCandidate,
    TroubleshootingContext,
    TroubleshootingResult,
)
from agt_mcp.troubleshooting.planner import TroubleshootingPlanner
from agt_mcp.troubleshooting.rules import EvidenceView


class TroubleshootingEngine:
    def __init__(
        self,
        correlation: EvidenceCorrelationEngine,
        catalog: HypothesisCatalog,
        config: TroubleshootingConfig,
    ) -> None:
        self.correlation, self.catalog, self.config = correlation, catalog, config
        self.generator = HypothesisGenerator(catalog)
        self.evaluator = HypothesisEvaluator(catalog, config.max_evidence_per_hypothesis)
        self.planner = TroubleshootingPlanner(catalog, config.max_plan_steps)

    async def diagnose(
        self, query: CorrelationQuery, execution: ExecutionContext
    ) -> TroubleshootingResult:
        result = await self.correlation.correlate(query, execution)
        return self.evaluate(result, execution)

    def evaluate(
        self, result: CorrelationResult, execution: ExecutionContext
    ) -> TroubleshootingResult:
        if result.context.environment_id != execution.environment_id:
            raise AuthorizationError()
        # Validate copied/injected models at this boundary, including canonical lineage.
        result = CorrelationResult.model_validate(result.model_dump())
        view = EvidenceView(result)
        generated = self.generator.generate(result, self.config.max_components)
        warnings = {w.code for w in result.warnings}
        if len(generated) > self.config.max_hypotheses:
            warnings.add("hypotheses_truncated")
        if len(result.component_context) > self.config.max_components:
            warnings.add("components_truncated")
        hypotheses = tuple(
            self.evaluator.evaluate(h, view) for h in generated[: self.config.max_hypotheses]
        )
        candidates = []
        for h in hypotheses:
            if h.evaluation.status == EvaluationStatus.SUPPORTED:
                candidates.append(
                    RootCauseCandidate(
                        id=identity("cause-candidate", h.id),
                        hypothesis_id=h.id,
                        subject=h.subject,
                        summary=h.statement,
                        supporting_evidence=h.evaluation.supporting_evidence,
                        confidence=h.evaluation.confidence,
                        provenance=h.evaluation.provenance,
                    )
                )
            warnings.update(
                code
                for code in h.evaluation.reason_codes
                if code in {"version_compatibility_unconfirmed", "evidence_limit_reached"}
            )
        ranks = {"high": 0, "medium": 1, "low": 2}
        candidates.sort(key=lambda c: (ranks[c.confidence.level], c.subject, c.id))
        if len(candidates) > self.config.max_candidates:
            warnings.add("root_candidates_truncated")
        plan, truncated = self.planner.plan(hypotheses)
        if truncated:
            warnings.add("plan_truncated")
        missing = tuple(
            sorted(
                {
                    r.required_capability
                    for h in hypotheses
                    for r in h.evaluation.missing_evidence
                    if r.required_capability.endswith("_NOT_AVAILABLE")
                }
            )
        )
        query = result.context.request
        observed = next((t for t in result.timeline if t.relevant), None)
        symptom = ReportedSymptom(
            text=query.symptom
            or (observed.observation if observed else "Inspect observed runtime conditions"),
            origin="user_reported"
            if query.symptom
            else "runtime_observed"
            if observed
            else "unspecified",
            evidence_ids=(observed.evidence_id,) if observed and not query.symptom else (),
        )
        context = TroubleshootingContext(
            environment_id=execution.environment_id,
            subject=result.context.subject,
            symptom=symptom,
            time_window=result.context.time_window,
            correlation_id=result.id,
        )
        sources = {p.model_dump_json(): p for h in hypotheses for p in h.evaluation.provenance}
        output = TroubleshootingResult(
            id="pending",
            context=context,
            correlation_result=result,
            hypotheses=hypotheses,
            root_cause_candidates=tuple(candidates[: self.config.max_candidates]),
            troubleshooting_plan=plan,
            warnings=tuple(sorted(warnings)),
            missing_capabilities=missing,
            provenance=tuple(sources[k] for k in sorted(sources)),
            status="PARTIAL"
            if warnings or any(h.evaluation.missing_evidence for h in hypotheses)
            else "COMPLETE",
        )
        return output.model_copy(
            update={"id": identity("troubleshooting", output.model_dump_json())}
        )
