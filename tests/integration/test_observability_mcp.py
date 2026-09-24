import asyncio
from datetime import timedelta

import pytest
from fastmcp import Client
from pydantic import ValidationError

from agt_mcp.configuration.models import Configuration
from agt_mcp.configuration.observability import (
    ObservabilityConfig,
    ObservabilitySource,
    ResourceBinding,
)
from agt_mcp.core.errors import UnsupportedCapabilityError
from agt_mcp.core.execution import OBSERVABILITY_TOOLS, Capability, ToolName
from agt_mcp.datasources.observability_memory import InMemoryObservabilityAdapter
from agt_mcp.mcp.context import create_context
from agt_mcp.mcp.server import create_server
from agt_mcp.observability.models import CorrelationKeys, SignalType
from agt_mcp.services.observability_composition import build_observability
from tests.integration.test_correlation_mcp import setup
from tests.observability_support import log, metric, span
from tests.unit.test_observability_prometheus import prometheus


def configured(change=None):
    runtime, _, resource = setup()
    data = runtime.configuration.model_dump()
    source = ObservabilitySource(
        id="telemetry",
        type="memory",
        enabled=True,
        environment_id="dev",
        usage=(SignalType.LOG, SignalType.METRIC, SignalType.TRACE),
        bindings=(
            ResourceBinding(
                environment_id="dev",
                resource_id=resource,
                selectors={"service": "apicast-production"},
                keys=CorrelationKeys(trace_id="trace-123"),
            ),
        ),
    )
    data["observability"] = ObservabilityConfig(sources=(source,)).model_dump()
    if change:
        change(data)
    runtime, adapter, resource = setup(configuration=Configuration.model_validate(data))
    stamp = runtime.correlation.engine.clock.now()
    rows = tuple(
        factory().model_copy(
            update={
                "environment_id": "dev",
                "resource_id": resource,
                "timestamp": stamp - timedelta(seconds=2),
            }
        )
        for factory in (log, metric, span)
    )
    runtime.observability.adapters["telemetry"] = InMemoryObservabilityAdapter(source, rows)
    q = dict(
        environment_id="dev",
        resource_refs=[resource],
        time_window={"start": (stamp - timedelta(minutes=5)).isoformat(), "end": stamp.isoformat()},
    )
    return runtime, adapter, q


def test_five_tools_via_actual_fastmcp_and_safe_defaults():
    runtime, adapter, q = configured()

    async def scenario():
        async with Client(create_server(runtime)) as client:
            tools = {t.name: t for t in await client.list_tools()}
            for name in sorted(OBSERVABILITY_TOOLS):
                assert tools[name].annotations.read_only_hint
                assert tools[name].annotations.destructive_hint is False
                assert tools[name].annotations.open_world_hint
                schema = tools[name].input_schema
                assert "url" not in str(schema) and "raw_query" not in str(schema)
                args = {"query": {**q}}
                if name == ToolName.INSPECT_TRACE:
                    args["query"].update(trace_id="trace-123", resource_refs=[])
                result = (await client.call_tool(name.value, args)).structured_content
                assert result["ok"], result
                data = result["data"]
                assert data["timeline"]["descriptive_only"] and data["evidence"]
                signal = {
                    "inspect_logs": "log",
                    "inspect_metrics": "metric",
                    "inspect_trace": "trace",
                }.get(name)
                if signal:
                    assert signal in {t["category"] for t in data["timeline"]["entries"]}
                assert all(e["resource_id"] == q["resource_refs"][0] for e in data["evidence"])
            assert len(adapter.runtime.calls) == 5

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "case,error",
    [
        ("permission", "authorization"),
        ("operation", "unsupported_capability"),
        ("environment", "authorization"),
        ("query_environment", "authorization"),
    ],
)
def test_mcp_denials_preserve_scope(case, error):
    def change(data):
        if case == "permission":
            data["mcp"]["server"]["authorization"]["permissions"] = [Capability.CORRELATION_READ]
        if case == "operation":
            data["application"]["allowed_operations"] = ["health"]

    runtime, adapter, q = configured(change)
    if case == "query_environment":
        q["environment_id"] = "other"

    async def scenario():
        async with Client(create_server(runtime)) as client:
            result = (
                await client.call_tool(
                    "inspect_logs",
                    {"query": q, "environment_id": "other" if case == "environment" else "dev"},
                )
            ).structured_content
            assert not result["ok"] and result["error"] == error, result
            assert not adapter.runtime.calls
            if case == "operation":
                assert Capability.OBSERVABILITY_LOGS not in runtime.available_capabilities("dev")

    asyncio.run(scenario())


def test_mcp_partial_logs_forbidden_metrics_and_events_available():
    def change(data):
        data["mcp"]["server"]["authorization"]["permissions"] = [
            c.value for c in Capability if c != Capability.OBSERVABILITY_LOGS
        ]

    runtime, _, q = configured(change)

    async def scenario():
        async with Client(create_server(runtime)) as client:
            result = (
                await client.call_tool("inspect_observability", {"query": q})
            ).structured_content
            assert result["ok"], result
            assert result["data"]["status"] == "PARTIAL"
            outcomes = {s["signal"]: s["status"] for s in result["data"]["sources"]}
            assert outcomes == {"LOG": "FORBIDDEN", "METRIC": "OK", "TRACE": "OK", "EVENT": "OK"}

    asyncio.run(scenario())


def test_runtime_requires_query_and_opt_in_registration():
    runtime, _, _ = configured()

    async def scenario():
        async with runtime.lifespan():
            with pytest.raises(UnsupportedCapabilityError):
                await runtime.execute(
                    create_context(runtime.configuration, ToolName.INSPECT_LOGS, "dev", None)
                )

    asyncio.run(scenario())
    data = runtime.configuration.model_dump()
    data["mcp"]["server"].pop("enabled_tools")
    config = Configuration.model_validate(data)
    assert not set(config.mcp.server.enabled_tools) & OBSERVABILITY_TOOLS
    data["observability"]["sources"][0]["environment_id"] = "unregistered"
    data["observability"]["sources"][0]["bindings"] = []
    with pytest.raises(ValidationError, match="unknown observability environment"):
        Configuration.model_validate(data)


def test_composition_does_not_resolve_credentials_or_contact_network(monkeypatch):
    monkeypatch.delenv("SPRINT8_TEST_TOKEN", raising=False)
    cfg = ObservabilityConfig(
        sources=(
            prometheus(
                credentials={
                    "provider": "environment",
                    "reference": "SPRINT8_TEST_TOKEN",
                    "environment_id": "demo",
                }
            ),
        )
    )
    built = build_observability(cfg)
    assert "telemetry" in built
    assert not build_observability(ObservabilityConfig(sources=(prometheus(enabled=False),)))
