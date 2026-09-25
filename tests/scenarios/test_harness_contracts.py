import asyncio
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from agt_mcp.core.errors import AuthorizationError
from agt_mcp.validation.assertions import evaluate
from agt_mcp.validation.models import DiagnosticValidationReport, ExpectedDiagnosis, FailureScenario
from agt_mcp.validation.runner import ScenarioRunner
from tests.scenarios.fixtures import (
    ScenarioDefinition,
    application,
    definitions,
    fixed_world,
    materialize,
)


def case(name="tcp-failure"):
    return next(c for c in definitions() if c.id == name)


@pytest.mark.parametrize(
    "change",
    [
        {"must_support": ["X"], "must_not_include": ["X"]},
        {"must_support": ["X"], "must_reject": ["X"]},
        {"inconclusive": True, "must_support": ["X"]},
        {"min_evidence": 5, "max_evidence": 2},
    ],
)
def test_invalid_expectations_fail_before_execution(change):
    with pytest.raises(ValidationError):
        ExpectedDiagnosis(**change)


@pytest.mark.parametrize(
    "change",
    [
        {"profile": "shell-command"},
        {"mode": "real-lab"},
        {"extra": "ignored"},
    ],
)
def test_invalid_dsl_is_not_executable(change):
    with pytest.raises(ValidationError):
        ScenarioDefinition.model_validate({**case().model_dump(), **change})


@pytest.mark.parametrize("change", ["environment", "subject", "window", "observation", "probe"])
def test_invalid_canonical_scenario_scope(change):
    scenario = materialize(case("secret-in-log"))
    data = scenario.model_dump()
    if change == "environment":
        data["environment"] = "other"
    elif change == "subject":
        data["query"]["resource_id"] = "absent"
    elif change == "window":
        data["query"]["time_window"] = None
    elif change == "observation":
        data["observations"][0]["environment_id"] = "other"
    else:
        data["probe_results"][0]["target"]["environment_id"] = "other"
    with pytest.raises(ValidationError):
        FailureScenario.model_validate(data)


def run(scenario):
    with fixed_world():
        return asyncio.run(ScenarioRunner(application).run(scenario))


def test_fixed_clock_produces_identical_results_and_qualitative_confidence():
    scenario = materialize(case())
    first, second = run(scenario), run(scenario)
    assert first == second
    assert {h.evaluation.confidence.level for h in first.actual.hypotheses} <= {
        "low",
        "medium",
        "high",
    }
    assert all(p.result.duration_ms == 0 for p in first.virtual_trace.probes)


def test_false_positive_and_negative_assertions_are_not_tautologies():
    scenario = materialize(case())
    actual = run(scenario)
    wrong = scenario.model_copy(
        update={
            "expected": ExpectedDiagnosis(
                must_support=("DNS_RESOLUTION_FAILURE",),
                must_not_include=("DEPENDENCY_TCP_UNAVAILABLE",),
                must_reject=("DEPENDENCY_TCP_UNAVAILABLE",),
                expected_confidence={"DEPENDENCY_TCP_UNAVAILABLE": "high"},
            )
        }
    )
    result = evaluate(wrong, actual.actual, actual.virtual_trace)
    assert result.status == "FAIL" and result.false_positive_failures == 2
    assert result.false_negative_failures == 1
    assert "confidence:DEPENDENCY_TCP_UNAVAILABLE" in result.failed_assertions


def test_missing_diagnosis_and_expected_denial_are_distinguished():
    scenario = materialize(case())
    assert evaluate(scenario, None).status == "FAIL"
    denied = scenario.model_copy(update={"expected": ExpectedDiagnosis(error="authorization")})
    result = evaluate(denied, None, error="authorization")
    assert result.status == "PASS" and result.actual is None
    with pytest.raises(ValueError, match="duplicate"):
        DiagnosticValidationReport.summarize((result, result))


def test_report_never_exposes_secret_even_when_product_regresses():
    scenario = materialize(case())
    actual = run(scenario)
    poisoned = actual.actual.model_copy(
        update={
            "context": actual.actual.context.model_copy(
                update={
                    "symptom": actual.actual.context.symptom.model_copy(
                        update={"text": "fake-scenario-secret"}
                    )
                }
            )
        }
    )
    result = evaluate(scenario, poisoned, actual.virtual_trace)
    assert "secret_protection" in result.failed_assertions
    assert result.actual is None and result.virtual_trace is None
    assert (
        "fake-scenario-secret"
        not in DiagnosticValidationReport.summarize((result,)).model_dump_json()
    )


def test_runner_uses_application_entrypoint_and_stops_after_denial():
    scenario = materialize(case())
    calls = []

    async def denied(tool, args):
        calls.append(tool)
        raise AuthorizationError()

    result = asyncio.run(ScenarioRunner(Mock()).run_with(scenario, denied))
    assert result.error == "authorization" and len(calls) == 1


def test_duplicate_observations_do_not_raise_confidence():
    duplicate = materialize(case("duplicate-evidence"))
    unique = duplicate.model_copy(update={"observations": duplicate.observations[:3]})
    first, second = run(duplicate), run(unique)
    assert first.actual == second.actual


@pytest.mark.parametrize("name", ["ssrf-attempt", "unapproved-target", "active-probes-disabled"])
def test_no_executor_call_for_blocked_or_unapproved_target(name):
    scenario = materialize(case(name))
    runtime = application(scenario)
    runner = ScenarioRunner(lambda _: runtime)
    with fixed_world():
        result = asyncio.run(runner.run(scenario))
    assert result.status == "PASS" and not runtime.trace.runner.executor.calls


def test_fixture_state_never_reads_secret_contents():
    scenario = materialize(case("missing-secret-reference"))
    refs = [r for r in scenario.runtime_state.topology.nodes if r.kind.value == "secret_reference"]
    assert refs and all(r.details["content_read"] is False for r in refs)
    assert any(u.target.kind == "Secret" for u in scenario.runtime_state.unresolved)
