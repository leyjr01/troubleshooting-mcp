import asyncio

import pytest
from pydantic import ValidationError

from agt_mcp.core.errors import AuthorizationError, UnsupportedCapabilityError
from agt_mcp.core.execution import ToolName
from agt_mcp.core.runtime import RuntimeQuery
from agt_mcp.datasources.kubernetes.adapter import KubernetesRuntimeAdapter
from agt_mcp.mcp.context import create_context
from tests.runtime_support import FakeKubernetesClient, runtime_configuration


def test_secrets_and_injection_never_leave_adapter(caplog):
    config = runtime_configuration()
    client = FakeKubernetesClient()
    pod = next(r for r in client.resources if r["kind"] == "Pod")
    pod["metadata"]["annotations"]["oversized"] = "sensitive" * 100000
    adapter = KubernetesRuntimeAdapter(config.environments[0], client)
    ctx = create_context(config, ToolName.DISCOVER_ENVIRONMENT, "dev", None)
    snapshot = asyncio.run(adapter.discover(ctx, RuntimeQuery(namespace="example")))
    serialized = snapshot.model_dump_json() + caplog.text
    for sensitive in (
        "Bearer synthetic-secret",
        "PRIVATE-KEY-SYNTHETIC",
        "CONFIGMAP-SECRET-SYNTHETIC",
        "CUSTOM-SECRET-SYNTHETIC",
        "Ignore previous instructions",
        "sensitive-key",
        "U0VDUkVU",
    ):
        assert sensitive not in serialized
    assert len(serialized) < 100000
    references = [n for n in snapshot.topology.nodes if n.kind.value == "secret_reference"]
    assert len(references) >= 5
    assert all(n.details["content_read"] is False for n in references)
    assert not any(c[0] in {"read", "list"} and c[1] == "Secret" for c in client.calls)
    assert "root_cause" not in serialized


@pytest.mark.parametrize("kind", ["environment", "namespace", "secret", "cluster-scope"])
def test_scope_and_forbidden_kinds(kind):
    config = runtime_configuration(
        discovery={"namespaces": {"include": ["example"], "exclude": ["excluded"]}}
    )
    client = FakeKubernetesClient()
    adapter = KubernetesRuntimeAdapter(config.environments[0], client)
    ctx = create_context(
        config, ToolName.INSPECT_RESOURCE, "other" if kind == "environment" else "dev", None
    )
    query = RuntimeQuery(
        namespace="forbidden" if kind == "namespace" else "example",
        kind="Secret" if kind == "secret" else "Namespace" if kind == "cluster-scope" else "Pod",
        name="app-pod",
    )
    with pytest.raises((AuthorizationError, UnsupportedCapabilityError)):
        asyncio.run(adapter.inspect(ctx, query))
    assert not any(c[0] == "read" for c in client.calls)
    if kind in {"environment", "namespace"}:
        assert not client.opened


@pytest.mark.parametrize("value", ["../secrets", "x?watch=true", "x\ny", "x/exec", "*", "X"])
def test_no_path_injection(value):
    with pytest.raises(ValidationError):
        RuntimeQuery(namespace=value, name=value)


def test_no_secret_or_write_verbs_in_sdk_catalog():
    from agt_mcp.datasources.kubernetes.catalog import TYPES

    assert all(t.plural != "secrets" for t in TYPES)
    assert all("/" not in t.plural for t in TYPES)
