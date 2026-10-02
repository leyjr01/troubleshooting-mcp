import asyncio

import pytest

from agt_mcp.configuration.gateway import GatewayDiscoveryConfig
from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    ConnectionError,
    UnsupportedCapabilityError,
)
from agt_mcp.core.execution import ToolName
from agt_mcp.core.operations import Operation
from agt_mcp.gateways.threescale.adapter import ThreeScaleGatewayAdapter
from agt_mcp.gateways.threescale.models import GatewayQuery
from agt_mcp.mcp.context import create_context
from tests.threescale_support import FakeRuntime, config, healthy_resources, snapshot


def setup(resources=None, configuration=None):
    configuration = configuration or config()
    result, _ = snapshot(resources, configuration)
    runtime = FakeRuntime(result)
    adapter = ThreeScaleGatewayAdapter("dev", runtime)
    context = create_context(configuration, ToolName.DISCOVER_GATEWAY, "dev", None)
    return adapter, runtime, context


def test_adapter_lifecycle_and_single_snapshot():
    adapter, runtime, context = setup()

    async def run():
        with pytest.raises(ConnectionError):
            await adapter.discover_installations(context)
        await adapter.connect(context)
        result = await adapter.discover_installations(context)
        assert len(runtime.calls) == 1
        assert all(i.observed_at == runtime.result.observed_at for i in result.installations)
        assert (await adapter.discover_gateway(context)).provider == "threescale"
        assert (await adapter.get_health(context)).status == "healthy"
        assert await adapter.get_routes(context)
        assert await adapter.get_dependencies(context)
        await adapter.close()
        assert not adapter.connected

    asyncio.run(run())


@pytest.mark.parametrize(
    "method", ["get_products", "get_backends", "get_policies", "get_gateway_logs", "trace_request"]
)
def test_admin_api_and_diagnosis_are_unsupported(method):
    adapter, _, context = setup()
    args = ("request", context) if method == "trace_request" else (context,)
    with pytest.raises(UnsupportedCapabilityError):
        asyncio.run(getattr(adapter, method)(*args))
    assert not adapter.capabilities() & {
        Operation.PRODUCTS,
        Operation.BACKENDS,
        Operation.LOGS,
        Operation.TRACE_REQUEST,
    }


@pytest.mark.parametrize("method", ["connect", "discover_installations"])
def test_adapter_environment_denied_before_runtime(method):
    adapter, runtime, context = setup()
    with pytest.raises(AuthorizationError):
        asyncio.run(
            getattr(adapter, method)(context.model_copy(update={"environment_id": "other"}))
        )
    assert not runtime.calls


def test_scoped_namespace_denied_before_runtime():
    adapter, runtime, context = setup()
    adapter.settings = GatewayDiscoveryConfig(namespace="example")

    async def run():
        await adapter.connect(context)
        with pytest.raises(AuthorizationError):
            await adapter.discover_installations(context, GatewayQuery(namespace="other"))

    asyncio.run(run())
    assert not runtime.calls


def test_primary_namespace_does_not_limit_runtime_discovery():
    resources = healthy_resources("apim") + [
        resource
        for resource in healthy_resources("apicast")
        if resource["metadata"]["name"].startswith("apicast-")
    ]
    adapter, runtime, context = setup(resources, config(("apim", "apicast")))
    adapter.settings = GatewayDiscoveryConfig(namespace="apim")

    async def run():
        await adapter.connect(context)
        result = await adapter.discover_installations(context)
        assert len(result.installations) == 1
        assert result.installations[0].namespace == "apim"

    asyncio.run(run())
    assert runtime.calls[0][1].namespace is None


@pytest.mark.parametrize("multiple", [True, False])
def test_legacy_single_gateway_port_rejects_missing_or_ambiguous(multiple):
    adapter, _, context = setup(
        healthy_resources("one") + healthy_resources("two") if multiple else [],
        config(("one", "two")),
    )

    async def run():
        await adapter.connect(context)
        with pytest.raises(ConfigurationError):
            await adapter.discover_gateway(context)

    asyncio.run(run())


def test_operation_context_adapts_to_runtime_deadline():
    from agt_mcp.core.operations import OperationContext

    adapter, runtime, context = setup()
    plain = OperationContext.model_validate(
        {k: v for k, v in context.model_dump().items() if k in OperationContext.model_fields}
    )

    async def run():
        await adapter.connect(plain)
        await adapter.discover_installations(plain)

    asyncio.run(run())
    assert runtime.calls[0][0].deadline > 0


@pytest.mark.parametrize("field", ["environment", "namespace"])
def test_misbound_runtime_result_fails_closed(field):
    adapter, runtime, context = setup()
    if field == "environment":
        runtime.result = runtime.result.model_copy(update={"environment_id": "other"})

    async def run():
        await adapter.connect(context)
        with pytest.raises(AuthorizationError):
            await adapter.discover_installations(
                context, GatewayQuery(namespace="other" if field == "namespace" else "example")
            )

    asyncio.run(run())
