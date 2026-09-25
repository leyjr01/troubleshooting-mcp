"""Semantic result assertions; no inference, confidence calculation or causal rules."""

from agt_mcp.trace.models import VirtualTrace
from agt_mcp.troubleshooting.models import TroubleshootingResult
from agt_mcp.validation.models import FailureScenario, ScenarioResult


def evaluate(
    scenario: FailureScenario,
    actual: TroubleshootingResult | None,
    trace: VirtualTrace | None = None,
    error: str | None = None,
) -> ScenarioResult:
    checks: dict[str, bool] = {"expected_error": error == scenario.expected.error}
    expected = scenario.expected
    count = 0
    promoted: set[str] = set()
    if actual is not None:
        hypotheses = actual.hypotheses
        candidate_ids = {c.hypothesis_id for c in actual.root_cause_candidates}
        promoted = {h.definition_id for h in hypotheses if h.id in candidate_ids}
        evidence = {e.id: e for g in actual.correlation_result.evidence_sets for e in g.evidence}
        count = len(evidence)
        checks["evidence_bounds"] = expected.min_evidence <= count <= expected.max_evidence
        checks["symptom_preserved"] = actual.context.symptom.text == scenario.query.symptom
        checks["environment_isolation"] = actual.context.environment_id == scenario.environment
        checks["candidate_provenance"] = all(
            c.provenance
            and c.supporting_evidence
            and all(
                i in evidence and evidence[i].source.content_sha256 for i in c.supporting_evidence
            )
            for c in actual.root_cause_candidates
        )
        checks["safe_recommendations"] = not actual.troubleshooting_plan.executed and all(
            not s.executable and s.safety_class in {"READ_ONLY_INSPECTION", "PASSIVE_PROBE"}
            for s in actual.troubleshooting_plan.steps
        )
        for identifier in expected.must_support:
            checks[f"support:{identifier}"] = identifier in promoted
        for identifier in expected.must_reject:
            checks[f"reject:{identifier}"] = (
                any(
                    h.definition_id == identifier and h.evaluation.status == "REJECTED"
                    for h in hypotheses
                )
                and identifier not in promoted
            )
        for identifier in expected.must_not_include:
            checks[f"forbid:{identifier}"] = identifier not in promoted
        for identifier in expected.must_detect:
            checks[f"detect:{identifier}"] = any(h.definition_id == identifier for h in hypotheses)
        for identifier, level in expected.expected_confidence.items():
            checks[f"confidence:{identifier}"] = any(
                h.definition_id == identifier and h.evaluation.confidence.level == level
                for h in hypotheses
            )
        requirements = {
            r
            for s in actual.troubleshooting_plan.steps
            if s.target == actual.context.subject
            for r in s.expected_evidence
        }
        for identifier in expected.expected_recommendations:
            checks[f"recommend:{identifier}"] = identifier in requirements
        categories = {t.event_type for t in actual.correlation_result.timeline}
        for category in expected.evidence_categories:
            checks[f"evidence:{category}"] = category in categories
        for kind in expected.unresolved_kinds:
            checks[f"unresolved:{kind}"] = any(
                e.target_kind == kind and e.relation.startswith("unresolved_")
                for e in actual.correlation_result.semantic_links
            )
        if expected.inconclusive:
            checks["inconclusive"] = not promoted and any(
                h.evaluation.status in {"INCONCLUSIVE", "BLOCKED_BY_MISSING_EVIDENCE"}
                for h in hypotheses
            )
        if expected.partial:
            checks["partial"] = actual.status in {"PARTIAL", "LIMITED"} or bool(actual.warnings)
        if expected.preserve_contradictions:
            checks["contradictions_preserved"] = any(
                h.evaluation.contradicting_evidence
                and all(i in evidence for i in h.evaluation.contradicting_evidence)
                for h in hypotheses
            )
        if expected.historical_context:
            history = actual.correlation_result.historical_matches
            checks["history_preserved"] = bool(history)
            checks["history_not_runtime_support"] = all(
                h.id not in evidence and not h.runtime_support for h in history
            )
    elif expected.error is None:
        checks["diagnosis_present"] = False
    if trace is not None:
        checks["trace_provenance"] = all(h.provenance for h in trace.hops)
        checks["probe_provenance"] = all(
            p.result.target.provenance.content_sha256 and p.evidence.source.content_sha256
            for p in trace.probes
        )
    for kind, status in expected.probe_statuses.items():
        checks[f"probe:{kind.value}"] = trace is not None and any(
            p.result.probe_type == kind and p.result.status == status for p in trace.probes
        )
    for field, value in expected.probe_facts.items():
        checks[f"probe_fact:{field}"] = trace is not None and any(
            p.result.observation.model_dump().get(field) == value for p in trace.probes
        )
    serialized = (actual.model_dump_json() if actual else "") + (
        trace.model_dump_json() if trace else ""
    )
    checks["secret_protection"] = all(s not in serialized for s in scenario.forbidden_fragments)
    # A failing security assertion must not cause the report itself to leak the fixture.
    if not checks["secret_protection"]:
        actual, trace = None, None
    failed = tuple(sorted(k for k, passed in checks.items() if not passed))
    return ScenarioResult(
        scenario_id=scenario.id,
        golden=scenario.golden,
        status="FAIL" if failed else "PASS",
        expected=expected,
        actual=actual,
        virtual_trace=trace,
        error=error,
        matched_assertions=tuple(sorted(k for k, passed in checks.items() if passed)),
        failed_assertions=failed,
        evidence_count=count,
        false_positive_failures=sum(
            k.startswith("forbid:")
            or k == "inconclusive"
            or k.startswith("reject:")
            and k.removeprefix("reject:") in promoted
            for k in failed
        ),
        false_negative_failures=sum(k.startswith(("support:", "detect:")) for k in failed),
    )
