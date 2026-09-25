"""Scenario expectations reuse canonical runtime, probe and diagnostic contracts."""

from typing import Literal, Self

from pydantic import Field, model_validator

from agt_mcp.configuration.probes import ProbesConfig
from agt_mcp.core.models import ConfidenceLevel, Identifier, Model, Text
from agt_mcp.core.runtime import RuntimeSnapshot
from agt_mcp.correlation.models import CorrelationQuery
from agt_mcp.observability.models import SignalObservation
from agt_mcp.probes.models import ProbeResult, ProbeStatus, ProbeType
from agt_mcp.trace.models import VirtualTrace
from agt_mcp.troubleshooting.models import TroubleshootingResult


class ExpectedDiagnosis(Model):
    must_support: tuple[Identifier, ...] = ()
    must_reject: tuple[Identifier, ...] = ()
    may_include: tuple[Identifier, ...] = ()
    must_not_include: tuple[Identifier, ...] = ()
    must_detect: tuple[Identifier, ...] = ()
    expected_confidence: dict[Identifier, ConfidenceLevel] = Field(default_factory=dict)
    expected_recommendations: tuple[Identifier, ...] = ()
    probe_statuses: dict[ProbeType, ProbeStatus] = Field(default_factory=dict)
    probe_facts: dict[str, str | bool | int] = Field(default_factory=dict)
    evidence_categories: tuple[Identifier, ...] = ()
    unresolved_kinds: tuple[Identifier, ...] = ()
    inconclusive: bool = False
    partial: bool = False
    error: Identifier | None = None
    min_evidence: int = Field(default=1, ge=0, le=200)
    max_evidence: int = Field(default=200, ge=1, le=200)
    preserve_contradictions: bool = False
    historical_context: bool = False

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if set(self.must_support) & set((*self.must_reject, *self.must_not_include)):
            raise ValueError("conflicting hypothesis expectations")
        if self.inconclusive and self.must_support:
            raise ValueError("inconclusive cannot require promoted candidates")
        if self.min_evidence > self.max_evidence:
            raise ValueError("invalid evidence bounds")
        return self


class FailureScenario(Model):
    id: Identifier
    title: Text
    description: Text
    gateway_type: Literal["threescale"] = "threescale"
    environment: Identifier
    mode: Literal["fixture"] = "fixture"
    golden: bool = False
    runtime_state: RuntimeSnapshot
    query: CorrelationQuery
    probes: ProbesConfig
    probe_results: tuple[ProbeResult, ...] = ()
    observations: tuple[SignalObservation, ...] = Field(default=(), max_length=20000)
    expected: ExpectedDiagnosis
    source_unavailable: bool = False
    request_environment: Identifier | None = None
    deny_diagnosis: bool = False
    # Only the fixture and evaluator see these values; reports never serialize them.
    forbidden_fragments: tuple[Identifier, ...] = Field(default=(), exclude=True, repr=False)

    @model_validator(mode="after")
    def scope(self) -> Self:
        if self.runtime_state.environment_id != self.environment:
            raise ValueError("scenario environment mismatch")
        if self.query.resource_id not in {r.id for r in self.runtime_state.topology.nodes}:
            raise ValueError("scenario subject must resolve")
        if self.query.time_window is None:
            raise ValueError("fixed scenario window required")
        if any(o.environment_id != self.environment for o in self.observations):
            raise ValueError("foreign observation")
        if any(p.target.environment_id != self.environment for p in self.probe_results):
            raise ValueError("foreign probe")
        return self


class ScenarioResult(Model):
    scenario_id: Identifier
    golden: bool
    status: Literal["PASS", "FAIL"]
    expected: ExpectedDiagnosis
    actual: TroubleshootingResult | None = None
    virtual_trace: VirtualTrace | None = None
    error: Identifier | None = None
    matched_assertions: tuple[Identifier, ...]
    failed_assertions: tuple[Identifier, ...]
    evidence_count: int
    false_positive_failures: int
    false_negative_failures: int


class DiagnosticValidationReport(Model):
    results: tuple[ScenarioResult, ...]
    total: int
    passed: int
    failed: int
    inconclusive_expected: int
    false_positive_failures: int
    false_negative_failures: int
    golden_total: int
    golden_passed: int
    golden_failed: int

    @classmethod
    def summarize(cls, results: tuple[ScenarioResult, ...]) -> "DiagnosticValidationReport":
        if len({r.scenario_id for r in results}) != len(results):
            raise ValueError("duplicate scenario result")
        return cls(
            results=results,
            total=len(results),
            passed=sum(r.status == "PASS" for r in results),
            failed=sum(r.status == "FAIL" for r in results),
            inconclusive_expected=sum(r.expected.inconclusive for r in results),
            false_positive_failures=sum(r.false_positive_failures for r in results),
            false_negative_failures=sum(r.false_negative_failures for r in results),
            golden_total=sum(r.golden for r in results),
            golden_passed=sum(r.golden and r.status == "PASS" for r in results),
            golden_failed=sum(r.golden and r.status == "FAIL" for r in results),
        )
