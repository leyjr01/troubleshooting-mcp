"""Produce inspection descriptions only; there is deliberately no executor."""

from agt_mcp.correlation.rules import identity
from agt_mcp.troubleshooting.catalog import HypothesisCatalog
from agt_mcp.troubleshooting.models import (
    HypothesisInstance,
    SafetyClass,
    TroubleshootingPlan,
    TroubleshootingStep,
)


class TroubleshootingPlanner:
    def __init__(self, catalog: HypothesisCatalog, max_steps: int) -> None:
        self.catalog, self.max_steps = catalog, max_steps

    def plan(self, hypotheses: tuple[HypothesisInstance, ...]) -> tuple[TroubleshootingPlan, bool]:
        steps: dict[tuple[str, str], TroubleshootingStep] = {}
        for h in hypotheses:
            requirements = (
                h.evaluation.missing_evidence
                or self.catalog.by_id[h.definition_id].optional_evidence
            )
            for requirement in requirements:
                key = (h.subject, requirement.id)
                previous = steps.get(key)
                ids = tuple(sorted({h.id, *(previous.hypothesis_ids if previous else ())}))
                steps[key] = TroubleshootingStep(
                    id=identity("step", *key),
                    description=requirement.description,
                    purpose="Collect missing evidence"
                    if h.evaluation.missing_evidence
                    else "Strengthen runtime context",
                    required_capability=requirement.required_capability,
                    target=h.subject,
                    expected_evidence=(requirement.id,),
                    hypothesis_ids=ids,
                    safety_class=requirement.safety_class,
                    status="PLANNED"
                    if requirement.safety_class == SafetyClass.READ_ONLY_INSPECTION
                    else "CAPABILITY_UNAVAILABLE",
                )
        ordered = sorted(
            steps.values(),
            key=lambda s: (s.safety_class != SafetyClass.READ_ONLY_INSPECTION, s.target, s.id),
        )
        return TroubleshootingPlan(steps=tuple(ordered[: self.max_steps])), len(
            ordered
        ) > self.max_steps
