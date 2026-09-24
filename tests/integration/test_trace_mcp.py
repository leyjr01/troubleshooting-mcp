import asyncio

import pytest
from fastmcp import Client

from agt_mcp.configuration.models import Configuration
from agt_mcp.core.execution import Capability
from agt_mcp.gateways.threescale.classifier import ThreeScaleComponentClassifier
from agt_mcp.mcp.server import create_server
from tests.integration.test_correlation_mcp import setup
from tests.probe_support import FakeExecutor, config


def configured(mode="execute_allowed"):
    runtime, _, resource = setup()
    settings = config()
    settings = settings.model_copy(
        update={
            "execution_mode": mode,
            "endpoints": (
                settings.endpoints[0].model_copy(
                    update={"environment_id": "dev", "resource_id": resource}
                ),
            ),
            "policy": settings.policy.model_copy(
                update={
                    "environments": (
                        settings.policy.environments[0].model_copy(
                            update={"environment_id": "dev"}
                        ),
                    )
                }
            ),
        }
    )
    data = runtime.configuration.model_dump()
    data["probes"] = settings.model_dump()
    runtime, adapter, resource = setup(configuration=Configuration.model_validate(data))
    runtime.trace.runner.executor = FakeExecutor()
    return runtime, adapter, resource


@pytest.mark.parametrize("tool", ["trace_resource", "trace_gateway_component"])
def test_five_tools_operational_with_no_arbitrary_destination(tool):
    runtime, adapter, resource = configured()
    installation = ThreeScaleComponentClassifier(adapter.runtime.result).classify()[0]
    component = next(c for c in installation.components if c.type.value == "APICAST_PRODUCTION")

    async def run():
        async with Client(create_server(runtime)) as client:
            tools = {t.name: t for t in await client.list_tools()}
            assert tools["execute_probe_plan"].annotations.open_world_hint
            assert not tools["execute_probe_plan"].annotations.idempotent_hint
            assert "target" not in tools["execute_probe_plan"].input_schema["properties"]
            query = {"include_knowledge": False, "include_history": False}
            query.update(
                {"resource_id": resource}
                if tool == "trace_resource"
                else {"component_id": component.id}
            )
            traced = (await client.call_tool(tool, {"query": query})).structured_content
            assert traced["ok"], traced
            trace = traced["data"]
            planned = (
                await client.call_tool("plan_probes", {"trace_id": trace["id"]})
            ).structured_content
            assert planned["ok"] and planned["data"]["requests"], planned
            assert not runtime.trace.runner.executor.calls
            result = (
                await client.call_tool("execute_probe_plan", {"plan_id": planned["data"]["id"]})
            ).structured_content
            assert result["ok"], result
            assert result["data"]["trace"]["probes"] and result["data"]["diagnosis"]
            explain = (
                await client.call_tool("explain_trace", {"trace_id": trace["id"]})
            ).structured_content
            assert explain["ok"] and explain["data"]["relationships"]
            assert len(adapter.runtime.calls) == 1

    asyncio.run(run())


@pytest.mark.parametrize(
    "case", ["environment", "permission", "operation", "unrelated", "arbitrary_url", "cache"]
)
def test_mcp_denials(case):
    runtime, _, resource = configured()
    data = runtime.configuration.model_dump()
    if case == "permission":
        data["mcp"]["server"]["authorization"]["permissions"] = [Capability.TRACE_READ]
    if case == "operation":
        data["application"]["allowed_operations"] = ["health"]
    runtime, _, _ = setup(configuration=Configuration.model_validate(data))

    async def run():
        async with Client(create_server(runtime)) as client:
            if case == "arbitrary_url":
                result = (
                    await client.call_tool(
                        "execute_probe_plan", {"plan_id": "http://169.254.169.254"}
                    )
                ).structured_content
                assert result["error"] == "resource_not_found"
                return
            if case == "cache":
                result = (
                    await client.call_tool("explain_trace", {"trace_id": "other-principal-id"})
                ).structured_content
                assert result["error"] == "resource_not_found"
                return
            query = {
                "resource_id": "unrelated" if case == "unrelated" else resource,
                "include_knowledge": False,
                "include_history": False,
            }
            result = (
                await client.call_tool(
                    "trace_resource",
                    {"query": query, "environment_id": "prod" if case == "environment" else "dev"},
                )
            ).structured_content
            assert result["error"] == (
                "unsupported_capability"
                if case == "operation"
                else "resource_not_found"
                if case == "unrelated"
                else "authorization"
            )

    asyncio.run(run())


def test_plan_only_never_calls_executor():
    runtime, _, resource = configured("plan_only")
    assert Capability.PROBE_EXECUTE not in runtime.available_capabilities("dev")

    async def run():
        async with Client(create_server(runtime)) as client:
            traced = (
                await client.call_tool(
                    "trace_resource",
                    {
                        "query": {
                            "resource_id": resource,
                            "include_history": False,
                            "include_knowledge": False,
                        }
                    },
                )
            ).structured_content["data"]
            planned = (
                await client.call_tool("plan_probes", {"trace_id": traced["id"]})
            ).structured_content["data"]
            executed = (
                await client.call_tool("execute_probe_plan", {"plan_id": planned["id"]})
            ).structured_content
            assert executed["ok"], executed
            assert all(
                p["result"]["status"] == "BLOCKED" for p in executed["data"]["trace"]["probes"]
            )
            assert not runtime.trace.runner.executor.calls

    asyncio.run(run())
