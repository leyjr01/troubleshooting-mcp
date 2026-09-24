import asyncio
from types import SimpleNamespace

import pytest

from agt_mcp.core.errors import AuthorizationError, ConfigurationError, ResourceNotFound
from agt_mcp.core.execution import ToolName
from agt_mcp.core.models import Resource
from agt_mcp.correlation.models import CorrelationQuery
from agt_mcp.mcp.context import create_context
from agt_mcp.services.correlation_providers import RuntimeCorrelationProvider, atom
from tests.correlation_support import evidence
from tests.integration.test_correlation_mcp import setup
from tests.threescale_support import config, healthy_resources


@pytest.mark.parametrize(
    "kind,details,expected",
    [
        ("endpointslice", {"endpoints": [{"ready": True}]}, "ready"),
        ("endpointslice", {"endpoints": [{"ready": False}]}, "unavailable"),
        ("endpointslice", {"endpoints": []}, "unknown"),
        ("endpointslice", {"endpoints": "bad"}, "unknown"),
        ("pod", {"containers": [{"ready": True}]}, "ready"),
        (
            "pod",
            {"containers": [{"ready": False, "waiting_reason": "CrashLoopBackOff"}]},
            "unavailable",
        ),
        ("pod", {"containers": []}, "unknown"),
        ("pod", {"containers": "bad"}, "unknown"),
        ("deployment", {"availableReplicas": 1}, "ready"),
        ("deployment", {"unavailableReplicas": 1}, "unavailable"),
        ("deployment", {}, "unknown"),
        ("service", {}, "unknown"),
    ],
)
def test_canonical_status_projection(kind, details, expected):
    resource = Resource(
        id="r", environment_id="demo", name="r", kind=kind, provider="fixture", details=details
    )
    assert atom(evidence("e", "r").evidence, resource).state == expected


@pytest.mark.parametrize("origin,missing", [("source", False), ("retrieval_fallback", True)])
def test_event_timestamp_origin(origin, missing):
    resource = Resource(id="r", environment_id="demo", name="r", kind="pod", provider="fixture")
    item = evidence("e", "r").evidence.model_copy(
        update={"metadata": {"evidence_kind": "event", "timestamp_origin": origin}}
    )
    result = atom(item, resource)
    assert (result.occurred_at is None) == missing and result.kind == "event"


def test_service_no_ready_endpoints_signal():
    resource = Resource(id="r", environment_id="demo", name="r", kind="service", provider="fixture")
    item = evidence("e", "r").evidence.model_copy(
        update={"metadata": {"signal": "no_ready_endpoints"}}
    )
    assert atom(item, resource).state == "unavailable"


def test_runtime_only_provider_and_resource_outside_installation():
    runtime, adapter, _ = setup()
    execution = create_context(runtime.configuration, ToolName.CORRELATE_EVIDENCE, "dev", None)
    asyncio.run(adapter.connect(execution))
    provider = runtime.correlation.engine.provider
    outside = next(
        n.id for n in adapter.runtime.result.topology.nodes if n.name == "backend-payments"
    )
    snap = asyncio.run(provider.collect(CorrelationQuery(resource_id=outside), execution))
    assert snap.installation_id is None
    assert outside in {n.id for n in snap.topology.nodes}
    gateways = SimpleNamespace(adapters=lambda env: {})
    provider = RuntimeCorrelationProvider(
        SimpleNamespace(adapters={"dev": adapter.runtime}), gateways
    )
    result = asyncio.run(provider.collect(CorrelationQuery(resource_id=outside), execution))
    assert result.evidence and result.components == ()
    for invalid in (CorrelationQuery(gateway_id="absent"), CorrelationQuery(component_id="absent")):
        with pytest.raises(ResourceNotFound):
            asyncio.run(provider.collect(invalid, execution))
    provider.runtime.adapters.clear()
    with pytest.raises(ResourceNotFound):
        asyncio.run(provider.collect(CorrelationQuery(resource_id=outside), execution))


@pytest.mark.parametrize(
    "case",
    [
        "ambiguous_installation",
        "ambiguous_binding",
        "missing_gateway",
        "missing_component",
        "namespace",
        "environment",
    ],
)
def test_provider_scope_rejections(case):
    configuration = config(("one", "two")) if case == "ambiguous_installation" else config()
    resources = (
        healthy_resources("one") + healthy_resources("two")
        if case == "ambiguous_installation"
        else None
    )
    runtime, adapter, subject = setup(resources, configuration)
    execution = create_context(configuration, ToolName.CORRELATE_EVIDENCE, "dev", None)
    asyncio.run(adapter.connect(execution))
    provider = runtime.correlation.engine.provider
    request = CorrelationQuery(resource_id=subject)
    error = ConfigurationError
    if case == "ambiguous_installation":
        request = CorrelationQuery(gateway_id="threescale-auto")
    elif case == "ambiguous_binding":
        provider.gateways = SimpleNamespace(
            adapters=lambda env: {"one": adapter, "two": adapter},
            registry=SimpleNamespace(entries=lambda: ()),
        )
    elif case == "missing_gateway":
        request, error = CorrelationQuery(gateway_id="absent"), ResourceNotFound
    elif case == "missing_component":
        request, error = CorrelationQuery(component_id="absent"), ResourceNotFound
    elif case == "namespace":
        request, error = (
            CorrelationQuery(resource_id=subject, namespace="other"),
            AuthorizationError,
        )
    else:
        adapter.runtime.result = adapter.runtime.result.model_copy(
            update={"environment_id": "prod"}
        )
        error = AuthorizationError
    with pytest.raises(error):
        asyncio.run(provider.collect(request, execution))


def test_generic_provider_rejects_cross_environment_and_namespace():
    runtime, adapter, subject = setup()
    execution = create_context(runtime.configuration, ToolName.CORRELATE_EVIDENCE, "dev", None)
    provider = RuntimeCorrelationProvider(
        SimpleNamespace(adapters={"dev": adapter.runtime}), SimpleNamespace(adapters=lambda env: {})
    )
    with pytest.raises(AuthorizationError):
        asyncio.run(
            provider.collect(CorrelationQuery(resource_id=subject, namespace="other"), execution)
        )
    adapter.runtime.result = adapter.runtime.result.model_copy(update={"environment_id": "prod"})
    with pytest.raises(AuthorizationError):
        asyncio.run(provider.collect(CorrelationQuery(resource_id=subject), execution))
