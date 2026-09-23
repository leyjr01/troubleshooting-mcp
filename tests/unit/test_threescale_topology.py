import copy

import pytest

from agt_mcp.gateways.threescale.classifier import ThreeScaleComponentClassifier
from agt_mcp.gateways.threescale.models import ComponentType as C
from tests.threescale_support import healthy_resources, snapshot


def test_semantic_graph_preserves_runtime_route_chain_and_provenance():
    snap, _ = snapshot()
    installation = ThreeScaleComponentClassifier(snap).classify()[0]
    component = next(c for c in installation.components if c.type == C.APICAST_PRODUCTION)
    nodes = {n.id: n for n in snap.topology.nodes}
    kinds = {nodes[r].reference.kind for r in component.runtime_resources}
    assert {"Deployment", "Pod", "Route", "Service", "EndpointSlice", "ConfigMap"} <= kinds
    assert all("staging" not in nodes[r].name for r in component.runtime_resources)
    ids = (
        set(installation.runtime_resources)
        | {installation.id}
        | {c.id for c in installation.components}
    )
    assert all(e.source in ids and e.target in ids for e in installation.relationships)
    assert all(
        e.provenance.environment_id == "dev" and e.mechanism for e in installation.relationships
    )
    relations = {e.relationship.value for e in installation.relationships}
    assert {
        "manages",
        "component_of",
        "exposes",
        "configured_by",
        "uses_storage",
        "uses_queue",
        "describes_connection_to",
    } <= relations
    assert (
        not set(c.runtime_resources[0] for c in installation.components if c.runtime_resources)
        - ids
    )


def test_runtime_sorting_does_not_change_semantic_output():
    snap, _ = snapshot()
    first = ThreeScaleComponentClassifier(snap).classify()
    shuffled = snap.model_copy(
        update={
            "topology": snap.topology.model_copy(
                update={
                    "nodes": tuple(reversed(snap.topology.nodes)),
                    "edges": tuple(reversed(snap.topology.edges)),
                }
            )
        }
    )
    assert first == ThreeScaleComponentClassifier(shuffled).classify()


@pytest.mark.parametrize("broken", ["missing-service", "unready-endpoint"])
def test_runtime_warnings_are_not_causal_diagnoses(broken):
    resources = healthy_resources()
    if broken == "missing-service":
        resources = [
            r
            for r in resources
            if not (r["kind"] == "Service" and r["metadata"]["name"] == "apicast-production")
        ]
    else:
        for r in resources:
            if r["kind"] == "EndpointSlice":
                r["endpoints"][0]["conditions"]["ready"] = False
    snap, _ = snapshot(resources)
    installation = ThreeScaleComponentClassifier(snap).classify()[0]
    assert "root_cause" not in installation.model_dump_json()
    if broken == "missing-service":
        assert snap.unresolved
    else:
        assert any(
            "no ready runtime endpoints" in e.observation for e in installation.runtime_evidence
        )


@pytest.mark.parametrize("max_edges,max_components", [(1, 200), (1000, 2)])
def test_semantic_limits_warn_and_keep_graph_valid(max_edges, max_components):
    snap, _ = snapshot()
    installation = ThreeScaleComponentClassifier(
        snap, max_edges=max_edges, max_components=max_components
    ).classify()[0]
    assert len(installation.relationships) <= max_edges
    assert len(installation.components) <= max_components
    assert any(w.code == "partial_topology" for w in installation.warnings)


def test_ephemeral_pod_recreation_does_not_change_component_identity():
    resources = healthy_resources()
    first, _ = snapshot(resources)
    changed = copy.deepcopy(resources)
    for r in changed:
        if r["kind"] == "Pod":
            r["metadata"]["uid"] += "-new"
    second, _ = snapshot(changed)
    a = ThreeScaleComponentClassifier(first).classify()[0]
    b = ThreeScaleComponentClassifier(second).classify()[0]
    assert a.id == b.id
    assert [c.id for c in a.components] == [c.id for c in b.components]
