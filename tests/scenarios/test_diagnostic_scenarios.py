import asyncio
from pathlib import Path

import pytest

from agt_mcp.validation.models import DiagnosticValidationReport
from agt_mcp.validation.runner import ScenarioRunner
from tests.scenarios.fixtures import application, definitions, fixed_world, materialize

CASES = definitions()


@pytest.fixture(scope="module")
def results():
    return {}


@pytest.mark.diagnostic_scenarios
@pytest.mark.parametrize(
    "case",
    [pytest.param(c, id=c.id, marks=[pytest.mark.golden] if c.golden else []) for c in CASES],
)
def test_diagnostic_contract(case, results, request, caplog):
    scenario = materialize(case)
    with fixed_world():
        result = asyncio.run(ScenarioRunner(application).run(scenario))
    results[case.id] = result
    assert "fake-scenario-secret" not in result.model_dump_json() + caplog.text
    if request.config.getoption("--scenario-acceptance"):
        assert result.status == "PASS", result.failed_assertions
    assert set(result.failed_assertions) == set(case.known_gaps), result.failed_assertions
    # Known detection gaps stay FAIL in the report, never converted to scenario PASS.
    assert result.status == ("FAIL" if case.known_gaps else "PASS")


@pytest.mark.diagnostic_scenarios
def test_suite_report(results):
    # Reuse completed scenario outputs; a filtered invocation reports its own subset.
    report = DiagnosticValidationReport.summarize(tuple(results[k] for k in sorted(results)))
    assert report.total == report.passed + report.failed
    assert report.golden_total == report.golden_passed + report.golden_failed
    assert report.false_positive_failures == 0
    assert report.failed == sum(bool(c.known_gaps) for c in CASES if c.id in results)
    (Path(__file__).resolve().parents[2] / "sprint9-scenarios.json.tmp").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
