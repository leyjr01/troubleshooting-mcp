import ast
import asyncio
from pathlib import Path
from time import monotonic

import pytest
from pydantic import ValidationError

from agt_mcp.configuration.loader import load_configuration
from agt_mcp.configuration.models import Configuration
from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    ConnectionError,
    DataSourceUnavailable,
    GatewayUnavailable,
    TimeoutError,
    UnsupportedCapabilityError,
)
from agt_mcp.core.execution import Capability, ToolName
from agt_mcp.core.operations import Query
from agt_mcp.mcp.bootstrap import build_runtime
from agt_mcp.mcp.context import create_context
from agt_mcp.mcp.dispatch import Dispatcher
from agt_mcp.services.registry import AdapterEntry

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def configuration():
    return load_configuration([ROOT / "config/server/local.example.yaml"], environ={})


@pytest.mark.parametrize(
    "field,value",
    [
        ("host", "0.0.0.0"),
        ("port", 0),
        ("transport", "sse"),
        ("log_level", "DEBUG"),
        ("request_timeout_seconds", 0),
        ("request_timeout_seconds", float("nan")),
    ],
)
def test_reject_unsafe_server_config(configuration, field, value):
    data = configuration.model_dump()
    data["mcp"]["server"][field] = value
    with pytest.raises(ValidationError):
        Configuration.model_validate(data)


@pytest.mark.parametrize(
    "kind",
    [
        "missing_environment",
        "grant_scope",
        "source_scope",
        "gateway_scope",
        "real_source",
        "real_gateway",
        "credentials",
    ],
)
def test_bootstrap_rejects_nonlocal_configuration(configuration, kind):
    data = configuration.model_dump()
    if kind == "missing_environment":
        data["environments"] = []
    elif kind == "grant_scope":
        data["mcp"]["server"]["authorization"]["environment_ids"] = ["other"]
    elif kind == "source_scope":
        data["datasources"][0]["environment_id"] = "other"
        data["gateways"] = []
    elif kind == "gateway_scope":
        data["datasources"][0]["environment_id"] = "other"
        data["gateways"][0]["environment_id"] = "other"
    elif kind == "real_source":
        data["datasources"][0]["provider"] = "postgresql"
    elif kind == "real_gateway":
        data["gateways"][0]["adapter"] = "threescale"
    else:
        data["datasources"][0]["credentials"] = {
            "provider": "environment",
            "reference": "UNUSED",
            "environment_id": "demo",
        }
    with pytest.raises(ConfigurationError):
        build_runtime(Configuration.model_validate(data))


def test_registry_duplicate_scope_and_seal(configuration):
    runtime = build_runtime(configuration)
    entry = runtime.gateways.entries()[0]
    with pytest.raises(ConfigurationError):
        runtime.gateways.register(entry)
    with pytest.raises(AuthorizationError):
        runtime.gateways.resolve(entry.id, "other")
    runtime.gateways.seal()
    with pytest.raises(ConfigurationError):
        runtime.gateways.register(
            AdapterEntry(id="new", environment_id="demo", adapter=entry.adapter)
        )


def test_runtime_timeout_failure_and_cancel(configuration, caplog):
    runtime = build_runtime(configuration)
    gateway = runtime.gateways.resolve("gateway-01", "demo")
    dispatcher = Dispatcher(runtime)
    context = create_context(configuration, ToolName.DISCOVER_GATEWAY, None, None)

    async def scenario():
        with pytest.raises(ConnectionError):
            await runtime.execute(context, "gateway-01")
        async with runtime.lifespan():
            gateway.fail = True
            result = await dispatcher.call(ToolName.DISCOVER_GATEWAY, resource_id="gateway-01")
            assert result.error == "gateway_unavailable"
            gateway.fail = False
            gateway.delay_seconds = 1
            short = context.model_copy(update={"deadline": monotonic() + 0.01})
            with pytest.raises(TimeoutError):
                await runtime.execute(short, "gateway-01")
            with pytest.raises(TimeoutError):
                await runtime.execute(short, "gateway-01")
            task = asyncio.create_task(
                dispatcher.call(ToolName.DISCOVER_GATEWAY, resource_id="gateway-01")
            )
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        assert not gateway.connected

    asyncio.run(scenario())


def test_mock_contracts(configuration):
    runtime = build_runtime(configuration)
    gateway = runtime.gateways.resolve("gateway-01", "demo")
    source = runtime.datasources.resolve("memory-source", "demo")
    context = create_context(configuration, ToolName.SYSTEM_HEALTH, None, None)

    async def scenario():
        with pytest.raises(ConnectionError):
            await source.health(context)
        with pytest.raises(ConnectionError):
            await gateway.get_health(context)
        other = context.model_copy(update={"environment_id": "other"})
        for adapter in (gateway, source):
            with pytest.raises(AuthorizationError):
                await adapter.connect(other)
        async with runtime.lifespan():
            assert (await gateway.get_health(context)).status == "healthy"
            for method in (
                gateway.get_products,
                gateway.get_backends,
                gateway.get_routes,
                gateway.get_policies,
                gateway.get_dependencies,
                gateway.get_gateway_logs,
                source.discover_schema,
            ):
                with pytest.raises(UnsupportedCapabilityError):
                    await method(context)
            with pytest.raises(UnsupportedCapabilityError):
                await gateway.trace_request("r1", context)
            with pytest.raises(UnsupportedCapabilityError):
                await source.query(Query(collection="anything"), context)
            source.fail = True
            with pytest.raises(DataSourceUnavailable):
                await source.health(context)
            gateway.fail = True
            with pytest.raises(GatewayUnavailable):
                await gateway.get_health(context)
        await source.close()
        await gateway.close()

    asyncio.run(scenario())


def test_capabilities_follow_permissions_features_and_adapters(configuration):
    data = configuration.model_dump()
    data["application"]["allowed_operations"] = []
    runtime = build_runtime(Configuration.model_validate(data))
    available = runtime.available_capabilities("demo")
    assert Capability.GATEWAY_DISCOVER not in available
    assert Capability.DATASOURCE_HEALTH not in available
    runtime = build_runtime(configuration)
    assert Capability.GATEWAY_DISCOVER not in runtime.available_capabilities("missing")


def test_framework_dependency_boundary():
    for path in (ROOT / "src/agt_mcp").rglob("*.py"):
        relative = path.relative_to(ROOT / "src/agt_mcp")
        if relative.parts[0] == "mcp":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            assert not any(
                name.split(".")[0] in {"fastmcp", "mcp", "mcp_types"} for name in names
            ), path
            if relative.parts[0] in {
                "services",
                "core",
                "gateways",
                "datasources",
                "evidence",
                "topology",
            }:
                assert not any(name.startswith("agt_mcp.mcp") for name in names), path


def test_lifecycle_rolls_back_partial_connection(configuration, monkeypatch):
    runtime = build_runtime(configuration)
    gateway = runtime.gateways.resolve("gateway-01", "demo")
    source = runtime.datasources.resolve("memory-source", "demo")

    async def fail(context):
        source.connected = True
        raise ConnectionError()

    monkeypatch.setattr(source, "connect", fail)

    async def scenario():
        with pytest.raises(ConnectionError):
            async with runtime.lifespan():
                pytest.fail("Startup failure must not yield")
        assert not source.connected
        assert not gateway.connected
        assert not runtime.ready

    asyncio.run(scenario())


def test_error_redaction_and_output_limit(configuration, monkeypatch, caplog):
    runtime = build_runtime(configuration)
    dispatcher = Dispatcher(runtime)

    async def fail(context, resource_id=None):
        raise ValueError("synthetic-secret-not-for-output")

    monkeypatch.setattr(runtime, "execute", fail)
    response = asyncio.run(dispatcher.call(ToolName.SYSTEM_HEALTH))
    assert response.error == "internal_error"
    assert "synthetic-secret" not in response.model_dump_json() + caplog.text

    async def large(context, resource_id=None):
        return {"large": "X" * 100000}

    monkeypatch.setattr(runtime, "execute", large)
    response = asyncio.run(dispatcher.call(ToolName.SYSTEM_HEALTH))
    assert response.error == "sanitization"
    assert response.data is None


def test_cross_environment_and_disabled_metadata(configuration):
    data = configuration.model_dump()
    data["environments"] = (
        *data["environments"],
        {"id": "other", "name": "Other", "type": "test", "cluster": "other-cluster"},
    )
    data["datasources"] = (
        *data["datasources"],
        {
            "id": "disabled",
            "environment_id": "demo",
            "type": "database",
            "provider": "postgresql",
            "enabled": False,
            "connection": {"host": "sensitive.invalid", "port": 5432},
            "credentials": {
                "provider": "environment",
                "reference": "SENSITIVE_REFERENCE",
                "environment_id": "demo",
            },
        },
        {
            "id": "hidden",
            "environment_id": "other",
            "type": "memory",
            "provider": "in-memory",
            "enabled": True,
            "connection": {"host": "hidden.invalid", "port": 443},
        },
    )
    data["gateways"] = (
        *data["gateways"],
        {
            "id": "hidden-gateway",
            "environment_id": "other",
            "adapter": "in-memory",
            "enabled": True,
            "datasource_id": "hidden",
        },
    )
    config = Configuration.model_validate(data)
    runtime = build_runtime(config)
    dispatcher = Dispatcher(runtime)

    async def scenario():
        async with runtime.lifespan():
            environments = await dispatcher.call(ToolName.LIST_ENVIRONMENTS)
            assert [e["id"] for e in environments.data["environments"]] == ["demo"]
            sources = await dispatcher.call(ToolName.LIST_DATASOURCES)
            assert "hidden" not in sources.model_dump_json()
            assert "sensitive" not in sources.model_dump_json().lower()
            disabled = await dispatcher.call(ToolName.INSPECT_DATASOURCE, resource_id="disabled")
            assert disabled.ok and disabled.data["health_state"] == "disabled"
            denied = await dispatcher.call(ToolName.DISCOVER_GATEWAY, resource_id="hidden-gateway")
            assert denied.error == "authorization"
            absent = await dispatcher.call(ToolName.INSPECT_DATASOURCE, resource_id="hidden")
            assert absent.error == "unsupported_capability"

    asyncio.run(scenario())


def test_permission_and_feature_denial(configuration):
    data = configuration.model_dump()
    data["mcp"]["server"]["authorization"]["permissions"] = ["capability.read", "datasource.read"]
    data["mcp"]["server"]["enabled_tools"] = ["list_capabilities", "inspect_datasource"]
    config = Configuration.model_validate(data)
    runtime = build_runtime(config)
    dispatcher = Dispatcher(runtime)

    async def scenario():
        async with runtime.lifespan():
            result = await dispatcher.call(ToolName.LIST_CAPABILITIES)
            assert result.data["capabilities"] == ["capability.read", "datasource.read"]
            denied = await dispatcher.call(ToolName.INSPECT_DATASOURCE, resource_id="memory-source")
            assert denied.error == "authorization"
            disabled = await dispatcher.call(ToolName.LIST_DATASOURCES)
            assert disabled.error == "unsupported_capability"

    asyncio.run(scenario())
