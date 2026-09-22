import asyncio
import copy
from datetime import UTC, datetime

import pytest

from agt_mcp.core.errors import (
    AuthenticationError,
    AuthorizationError,
    DataSourceUnavailable,
    ResourceNotFound,
    TimeoutError,
)
from agt_mcp.core.execution import ToolName
from agt_mcp.core.runtime import RuntimeQuery
from agt_mcp.datasources.kubernetes.adapter import KubernetesRuntimeAdapter
from agt_mcp.datasources.kubernetes.graph import matches
from agt_mcp.datasources.kubernetes.mapping import normalize, timestamp
from agt_mcp.mcp.context import create_context
from agt_mcp.services.discovery import RuntimeDiscoveryService
from tests.runtime_support import FakeKubernetesClient, runtime_configuration


def discover(client=None, config=None, query=None):
    config = config or runtime_configuration()
    client = client or FakeKubernetesClient()
    adapter = KubernetesRuntimeAdapter(config.environments[0], client)
    context = create_context(config, ToolName.DISCOVER_ENVIRONMENT, "dev", None)
    return asyncio.run(adapter.discover(context, query or RuntimeQuery(namespace="example")))


def test_complete_mapping_and_declared_topology():
    snapshot = discover()
    assert len(snapshot.categories) == 18
    assert all(c.status == "completed" for c in snapshot.categories)
    pairs = {
        (
            next(n.name for n in snapshot.topology.nodes if n.id == e.source),
            e.relationship.value,
            next(n.name for n in snapshot.topology.nodes if n.id == e.target),
        )
        for e in snapshot.topology.edges
    }
    expected = {
        ("app", "owns", "app-rs"),
        ("app-rs", "owns", "app-pod"),
        ("app", "selects", "app-pod"),
        ("app", "has_endpointslice", "app-slice"),
        ("app-slice", "targets", "app-pod"),
        ("app", "has_endpoint", "app-pod"),
        ("app-route", "routes_to", "app"),
        ("app-ingress", "routes_to", "app"),
        ("app-pod", "references_configmap", "settings"),
        ("app-pod", "references_secret", "db-secret"),
        ("app-pod", "mounts", "disk"),
        ("disk", "bound_to", "pv-disk"),
        ("app-pod", "uses_service_account", "runtime-sa"),
        ("app-policy", "selects", "app-pod"),
    }
    assert expected <= pairs
    assert all(
        e.source_of_information.environment_id == "dev" and e.metadata["mechanism"]
        for e in snapshot.topology.edges
    )
    assert len({n.id for n in snapshot.topology.nodes}) == len(snapshot.topology.nodes)
    assert any("CrashLoopBackOff" in e.observation for e in snapshot.evidence)
    assert any(e.observation == "Service has no ready runtime endpoints" for e in snapshot.evidence)
    unresolved = next(r for r in snapshot.unresolved if r.target.name == "missing-service")
    assert unresolved.resolution == "not_found"
    assert all(n.name != "missing-service" for n in snapshot.topology.nodes)
    endpoint = next(n for n in snapshot.topology.nodes if n.name == "app-slice")
    assert endpoint.details["endpoints"][0]["addresses"] == ["10.0.0.5"]
    assert endpoint.details["endpoints"][0]["ready"] is True
    assert all(e.timestamp.tzinfo for e in snapshot.evidence)


@pytest.mark.parametrize(
    "error,status",
    [
        (AuthorizationError, "forbidden"),
        (ResourceNotFound, "unsupported"),
        (DataSourceUnavailable, "unavailable"),
        (TimeoutError, "unavailable"),
    ],
)
def test_partial_discovery(error, status):
    client = FakeKubernetesClient()
    client.forbidden["NetworkPolicy"] = error
    snapshot = discover(client)
    assert next(c for c in snapshot.categories if c.kind == "NetworkPolicy").status == status
    assert any(n.name == "app-pod" for n in snapshot.topology.nodes)


def test_authentication_failure_is_fatal():
    client = FakeKubernetesClient()
    client.forbidden["Pod"] = AuthenticationError
    with pytest.raises(AuthenticationError):
        discover(client)


@pytest.mark.parametrize("error", [AuthorizationError, DataSourceUnavailable, TimeoutError])
def test_api_discovery_partial(error):
    client = FakeKubernetesClient()
    client.api_errors["networking.k8s.io/v1"] = error
    snapshot = discover(client)
    assert snapshot.warnings
    assert "v1" in snapshot.capabilities


def test_kubernetes_without_openshift_and_cluster_scope():
    config = runtime_configuration(
        provider="kubernetes", discovery={"namespaces": {"include": ["example"]}}
    )
    client = FakeKubernetesClient()
    client.api_errors["route.openshift.io/v1"] = ResourceNotFound
    snapshot = discover(client, config)
    assert all(
        c.kind not in {"Route", "Namespace", "PersistentVolume", "CustomResourceDefinition"}
        for c in snapshot.categories
    )
    assert any(
        r.target.name == "pv-disk" and r.resolution == "not_observed" for r in snapshot.unresolved
    )
    assert all(call[2] is not None for call in client.calls if call[0] == "list")


def test_pagination_truncation_and_resource_budget():
    config = runtime_configuration(
        discovery={
            "namespaces": {"include": ["example"]},
            "limits": {
                "page_size": 1,
                "max_resources_per_type": 1,
                "max_topology_nodes": 10,
                "max_relationships": 2,
            },
        }
    )
    client = FakeKubernetesClient()
    snapshot = discover(client, config)
    assert len(snapshot.topology.nodes) <= 10
    assert len(snapshot.topology.edges) <= 2
    assert any(c.status == "truncated" for c in snapshot.categories)
    assert any(w.code == "truncated_discovery" for w in snapshot.warnings)
    config = runtime_configuration(
        discovery={"namespaces": {"include": ["example"]}, "limits": {"page_size": 1}}
    )
    client = FakeKubernetesClient()
    discover(client, config)
    assert any(c[0] == "list" and c[1] == "Deployment" and c[4] == "1" for c in client.calls)


def test_namespace_limit_and_exclusion():
    config = runtime_configuration(
        discovery={
            "namespaces": {"include": ["a", "example", "z"], "exclude": ["a"]},
            "limits": {"max_namespaces": 1},
        }
    )
    snapshot = discover(config=config, query=RuntimeQuery())
    assert snapshot.namespaces == ("example",)
    assert any(w.code == "truncated_discovery" for w in snapshot.warnings)


def test_uid_identity_and_ownership():
    client = FakeKubernetesClient()
    pod = next(r for r in client.resources if r["kind"] == "Pod")
    original = normalize(pod, "dev", "cluster")
    pod["metadata"]["uid"] = "replacement-uid"
    assert normalize(pod, "dev", "cluster").id != original.id
    pod["metadata"]["ownerReferences"][0]["uid"] = "stale-owner"
    snapshot = discover(client)
    pod_id = next(n.id for n in snapshot.topology.nodes if n.name == "app-pod")
    assert not any(
        e.relationship.value == "owns" and e.target == pod_id for e in snapshot.topology.edges
    )
    assert any(r.target.uid == "stale-owner" for r in snapshot.unresolved)


@pytest.mark.parametrize(
    "selector,labels,expected",
    [
        ({}, {}, True),
        ({"matchLabels": {"a": "b"}}, {}, False),
        ({"matchExpressions": [{"key": "a", "operator": "In", "values": ["b"]}]}, {"a": "b"}, True),
        ({"matchExpressions": [{"key": "a", "operator": "In", "values": ["b"]}]}, {}, False),
        (
            {"matchExpressions": [{"key": "a", "operator": "NotIn", "values": ["b"]}]},
            {"a": "b"},
            False,
        ),
        ({"matchExpressions": [{"key": "a", "operator": "NotIn", "values": ["b"]}]}, {}, True),
        ({"matchExpressions": [{"key": "a", "operator": "Exists"}]}, {}, False),
        ({"matchExpressions": [{"key": "a", "operator": "DoesNotExist"}]}, {"a": "b"}, False),
        ({"matchExpressions": [{"key": "a", "operator": "unknown"}]}, {}, False),
    ],
)
def test_selector_semantics(selector, labels, expected):
    assert matches(selector, labels) is expected


def test_events_are_sorted_bounded_and_uid_scoped():
    client = FakeKubernetesClient()
    event = next(r for r in client.resources if r["kind"] == "Event")
    another = copy.deepcopy(event)
    another["metadata"]["uid"] = "other-event"
    another["metadata"]["name"] = "other-event"
    another["lastTimestamp"] = "2026-09-20T12:00:00Z"
    client.resources.append(another)
    config = runtime_configuration()
    adapter = KubernetesRuntimeAdapter(config.environments[0], client)
    ctx = create_context(config, ToolName.INSPECT_EVENTS, "dev", None)
    result = asyncio.run(
        adapter.events(
            ctx,
            RuntimeQuery(
                namespace="example",
                kind="Pod",
                name="app-pod",
                since=datetime(2026, 9, 21, tzinfo=UTC),
            ),
        )
    )
    assert len(result.evidence) == 1
    assert result.evidence[0].type.value == "observation"
    assert not result.truncated
    assert any(c[0] == "list" and c[5] == "involvedObject.uid=uid-app-pod" for c in client.calls)


@pytest.mark.parametrize(
    "operation",
    [ToolName.INSPECT_RESOURCE, ToolName.FIND_RELATED_RESOURCES, ToolName.GET_RESOURCE_TOPOLOGY],
)
def test_inspection_and_subgraph(operation):
    config = runtime_configuration()
    adapter = KubernetesRuntimeAdapter(config.environments[0], FakeKubernetesClient())
    service = RuntimeDiscoveryService({"dev": adapter})
    ctx = create_context(config, operation, "dev", None)
    result = asyncio.run(
        service.execute(
            ctx, RuntimeQuery(namespace="example", kind="Deployment", name="app", depth=3, limit=3)
        )
    )
    assert len(result["topology"]["nodes"]) <= 3
    assert result["truncated"]


@pytest.mark.parametrize("value", [None, "not-a-date", "2026-09-21T12:00:00"])
def test_naive_invalid_dates_use_observation_time(value):
    fallback = datetime.now(UTC)
    assert timestamp(value, fallback) == fallback
