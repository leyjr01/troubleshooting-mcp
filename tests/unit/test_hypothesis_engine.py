from datetime import timedelta

import pytest

from agt_mcp.core.errors import ConfigurationError
from agt_mcp.core.models import ResourceKind
from agt_mcp.correlation.models import CorrelationLink, SignalCode, TimeWindow
from agt_mcp.troubleshooting.catalog import HypothesisCatalog
from agt_mcp.troubleshooting.models import RuleKind
from agt_mcp.troubleshooting.rules import RULES, Assessment
from tests.correlation_support import NOW, evidence, provenance, query
from tests.troubleshooting_support import catalog, diagnose, diagnostic_snapshot, engine, hypothesis


def test_catalog_is_extensible_unique_and_declarative():
    known = catalog()
    assert {d.rule for d in known.definitions} == set(RuleKind)
    assert len(known.by_id) == 15
    assert all(d.required_evidence and d.optional_evidence for d in known.definitions)

    class Provider:
        def definitions(self):
            return known.definitions

    with pytest.raises(ConfigurationError):
        HypothesisCatalog((Provider(), Provider()))


@pytest.mark.parametrize(
    "state,status,level",
    [
        ("unavailable", "SUPPORTED", "high"),
        ("ready", "REJECTED", "low"),
        ("unknown", "BLOCKED_BY_MISSING_EVIDENCE", "low"),
    ],
)
def test_endpoint_support_rejection_and_missing(state, status, level):
    result = diagnose(engine(diagnostic_snapshot((evidence("slice-state", "slice", state),))))
    h = hypothesis(result, "APICAST_NO_READY_RUNTIME_ENDPOINT")
    assert h.evaluation.status == status and h.evaluation.confidence.level == level
    assert any(c.hypothesis_id == h.id for c in result.root_cause_candidates) == (
        status == "SUPPORTED"
    )
    assert result.correlation_result.context.engine_version == "1.0.0"
    assert all(c.scope == "observed_condition" for c in result.root_cause_candidates)


def test_ready_contradiction_with_negative_observation_is_inconclusive():
    result = diagnose(
        engine(
            diagnostic_snapshot(
                (
                    evidence("no", "slice", "unavailable"),
                    evidence("yes", "slice", "ready", seconds=-1),
                )
            )
        )
    )
    h = hypothesis(result, "SERVICE_NO_READY_ENDPOINT")
    assert h.evaluation.status == "INCONCLUSIVE"
    assert h.evaluation.supporting_evidence == ("no",) and h.evaluation.contradicting_evidence == (
        "yes",
    )
    assert not result.root_cause_candidates


@pytest.mark.parametrize("coverage", ["forbidden", "unavailable", "truncated", "unsupported"])
def test_partial_endpoint_inventory_is_missing_not_false_rejection(coverage):
    result = diagnose(engine(diagnostic_snapshot(coverage=coverage)))
    h = hypothesis(result, "APICAST_NO_READY_RUNTIME_ENDPOINT")
    assert h.evaluation.status == "BLOCKED_BY_MISSING_EVIDENCE"
    assert "endpoint_readiness" in {r.id for r in h.evaluation.missing_evidence}
    assert not any(c.hypothesis_id == h.id for c in result.root_cause_candidates)


def test_known_empty_slice_supports_no_endpoint():
    atom = evidence("empty", "slice").model_copy(update={"signals": (SignalCode.ENDPOINTS_EMPTY,)})
    h = hypothesis(diagnose(engine(diagnostic_snapshot((atom,)))), "SERVICE_NO_READY_ENDPOINT")
    assert h.evaluation.status == "SUPPORTED" and h.evaluation.confidence.level == "high"


@pytest.mark.parametrize(
    "component,identifier,capability",
    [
        (
            "BACKEND_LISTENER",
            "BACKEND_EXTERNAL_REDIS_DEPENDENCY_UNRESOLVED",
            "REDIS_CONNECTIVITY_NOT_AVAILABLE",
        ),
        (
            "SYSTEM_APP",
            "SYSTEM_EXTERNAL_REDIS_DEPENDENCY_UNRESOLVED",
            "REDIS_CONNECTIVITY_NOT_AVAILABLE",
        ),
        (
            "SYSTEM_APP",
            "SYSTEM_DATABASE_DEPENDENCY_UNRESOLVED",
            "DATABASE_CONNECTIVITY_NOT_AVAILABLE",
        ),
    ],
)
def test_external_dependencies_never_confirmed_without_probe(component, identifier, capability):
    snap = diagnostic_snapshot(component_type=component)
    snap = snap.model_copy(
        update={
            "links": (
                CorrelationLink(
                    id="external",
                    source="service",
                    target="external-dependency",
                    relation="describes_connection_to",
                    provenance=provenance(),
                ),
            )
        }
    )
    result = diagnose(engine(snap))
    h = hypothesis(result, identifier)
    assert h.evaluation.status == "INCONCLUSIVE" and h.evaluation.confidence.level == "low"
    assert h.evaluation.missing_evidence and capability in result.missing_capabilities
    assert not any(c.hypothesis_id == h.id for c in result.root_cause_candidates)
    assert all(not s.executable for s in result.troubleshooting_plan.steps)
    assert any(
        s.safety_class == "PASSIVE_PROBE" and s.status == "CAPABILITY_UNAVAILABLE"
        for s in result.troubleshooting_plan.steps
    )


@pytest.mark.parametrize("version", [None, "UNKNOWN", "2.16.1", "2.15"])
def test_version_constraint_is_explicit(version):
    result = diagnose(
        engine(diagnostic_snapshot(component_type="BACKEND_LISTENER", version=version))
    )
    matches = [
        h
        for h in result.hypotheses
        if h.definition_id == "BACKEND_EXTERNAL_REDIS_DEPENDENCY_UNRESOLVED"
    ]
    if version == "2.15":
        assert not matches
    elif version == "2.16.1":
        assert matches[0].version_compatible is True
    else:
        assert matches[0].version_compatible is None
        assert "version_compatibility_unconfirmed" in result.warnings


@pytest.mark.parametrize(
    "kind,signal,definition_id",
    [
        ("pod", SignalCode.CRASH_LOOP, "POD_CRASH_LOOP"),
        ("persistentvolumeclaim", SignalCode.PVC_NOT_BOUND, "PVC_NOT_BOUND"),
    ],
)
def test_lifecycle_and_volume_are_conditions_not_invented_process_causes(
    kind, signal, definition_id
):
    atom = evidence("observed", "pod", "unavailable").model_copy(update={"signals": (signal,)})
    snap = diagnostic_snapshot((atom,))
    graph = snap.topology.model_copy(
        update={
            "nodes": tuple(
                n.model_copy(update={"kind": ResourceKind(kind)}) if n.id == "pod" else n
                for n in snap.topology.nodes
            )
        }
    )
    snap = snap.model_copy(update={"topology": graph})
    result = diagnose(engine(snap), query(resource_id="pod"))
    h = hypothesis(result, definition_id)
    assert h.evaluation.status == "SUPPORTED" and h.evaluation.provenance == (provenance(),)
    assert (
        "application bug" not in h.statement
        and "CONFIRMED_ROOT_CAUSE" not in result.model_dump_json()
    )


def test_bound_volume_rejects_and_no_observation_blocks():
    snap = diagnostic_snapshot(
        (evidence("bound", "pod").model_copy(update={"signals": (SignalCode.PVC_BOUND,)}),)
    )
    snap = snap.model_copy(
        update={
            "topology": snap.topology.model_copy(
                update={
                    "nodes": tuple(
                        n.model_copy(update={"kind": ResourceKind.PVC}) if n.id == "pod" else n
                        for n in snap.topology.nodes
                    )
                }
            )
        }
    )
    assert (
        hypothesis(
            diagnose(engine(snap), query(resource_id="pod")), "PVC_NOT_BOUND"
        ).evaluation.status
        == "REJECTED"
    )
    assert hypothesis(
        diagnose(engine(diagnostic_snapshot(())), query(resource_id="pod")), "POD_CRASH_LOOP"
    ).evaluation.missing_evidence


@pytest.mark.parametrize(
    "resolution,status",
    [
        ("not_found", "SUPPORTED"),
        ("forbidden", "BLOCKED_BY_MISSING_EVIDENCE"),
        ("not_observed", "BLOCKED_BY_MISSING_EVIDENCE"),
    ],
)
def test_route_unresolved_requires_completed_lookup(resolution, status):
    snap = diagnostic_snapshot((evidence("route-observation", "service"),))
    graph = snap.topology.model_copy(
        update={
            "nodes": tuple(
                n.model_copy(update={"kind": ResourceKind.ROUTE}) if n.id == "service" else n
                for n in snap.topology.nodes
            )
        }
    )
    snap = snap.model_copy(
        update={
            "topology": graph,
            "links": (
                CorrelationLink(
                    id="missing",
                    source="service",
                    target="target",
                    relation="unresolved_" + resolution,
                    provenance=provenance(),
                    target_kind="Service",
                ),
            ),
        }
    )
    result = diagnose(engine(snap))
    h = hypothesis(result, "ROUTE_TARGET_MISSING")
    assert h.evaluation.status == status
    if status == "SUPPORTED":
        assert h.evaluation.confidence.level == "high" and h.evaluation.topology_refs == (
            "missing",
        )


def test_disabled_optional_component_cannot_generate_failure():
    snap = diagnostic_snapshot((), component_type="ZYNC")
    component = snap.components[0].model_copy(
        update={"expected": False, "presence": "DISABLED", "resources": ()}
    )
    snap = snap.model_copy(update={"components": (component,)})
    result = diagnose(engine(snap), query(resource_id=None, component_id="component"))
    assert not result.hypotheses and not result.root_cause_candidates


def test_multiple_problems_return_multiple_candidates_and_no_single_winner():
    atoms = (
        evidence("unavailable", "deployment", "unavailable"),
        evidence("failed", "pod", "unavailable").model_copy(
            update={"signals": (SignalCode.CRASH_LOOP,)}
        ),
    )
    result = diagnose(engine(diagnostic_snapshot(atoms)), query(resource_id="deployment"))
    promoted = {c.hypothesis_id for c in result.root_cause_candidates}
    assert hypothesis(result, "WORKLOAD_UNAVAILABLE").id in promoted
    assert hypothesis(result, "POD_CRASH_LOOP").id in promoted


def test_no_data_has_explicit_missing_evidence_and_safe_plan():
    result = diagnose(engine(diagnostic_snapshot(())))
    assert result.hypotheses and not result.root_cause_candidates
    assert all(h.evaluation.status == "BLOCKED_BY_MISSING_EVIDENCE" for h in result.hypotheses)
    assert result.troubleshooting_plan.steps and not result.troubleshooting_plan.executed
    assert all(
        s.safety_class == "READ_ONLY_INSPECTION" and not s.executable
        for s in result.troubleshooting_plan.steps
    )


def test_reported_symptom_never_becomes_observed_evidence():
    result = diagnose(request=query(symptom="API returns HTTP 503; token: PRIVATE"))
    assert (
        result.context.symptom.origin == "user_reported" and not result.context.symptom.evidence_ids
    )
    assert "PRIVATE" not in result.model_dump_json()
    assert result.context.symptom.text not in {
        e.observation for s in result.correlation_result.evidence_sets for e in s.evidence
    }


def test_same_snapshot_has_identical_hypotheses_status_order_and_ids():
    snap = diagnostic_snapshot()
    reverse = snap.model_copy(
        update={
            "evidence": tuple(reversed(snap.evidence)),
            "topology": snap.topology.model_copy(
                update={
                    "nodes": tuple(reversed(snap.topology.nodes)),
                    "edges": tuple(reversed(snap.topology.edges)),
                }
            ),
        }
    )
    assert diagnose(engine(snap)) == diagnose(engine(reverse))
    duplicate = snap.evidence[0].model_copy(
        update={"evidence": snap.evidence[0].evidence.model_copy(update={"id": "z-mirror"})}
    )
    assert diagnose(engine(snap)) == diagnose(
        engine(snap.model_copy(update={"evidence": (*snap.evidence, duplicate)}))
    )


def test_stale_and_unknown_evidence_cannot_promote():
    for seconds in (None, -1000, 90):
        result = diagnose(
            engine(diagnostic_snapshot((evidence("state", "slice", "unavailable", seconds),)))
        )
        assert not result.root_cause_candidates
    result = diagnose(
        request=query(
            time_window=TimeWindow(start=NOW - timedelta(hours=2), end=NOW - timedelta(hours=1))
        )
    )
    assert not result.root_cause_candidates


def test_limits_are_explicit_and_contradictions_survive():
    subject = engine(
        max_hypotheses=1,
        max_candidates=1,
        max_plan_steps=1,
        max_components=1,
        max_evidence_per_hypothesis=1,
    )
    result = diagnose(subject)
    assert (
        len(result.hypotheses) == 1
        and len(result.root_cause_candidates) <= 1
        and len(result.troubleshooting_plan.steps) <= 1
    )
    assert "hypotheses_truncated" in result.warnings
    atoms = (evidence("bad", "slice", "unavailable"), evidence("good", "slice", "ready"))
    result = diagnose(engine(diagnostic_snapshot(atoms), max_evidence_per_hypothesis=1))
    h = hypothesis(result, "SERVICE_NO_READY_ENDPOINT")
    assert h.evaluation.contradicting_evidence == ("good",) and not result.root_cause_candidates


def test_rules_do_not_promote_without_support_even_if_requirement_is_empty(monkeypatch):
    subject = engine()
    monkeypatch.setitem(RULES, RuleKind.ENDPOINT, lambda *args: Assessment())
    assert (
        hypothesis(diagnose(subject), "SERVICE_NO_READY_ENDPOINT").evaluation.status
        == "INCONCLUSIVE"
    )


@pytest.mark.parametrize("code", ["topology_limit_reached", "evidence_truncated"])
def test_truncation_prevents_structural_absence_proof(code):
    from agt_mcp.correlation.models import CorrelationWarning

    snap = diagnostic_snapshot().model_copy(update={"warnings": (CorrelationWarning(code=code),)})
    result = diagnose(engine(snap))
    assert (
        hypothesis(result, "SERVICE_NO_READY_ENDPOINT").evaluation.status
        == "BLOCKED_BY_MISSING_EVIDENCE"
    )
    assert not result.root_cause_candidates


def test_observed_symptom_records_original_evidence_origin():
    result = diagnose()
    assert result.context.symptom.origin == "runtime_observed"
    assert result.context.symptom.evidence_ids


def test_reference_hypothesis_never_asserts_connectivity():
    link = CorrelationLink(
        id="missing-secret",
        source="pod",
        target="unobserved-secret",
        relation="unresolved_not_observed",
        target_kind="Secret",
        provenance=provenance(),
    )
    snap = diagnostic_snapshot().model_copy(update={"links": (link,)})
    h = hypothesis(
        diagnose(engine(snap), query(resource_id="pod")), "CONFIGURATION_REFERENCE_UNRESOLVED"
    )
    assert h.evaluation.status == "BLOCKED_BY_MISSING_EVIDENCE"
    assert h.evaluation.topology_refs == ("missing-secret",)


def test_independent_runtime_support_and_candidate_limit():
    atoms = (
        evidence("one", "service", "unavailable", source="one"),
        evidence("two", "pod", "unavailable", source="two"),
    )
    result = diagnose(engine(diagnostic_snapshot(atoms, component_type="BACKEND_LISTENER")))
    h = hypothesis(result, "BACKEND_COMPONENT_UNAVAILABLE")
    assert h.evaluation.confidence.level == "high"
    result = diagnose(engine(max_candidates=1))
    assert len(result.root_cause_candidates) == 1 and "root_candidates_truncated" in result.warnings


@pytest.mark.parametrize(
    "phase,signal",
    [
        ("Pending", SignalCode.PVC_NOT_BOUND),
        ("Lost", SignalCode.PVC_NOT_BOUND),
        ("Bound", SignalCode.PVC_BOUND),
        ("Unknown", None),
    ],
)
def test_provider_retains_volume_binding_signal(phase, signal):
    from agt_mcp.core.models import Resource
    from agt_mcp.services.correlation_providers import atom

    node = Resource(
        id="volume",
        environment_id="demo",
        kind=ResourceKind.PVC,
        name="volume",
        provider="fixture",
        status=phase,
    )
    item = atom(evidence("volume-state", "volume").evidence, node)
    assert item.signals == ((signal,) if signal else ())
