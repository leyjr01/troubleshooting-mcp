import asyncio
import json
import logging
from pathlib import Path
from uuid import UUID, uuid4

from fastmcp import Client

from agt_mcp.configuration.loader import load_configuration
from agt_mcp.configuration.models import Configuration
from agt_mcp.core.execution import ToolName
from agt_mcp.mcp.bootstrap import build_runtime
from agt_mcp.mcp.server import create_server

ROOT = Path(__file__).resolve().parents[2]


def config():
    return load_configuration([ROOT / "config/server/local.example.yaml"], environ={})


def test_mcp_seven_tools_and_safe_results(caplog):
    runtime = build_runtime(config())
    correlation = str(uuid4())

    async def scenario():
        async with Client(create_server(runtime)) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools} == set(ToolName)
            assert all(tool.annotations.read_only_hint for tool in tools)
            assert all(tool.output_schema for tool in tools)
            for name in ToolName:
                args = {"correlation_id": correlation}
                if name == ToolName.DISCOVER_GATEWAY:
                    args["gateway_id"] = "gateway-01"
                if name == ToolName.INSPECT_DATASOURCE:
                    args["datasource_id"] = "memory-source"
                result = await client.call_tool(name.value, args)
                response = result.structured_content
                assert response["ok"], response
                UUID(response["request_id"])
                assert response["correlation_id"] == correlation
                assert "credentials" not in json.dumps(response)
                assert "memory.invalid" not in json.dumps(response)
                if name == ToolName.SYSTEM_HEALTH:
                    assert response["data"]["registered_gateways"] == 1
                elif name == ToolName.DISCOVER_GATEWAY:
                    assert response["data"]["provider"] == "in-memory"
                elif name == ToolName.INSPECT_DATASOURCE:
                    assert response["data"]["health_state"] == "healthy"
                elif name == ToolName.LIST_CAPABILITIES:
                    assert "gateway.discover" in response["data"]["capabilities"]
        assert not runtime.ready
        assert not runtime.gateways.resolve("gateway-01", "demo").connected

    with caplog.at_level(logging.INFO, logger="agt_mcp.audit"):
        asyncio.run(scenario())
    events = [
        json.loads(record.message) for record in caplog.records if record.name == "agt_mcp.audit"
    ]
    assert len(events) == 7
    assert all(event["correlation_id"] == correlation for event in events)
    assert len({event["request_id"] for event in events}) == 7


def test_mcp_rejections_and_invalid_input():
    async def scenario():
        async with Client(create_server(build_runtime(config()))) as client:
            denied = await client.call_tool("system_health", {"environment_id": "other"})
            assert denied.structured_content["error"] == "authorization"
            for args in (
                {"environment_id": "invalid\nvalue"},
                {"principal": "admin"},
                {"environment_id": 123},
            ):
                invalid = await client.call_tool("system_health", args, raise_on_error=False)
                assert invalid.is_error
            missing = await client.call_tool("discover_gateway", {"gateway_id": "missing"})
            assert missing.structured_content["error"] == "unsupported_capability"
            invalid = await client.call_tool(
                "system_health", {"correlation_id": "Bearer test-secret"}
            )
            UUID(invalid.structured_content["correlation_id"])
            assert "test-secret" not in json.dumps(invalid.structured_content)

    asyncio.run(scenario())


def test_mcp_default_deny_and_disabled_tool():
    data = config().model_dump()
    data["mcp"]["server"]["authorization"]["mode"] = "deny-all"
    data["mcp"]["server"]["enabled_tools"] = ["system_health"]

    async def scenario():
        runtime = build_runtime(Configuration.model_validate(data))
        async with Client(create_server(runtime)) as client:
            assert [tool.name for tool in await client.list_tools()] == ["system_health"]
            result = await client.call_tool("system_health", {})
            assert result.structured_content["error"] == "authorization"

    asyncio.run(scenario())
