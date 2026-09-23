import asyncio
import json

import pytest
from fastmcp import Client

from agt_mcp.mcp.bootstrap import build_runtime
from agt_mcp.mcp.server import create_server
from tests.threescale_support import FakeRuntime, config, snapshot


def setup():
    configuration = config()
    snap, _ = snapshot(configuration=configuration)
    runtime = build_runtime(configuration)
    adapter = runtime.gateway_discovery.adapters("dev")["threescale-auto"]
    adapter.runtime = FakeRuntime(snap)
    return runtime, adapter


@pytest.mark.parametrize(
    "tool",
    [
        "discover_gateway",
        "get_gateway_topology",
        "inspect_gateway_component",
        "get_gateway_dependencies",
    ],
)
def test_semantic_tools_via_actual_mcp(tool, caplog):
    caplog.set_level("INFO", logger="agt_mcp.audit")
    runtime, adapter = setup()

    async def run():
        async with Client(create_server(runtime)) as client:
            result = await client.call_tool("discover_gateway", {"environment_id": "dev"})
            data = result.structured_content
            assert data["ok"], data
            installation = data["data"]["installations"][0]
            query = {"gateway_id": installation["id"], "limit": 200}
            if tool == "inspect_gateway_component":
                query["component_id"] = next(
                    c["id"] for c in installation["components"] if c["type"] == "SYSTEM_APP"
                )
            if tool != "discover_gateway":
                result = await client.call_tool(tool, {"environment_id": "dev", "query": query})
                assert result.structured_content["ok"], result.structured_content
            serialized = json.dumps(result.structured_content)
            assert "PASSWORD-SYNTHETIC" not in serialized
            assert "CR-SECRET-SYNTHETIC" not in serialized
            if tool == "get_gateway_topology":
                assert result.structured_content["data"]["runtime_nodes"]
            assert len(adapter.runtime.calls) == (1 if tool == "discover_gateway" else 2)

    asyncio.run(run())
    audit = [
        json.loads(record.message) for record in caplog.records if record.name == "agt_mcp.audit"
    ]
    audit = [event for event in audit if event["event"] == "tool_finished"]
    assert audit
    assert all(event["adapter"] == "threescale" for event in audit)


@pytest.mark.parametrize(
    "case,error",
    [
        ("environment", "authorization"),
        ("component", "resource_not_found"),
        ("gateway", "resource_not_found"),
        ("missing", "configuration"),
        ("namespace", "authorization"),
    ],
)
def test_semantic_mcp_rejections(case, error):
    runtime, adapter = setup()

    async def run():
        async with Client(create_server(runtime)) as client:
            response = await client.call_tool("discover_gateway", {})
            identifier = response.structured_content["data"]["installations"][0]["id"]
            query = {"gateway_id": identifier}
            tool = "get_gateway_topology"
            if case == "component":
                tool = "inspect_gateway_component"
                query["component_id"] = "missing"
            if case == "gateway":
                query["gateway_id"] = "missing"
            if case == "missing":
                query = {}
            if case == "namespace":
                query["namespace"] = "other"
            result = await client.call_tool(
                tool,
                {"environment_id": "other" if case == "environment" else "dev", "query": query},
            )
            assert result.structured_content["error"] == error

    asyncio.run(run())


def test_unexpected_adapter_exception_is_sanitized():
    from unittest.mock import AsyncMock

    runtime, adapter = setup()
    adapter.runtime.discover = AsyncMock(side_effect=ValueError("backend-redis PASSWORD-SYNTHETIC"))

    async def run():
        async with Client(create_server(runtime)) as client:
            result = await client.call_tool("discover_gateway", {})
            assert not result.structured_content["ok"]
            assert "PASSWORD-SYNTHETIC" not in json.dumps(result.structured_content)

    asyncio.run(run())
