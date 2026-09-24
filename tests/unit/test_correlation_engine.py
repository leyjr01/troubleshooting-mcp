import asyncio
from datetime import timedelta

import pytest
from pydantic import ValidationError

from agt_mcp.configuration.correlation import CorrelationConfig
from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    ResourceNotFound,
)
from agt_mcp.core.models import ConfidenceLevel
from agt_mcp.correlation.models import (
    CorrelationLink,
    CorrelationQuery,
    CorrelationResult,
    RelationType,
    TimeWindow,
)
from tests.correlation_support import (
    NOW,
    References,
    engine,
    evidence,
    provenance,
    query,
    run,
    snapshot,
)


def test_service_without_endpoints_is_correlation_not_diagnosis():
    result = run()
    assert {
        RelationType.RESOURCE,
        RelationType.TOPOLOGICAL,
        RelationType.STATUS,
        RelationType.COMPONENT,
        RelationType.TEMPORAL,
        RelationType.EVENT,
    } <= {c.relation_type for c in result.candidates}
    assert not any(
        word in result.model_dump() for word in ("findings", "root_cause", "recommendations")
    )
    assert all(c.confidence.level != "high" for c in result.candidates)
    assert all(c.provenance for c in result.candidates)


def test_crash_loop_deployment_and_restart_have_temporal_and_component_links():
    atoms = (
        evidence("deployment-unavailable", "deployment", "unavailable"),
        evidence("crash-loop", "pod", "unavailable", -8),
        evidence("restart", "pod", seconds=-4, kind="event"),
    )
    result = run(engine(snapshot(atoms)), query(resource_id="deployment"))
    assert any(
        set(c.supporting_evidence) == {"deployment-unavailable", "restart"}
        and c.relation_type == RelationType.TEMPORAL
        for c in result.candidates
    )
    assert any(
        c.relation_type == RelationType.COMPONENT and len(c.supporting_evidence) == 3
        for c in result.candidates
    )


def test_ready_endpoint_contradiction_survives_candidate_cap():
    result = run(
        engine(
            snapshot(
                (
                    evidence("unavailable", "service", "unavailable"),
                    evidence("healthy", "slice", "ready"),
                )
            ),
            max_candidates=1,
        )
    )
    candidate = result.candidates[0]
    assert candidate.supporting_evidence == ("unavailable",)
    assert candidate.contradicting_evidence == ("healthy",)
    assert candidate.confidence.level == "low" and candidate.status == "INCONCLUSIVE"
    assert candidate.confidence.contradicting_evidence == ("healthy",)


def test_permutations_are_deterministic_and_sources_unchanged():
    snap = snapshot()
    shuffled = snap.model_copy(
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
    first, second = run(engine(snap)), run(engine(shuffled))
    assert first == second
    assert all(t.provenance == provenance() for t in first.timeline)
    assert [t.timestamp for t in first.timeline] == sorted(t.timestamp for t in first.timeline)
    assert first.context.engine_version == "1.0.0"
    assert first.context.correlated_at == NOW


def test_duplicate_fact_does_not_increase_confidence_or_support():
    snap = snapshot()
    duplicate = snap.evidence[0].model_copy(
        update={"evidence": snap.evidence[0].evidence.model_copy(update={"id": "z-mirror"})}
    )
    assert run(engine(snap)) == run(
        engine(snap.model_copy(update={"evidence": (*snap.evidence, duplicate)}))
    )


@pytest.mark.parametrize(
    "seconds,warning",
    [(None, "missing_timestamp"), (-1000, "stale_evidence"), (60, "future_timestamp")],
)
def test_invalid_timestamp_retained_without_runtime_support(seconds, warning):
    result = run(engine(snapshot((evidence("bad-time", "service", seconds=seconds),))))
    assert warning in {w.code for w in result.warnings}
    assert not result.timeline[0].relevant
    assert result.timeline[0].timestamp == (
        NOW + timedelta(seconds=seconds) if seconds is not None else None
    )
    assert all("bad-time" not in c.supporting_evidence for c in result.candidates)


@pytest.mark.parametrize(
    "depth,expected",
    [(0, {"service"}), (1, {"service", "slice"}), (2, {"service", "slice", "pod"})],
)
def test_depth_bound(depth, expected):
    result = run(request=query(topology_depth=depth))
    assert set(result.evidence_sets[0].resources) == expected


def test_limits_favor_fresh_observations_and_warn():
    snap = snapshot((evidence("old", "service", seconds=-9999), evidence("fresh", "service")))
    result = run(engine(snap, max_events=1, max_resources=1, max_candidates=1))
    assert result.timeline[0].evidence_id == "fresh"
    assert {"evidence_truncated", "topology_limit_reached", "candidates_truncated"} <= {
        w.code for w in result.warnings
    }


@pytest.mark.parametrize(
    "values", [dict(), dict(topology_depth=4, resource_id="x"), dict(resource_id="bad\nname")]
)
def test_invalid_queries(values):
    with pytest.raises(ValidationError):
        CorrelationQuery(**values)


def test_window_validation_and_configuration():
    with pytest.raises(ValidationError):
        TimeWindow(start=NOW, end=NOW)
    with pytest.raises(ValidationError):
        CorrelationConfig(default_lookback_seconds=10, max_lookback_seconds=1)
    for request in (
        query(topology_depth=3),
        query(time_window=TimeWindow(start=NOW - timedelta(days=2), end=NOW)),
        query(time_window=TimeWindow(start=NOW, end=NOW + timedelta(seconds=60))),
    ):
        subject = engine()
        with pytest.raises(ConfigurationError):
            run(subject, request)
        assert subject.provider.calls == 0


def test_historical_window_does_not_claim_current_structural_support():
    result = run(
        request=query(
            time_window=TimeWindow(start=NOW - timedelta(hours=2), end=NOW - timedelta(hours=1))
        )
    )
    assert not result.candidates
    assert "snapshot_outside_window" in {w.code for w in result.warnings}


@pytest.mark.parametrize(
    "missing_query", [query(resource_id="absent"), query(resource_id=None, component_id="absent")]
)
def test_missing_subject(missing_query):
    with pytest.raises(ResourceNotFound):
        run(request=missing_query)


def test_component_and_gateway_roots():
    assert (
        len(
            run(request=query(resource_id=None, component_id="component"))
            .evidence_sets[0]
            .resources
        )
        == 4
    )
    assert (
        len(
            run(request=query(resource_id=None, gateway_id="installation"))
            .evidence_sets[0]
            .resources
        )
        == 4
    )


@pytest.mark.parametrize("field", ["knowledge", "history"])
def test_optional_failure_is_partial_and_preserves_runtime(field):
    subject = engine()
    setattr(subject, field, References(error=RuntimeError("secret exception")))
    result = run(subject, query(include_knowledge=True, include_history=True))
    assert result.evidence_sets[0].evidence and result.candidates
    assert result.status == "PARTIAL"
    assert field + "_unavailable" in {w.code for w in result.warnings}
    assert "secret exception" not in result.model_dump_json()


@pytest.mark.parametrize(
    "field,error",
    [
        ("knowledge", AuthorizationError()),
        ("history", AuthorizationError()),
        ("knowledge", asyncio.CancelledError()),
        ("history", asyncio.CancelledError()),
    ],
)
def test_fatal_or_cancellation_is_not_partial(field, error):
    subject = engine()
    setattr(subject, field, References(error=error))
    with pytest.raises(type(error)):
        run(subject, query(include_knowledge=True, include_history=True))


def test_duplicate_identifier_with_different_observation_is_rejected():
    with pytest.raises(ConfigurationError):
        run(
            engine(
                snapshot(
                    (
                        evidence("same", "service", "ready"),
                        evidence("same", "service", "unavailable"),
                    )
                )
            )
        )


def test_external_dependency_is_only_a_reference():
    link = CorrelationLink(
        id="external",
        source="service",
        target="external-reference",
        relation="describes_connection_to",
        provenance=provenance(),
    )
    result = run(engine(snapshot().model_copy(update={"links": (link,)})))
    matches = [
        c for c in result.candidates if c.relation_type == RelationType.CONFIGURATION_REFERENCE
    ]
    assert matches and not matches[0].supporting_evidence
    assert "connectivity not tested" in matches[0].reasons[0]


def test_high_requires_independent_sources_and_direct_proximity():
    atoms = tuple(
        a.model_copy(
            update={
                "evidence": a.evidence.model_copy(
                    update={
                        "confidence": a.evidence.confidence.model_copy(
                            update={"level": ConfidenceLevel.HIGH}
                        )
                    }
                )
            }
        )
        for a in (evidence("one", "service", source="one"), evidence("two", "slice", source="two"))
    )
    result = run(engine(snapshot(atoms)))
    assert any(c.confidence.level == "high" for c in result.candidates)


@pytest.mark.parametrize(
    "mutation",
    [
        "topology",
        "set",
        "resource",
        "knowledge",
        "support",
        "candidate_ref",
        "confidence",
        "timeline",
    ],
)
def test_result_rejects_broken_lineage(mutation):
    data = run().model_dump(mode="json")
    if mutation == "topology":
        data["context"]["environment_id"] = "prod"
    elif mutation == "set":
        data["evidence_sets"][0]["environment_id"] = "prod"
    elif mutation == "resource":
        data["evidence_sets"][0]["evidence"][0]["resource_id"] = "absent"
    elif mutation == "knowledge":
        data["evidence_sets"][0]["knowledge_refs"] = ["absent"]
    elif mutation == "support":
        data["candidates"][0]["supporting_evidence"] = ["absent"]
    elif mutation == "candidate_ref":
        data["candidates"][0]["topology_refs"] = ["absent"]
    elif mutation == "confidence":
        data["candidates"][0]["confidence"]["supporting_evidence"] = ["absent"]
    else:
        data["timeline"][0]["evidence_id"] = "absent"
    with pytest.raises(ValidationError):
        CorrelationResult.model_validate(data)


def test_bundle_embeds_correlations_without_creating_findings(bundle_data):
    from agt_mcp.evidence.bundle import IncidentBundle

    before = IncidentBundle.model_validate(bundle_data)
    bundle_data["correlations"] = [run().model_dump(mode="json")]
    bundle = IncidentBundle.model_validate(bundle_data)
    assert bundle.findings == before.findings
    assert bundle.incident.root_cause_finding_id == before.incident.root_cause_finding_id
    assert IncidentBundle.model_validate_json(bundle.model_dump_json()) == bundle
    foreign = bundle.correlations[0].model_copy(
        update={
            "context": bundle.correlations[0].context.model_copy(update={"environment_id": "prod"})
        }
    )
    with pytest.raises(ValidationError):
        IncidentBundle(**(before.model_dump() | {"correlations": (foreign,)}))


def test_optional_provider_timeout_retains_runtime():
    class Slow:
        async def retrieve(self, *args):
            await asyncio.sleep(0.1)
            return ()

    subject = engine(enrichment_timeout_seconds=0.01)
    subject.history = Slow()
    result = run(subject, query(include_history=True))
    assert result.evidence_sets[0].evidence and result.status == "PARTIAL"
    assert "history_unavailable" in {w.code for w in result.warnings}


def test_default_window_ends_after_collection():
    from agt_mcp.correlation.engine import SystemClock

    assert SystemClock().now().tzinfo is not None
    subject = engine()
    original = subject.provider.collect

    async def collect(query, context):
        subject.clock.value = NOW + timedelta(seconds=2)
        return await original(query, context)

    subject.provider.collect = collect
    result = run(subject)
    assert result.context.time_window.end == NOW + timedelta(seconds=2)
    assert "snapshot_outside_window" not in {w.code for w in result.warnings}
