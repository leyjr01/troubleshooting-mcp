import asyncio
from datetime import timedelta

import pytest

from agt_mcp.correlation.models import CorrelationLink
from agt_mcp.probes.models import ProbeObservation, ProbeResult, ProbeStatus, ProbeType
from agt_mcp.probes.planner import target_from
from agt_mcp.probes.refresh import reevaluate
from agt_mcp.probes.runner import as_evidence
from agt_mcp.troubleshooting.catalog import HypothesisCatalog
from agt_mcp.troubleshooting.network_hypotheses import NetworkHypothesisProvider
from tests.correlation_support import NOW, context, evidence, provenance, query
from tests.probe_support import config
from tests.troubleshooting_support import diagnose, diagnostic_snapshot, engine, hypothesis


def evaluate_probes(*results):
    subject = engine(diagnostic_snapshot(()))

    class Combined:
        def definitions(self):
            return (*subject.catalog.definitions, *NetworkHypothesisProvider().definitions())

    catalog = HypothesisCatalog((Combined(),))
    subject.catalog = subject.generator.catalog = subject.evaluator.catalog = (
        subject.planner.catalog
    ) = catalog
    before = diagnose(subject)
    return asyncio.run(
        reevaluate(
            subject, before.correlation_result, tuple(as_evidence(r) for r in results), context()
        )
    )


def probe(kind, status="PASS", error=None, seconds=-1, **observation):
    return ProbeResult(
        request_id=f"test-{kind}-{status}-{seconds}",
        target=target_from(config().endpoints[0], NOW),
        probe_type=kind,
        status=status,
        error_category=error,
        timestamp=NOW + timedelta(seconds=seconds),
        duration_ms=0,
        observation=ProbeObservation(**observation),
    )


@pytest.mark.parametrize(
    "kind,status,error,facts,identifier,expected",
    [
        ("DNS", "FAILED", "DNS_RESOLUTION_FAILED", {}, "DNS_RESOLUTION_FAILURE", "SUPPORTED"),
        ("DNS", "FAILED", "DNS_TIMEOUT", {}, "DNS_RESOLUTION_FAILURE", "SUPPORTED"),
        ("DNS", "PASS", None, {"addresses": ("10.20.1.2",)}, "DNS_RESOLUTION_FAILURE", "REJECTED"),
        ("DNS", "PASS", None, {}, "DNS_RESOLUTION_FAILURE", "INCONCLUSIVE"),
        ("DNS", "FAILED", "EXECUTOR_ERROR", {}, "DNS_RESOLUTION_FAILURE", "INCONCLUSIVE"),
        ("HTTPS", "PASS", None, {"http_status": 500}, "BACKEND_HTTP_ERROR", "SUPPORTED"),
        ("HTTP", "PASS", None, {"http_status": 200}, "BACKEND_HTTP_ERROR", "REJECTED"),
        ("HTTP", "PASS", None, {"http_status": 404}, "BACKEND_HTTP_ERROR", "REJECTED"),
        ("HTTP", "PASS", None, {}, "BACKEND_HTTP_ERROR", "INCONCLUSIVE"),
        ("HTTPS", "FAILED", "HTTP_TIMEOUT", {}, "BACKEND_TIMEOUT", "SUPPORTED"),
        ("HTTPS", "PASS", None, {"http_status": 500}, "BACKEND_TIMEOUT", "REJECTED"),
        ("HTTPS", "FAILED", "HTTP_PROTOCOL_ERROR", {}, "BACKEND_TIMEOUT", "INCONCLUSIVE"),
    ],
)
def test_typed_observations_promote_only_the_observed_condition(
    kind, status, error, facts, identifier, expected
):
    result = evaluate_probes(probe(kind, status, error, **facts))
    h = hypothesis(result, identifier)
    assert h.evaluation.status == expected
    candidates = [c for c in result.root_cause_candidates if c.hypothesis_id == h.id]
    assert bool(candidates) == (expected == "SUPPORTED")
    if candidates:
        assert candidates[0].supporting_evidence == h.evaluation.supporting_evidence
        assert candidates[0].provenance and candidates[0].confidence.level == "medium"
    for other in ("TLS_VERIFICATION_UNAVAILABLE", "DEPENDENCY_TCP_UNAVAILABLE"):
        assert hypothesis(result, other).evaluation.status == "INCONCLUSIVE"


@pytest.mark.parametrize("status", ["BLOCKED", "NOT_EXECUTED", "CANCELLED"])
@pytest.mark.parametrize(
    "kind,error,identifier",
    [
        ("DNS", "DNS_RESOLUTION_FAILED", "DNS_RESOLUTION_FAILURE"),
        ("HTTPS", "HTTP_TIMEOUT", "BACKEND_TIMEOUT"),
    ],
)
def test_unexecuted_or_blocked_results_cannot_promote(kind, error, identifier, status):
    result = evaluate_probes(probe(kind, status, error))
    assert hypothesis(result, identifier).evaluation.status == "INCONCLUSIVE"
    assert not result.root_cause_candidates


@pytest.mark.parametrize("seconds", [-1000, 90])
def test_out_of_window_failure_cannot_promote(seconds):
    result = evaluate_probes(probe("DNS", "FAILED", "DNS_RESOLUTION_FAILED", seconds))
    assert not result.root_cause_candidates


def test_current_conflicting_dns_facts_stay_inconclusive_and_retain_provenance():
    result = evaluate_probes(
        probe("DNS", "FAILED", "DNS_RESOLUTION_FAILED", -2),
        probe("DNS", addresses=("10.20.1.2",)),
    )
    evaluation = hypothesis(result, "DNS_RESOLUTION_FAILURE").evaluation
    assert evaluation.status == "INCONCLUSIVE"
    assert evaluation.supporting_evidence and evaluation.contradicting_evidence
    assert len(evaluation.provenance) == 2
    assert not result.root_cause_candidates


@pytest.mark.parametrize("kind", ["ConfigMap", "Secret"])
@pytest.mark.parametrize(
    "resolution,seconds,expected",
    [
        ("not_found", 0, "SUPPORTED"),
        ("not_observed", 0, "BLOCKED_BY_MISSING_EVIDENCE"),
        ("forbidden", 0, "BLOCKED_BY_MISSING_EVIDENCE"),
        ("not_found", -1000, "BLOCKED_BY_MISSING_EVIDENCE"),
    ],
)
def test_configuration_reference_needs_current_explicit_absence(
    kind, resolution, seconds, expected
):
    link = CorrelationLink(
        id="reference",
        source="pod",
        target="missing",
        target_kind=kind,
        relation="unresolved_" + resolution,
        provenance=provenance().model_copy(
            update={"retrieved_at": NOW + timedelta(seconds=seconds)}
        ),
    )
    snapshot = diagnostic_snapshot((evidence("pod-observation", "pod"),)).model_copy(
        update={"links": (link,)}
    )
    result = diagnose(engine(snapshot), query(resource_id="pod"))
    h = hypothesis(result, "CONFIGURATION_REFERENCE_UNRESOLVED")
    assert h.evaluation.status == expected
    assert h.evaluation.topology_refs == ("reference",)
    if expected == "SUPPORTED":
        assert h.evaluation.supporting_evidence == ("pod-observation",)
        assert link.provenance in h.evaluation.provenance


@pytest.mark.parametrize(
    "expiry,chain,expected",
    [
        ("2026-09-01T00:00:00+00:00", None, "tls_certificate_validity"),
        ("2027-09-01T00:00:00+00:00", False, "tls_certificate_chain"),
        ("not-a-date", None, None),
        ("2020-01-01T00:00:00", None, None),
    ],
)
def test_tls_recommendations_distinguish_expiry_from_chain_without_writes(expiry, chain, expected):
    result = evaluate_probes(
        probe(
            ProbeType.TLS,
            ProbeStatus.FAILED,
            "TLS_VERIFICATION_FAILED",
            certificate_verified=False,
            valid_until=expiry,
            chain_verified=chain,
        )
    )
    h = hypothesis(result, "TLS_VERIFICATION_UNAVAILABLE")
    assert h.evaluation.status == "SUPPORTED"
    steps = [s for s in result.troubleshooting_plan.steps if h.id in s.hypothesis_ids]
    requirements = {r for s in steps for r in s.expected_evidence}
    assert "tls_verification" in requirements
    specific = requirements & {"tls_certificate_validity", "tls_certificate_chain"}
    assert specific == ({expected} if expected else set())
    assert all(not s.executable and s.safety_class == "READ_ONLY_INSPECTION" for s in steps)
    if expected:
        assert (
            "tls_certificate_expired" if expected.endswith("validity") else "tls_chain_unverified"
        ) in h.evaluation.reason_codes
