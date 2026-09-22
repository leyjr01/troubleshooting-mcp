import ast
import asyncio
import copy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import yaml
from pydantic import ValidationError

from agt_mcp.configuration.loader import load_configuration
from agt_mcp.configuration.runtime import CustomResourceSpec
from agt_mcp.core.errors import ConfigurationError, SanitizationError
from agt_mcp.core.execution import Capability, ToolName
from agt_mcp.core.runtime import RuntimeQuery
from agt_mcp.datasources.kubernetes.adapter import KubernetesRuntimeAdapter
from agt_mcp.datasources.kubernetes.catalog import TYPES
from agt_mcp.mcp.bootstrap import build_runtime
from agt_mcp.mcp.context import create_context
from tests.runtime_support import FakeKubernetesClient, runtime_configuration
from tests.unit.test_kubernetes_adapter import discover

ROOT = Path(__file__).resolve().parents[2]


def test_rbac_examples_only_grant_explicit_reads():
    manifests = list((ROOT / "config/rbac").glob("*.yaml"))
    assert len(manifests) == 3
    for path in manifests:
        doc = yaml.safe_load(path.read_text())
        assert doc["kind"] in {"Role", "ClusterRole"}
        for rule in doc["rules"]:
            assert set(rule["verbs"]) <= {"get", "list"}
            assert "*" not in rule["apiGroups"]
            assert all(r not in {"*", "secrets"} and "/" not in r for r in rule["resources"])


def test_sdk_and_framework_import_boundaries():
    for path in (ROOT / "src/agt_mcp").rglob("*.py"):
        imports = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imports.extend(n.name for n in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
        if any(n.startswith("kubernetes") for n in imports):
            assert path == ROOT / "src/agt_mcp/datasources/kubernetes/client.py"
        if any(n.startswith("fastmcp") for n in imports):
            assert "mcp" in path.relative_to(ROOT / "src/agt_mcp").parts


def test_runtime_example_validates_without_credentials():
    config = load_configuration([ROOT / "config/server/kubernetes.example.yaml"], environ={})
    assert config.environments[0].runtime.discovery.cluster_scoped is False
    assert Capability.RESOURCE_READ in config.mcp.server.authorization.permissions


@pytest.mark.parametrize(
    "plural,group",
    [
        ("secrets", "example.io"),
        ("tokenreviews", "example.io"),
        ("subjectaccessreviews", "example.io"),
        ("widgets", "core"),
    ],
)
def test_custom_resource_allowlist_rejects_sensitive_bindings(plural, group):
    with pytest.raises(ValidationError):
        CustomResourceSpec(group=group, version="v1", plural=plural, kind="Widget")


@pytest.mark.parametrize("method", ["inspect", "events"])
@pytest.mark.parametrize(
    "field,value",
    [("namespace", "other"), ("name", "other"), ("kind", "Secret"), ("apiVersion", "other/v1")],
)
def test_wrong_api_response_is_never_exposed(method, field, value):
    config = runtime_configuration()
    backend = FakeKubernetesClient()
    raw = copy.deepcopy(next(r for r in backend.resources if r["kind"] == "Pod"))
    if field in {"namespace", "name"}:
        raw["metadata"][field] = value
    else:
        raw[field] = value
    backend.read_resource = AsyncMock(return_value=raw)
    adapter = KubernetesRuntimeAdapter(config.environments[0], backend)
    context = create_context(config, ToolName.INSPECT_RESOURCE, "dev", None)
    with pytest.raises(SanitizationError):
        asyncio.run(
            getattr(adapter, method)(
                context, RuntimeQuery(namespace="example", kind="Pod", name="app-pod")
            )
        )


@pytest.mark.parametrize("items", ["invalid", [None], [123]])
def test_malformed_list_is_safe(items):
    config = runtime_configuration()
    backend = FakeKubernetesClient()
    backend.list_resources = AsyncMock(return_value={"items": items})
    snapshot = discover(backend, config)
    assert all(c.status == "unavailable" for c in snapshot.categories)
    assert not snapshot.topology.nodes


def test_namespace_spoof_in_list_is_rejected():
    backend = FakeKubernetesClient()
    raw = copy.deepcopy(next(r for r in backend.resources if r["kind"] == "Pod"))
    raw["metadata"]["namespace"] = "forbidden"
    backend.list_resources = AsyncMock(return_value={"items": [raw]})
    snapshot = discover(backend)
    assert not snapshot.topology.nodes
    assert any(w.code == "invalid_resource" for w in snapshot.warnings)


@pytest.mark.parametrize(
    "cursor", ["repeat", 123, "x" * 4097], ids=["repeat", "non-string", "oversize"]
)
def test_bad_pagination_is_bounded(cursor):
    config = runtime_configuration()
    backend = FakeKubernetesClient()
    backend.list_resources = AsyncMock(return_value={"items": [], "metadata": {"continue": cursor}})
    adapter = KubernetesRuntimeAdapter(config.environments[0], backend)
    context = create_context(config, ToolName.DISCOVER_ENVIRONMENT, "dev", None)
    items, state = asyncio.run(adapter._collect(TYPES[0], "example", context, 3))
    assert items == [] and state == "truncated"
    assert backend.list_resources.await_count <= 2


def test_configmap_byte_limit_and_invalid_owner():
    config = runtime_configuration(
        discovery={"namespaces": {"include": ["example"]}, "limits": {"max_configmap_bytes": 1}}
    )
    backend = FakeKubernetesClient()
    pod = next(r for r in backend.resources if r["kind"] == "Pod")
    pod["metadata"]["ownerReferences"][0].pop("uid")
    snapshot = discover(backend, config)
    assert {w.code for w in snapshot.warnings} >= {"invalid_resource", "truncated_discovery"}
    pod_id = next(n.id for n in snapshot.topology.nodes if n.name == "app-pod")
    assert not any(
        e.target == pod_id and e.relationship.value == "owns" for e in snapshot.topology.edges
    )
    assert "CONFIGMAP-SECRET" not in snapshot.model_dump_json()


def test_disabled_runtime_has_no_advertised_capabilities():
    config = runtime_configuration()
    environment = config.environments[0].model_copy(update={"enabled": False})
    runtime = build_runtime(config.model_copy(update={"environments": (environment,)}))
    assert not runtime.discovery.adapters
    assert Capability.RUNTIME_DISCOVER not in runtime.available_capabilities("dev")


def test_configured_depth_limit_and_ambiguous_namespace():
    config = runtime_configuration(
        discovery={
            "namespaces": {"include": ["example", "second"]},
            "limits": {"max_topology_depth": 1},
        }
    )
    adapter = KubernetesRuntimeAdapter(config.environments[0], FakeKubernetesClient())
    context = create_context(config, ToolName.INSPECT_RESOURCE, "dev", None)
    for query in [RuntimeQuery(depth=2), RuntimeQuery(kind="Pod", name="app-pod")]:
        with pytest.raises(ConfigurationError):
            asyncio.run(adapter.inspect(context, query))


def test_event_budget_reports_truncation_without_losing_first_event():
    config = runtime_configuration(
        discovery={"namespaces": {"include": ["example"]}, "limits": {"max_events": 1}}
    )
    backend = FakeKubernetesClient()
    event = copy.deepcopy(next(r for r in backend.resources if r["kind"] == "Event"))
    event["metadata"]["name"] = "second-event"
    event["metadata"]["uid"] = "second-event"
    backend.resources.append(event)
    adapter = KubernetesRuntimeAdapter(config.environments[0], backend)
    context = create_context(config, ToolName.INSPECT_EVENTS, "dev", None)
    result = asyncio.run(
        adapter.events(
            context, RuntimeQuery(namespace="example", kind="Pod", name="app-pod", limit=200)
        )
    )
    assert len(result.evidence) == result.limit == 1
    assert result.truncated
