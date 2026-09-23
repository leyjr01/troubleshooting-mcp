import asyncio
import json

import pytest
from fastmcp import Client

from agt_mcp.core.execution import KNOWLEDGE_TOOLS, Capability
from agt_mcp.core.operations import Operation
from agt_mcp.mcp.server import create_server
from tests.knowledge_support import ready


@pytest.mark.parametrize("tool", sorted(KNOWLEDGE_TOOLS))
def test_knowledge_tools_actual_mcp(tmp_path, tool, caplog):
    runtime, context, _ = ready(tmp_path)
    caplog.set_level("INFO", logger="agt_mcp.audit")

    async def run():
        async with Client(create_server(runtime)) as client:
            registered = {t.name: t for t in await client.list_tools()}
            assert set(KNOWLEDGE_TOOLS) <= registered.keys()
            assert all(registered[t].annotations.read_only_hint for t in KNOWLEDGE_TOOLS)
            args = {"query": {"text": "APIcast Redis 503"}}
            if tool == "list_knowledge_sources":
                args = {}
            if tool == "get_knowledge_source_health":
                args = {"source_id": "internal"}
            response = (await client.call_tool(tool, args)).structured_content
            assert response["ok"], response
            if "results" in response["data"]:
                assert response["data"]["results"]
                assert all(r["chunk"]["source"]["document_id"] for r in response["data"]["results"])
            assert "prod-runbook" not in json.dumps(response)

    asyncio.run(run())
    assert "APIcast Redis 503" not in caplog.text
    assert '"adapter": "knowledge"' in caplog.text


@pytest.mark.parametrize(
    "case", ["environment", "permission", "operation", "source", "category", "filter"]
)
def test_knowledge_mcp_denials(tmp_path, case):
    runtime, _, _ = ready(tmp_path)
    if case == "permission":
        grant = runtime.configuration.mcp.server.authorization
        object.__setattr__(
            grant, "permissions", grant.permissions - {Capability.KNOWLEDGE_INTERNAL}
        )
    if case == "operation":
        object.__setattr__(
            runtime.configuration.application, "allowed_operations", (Operation.HEALTH,)
        )

    async def run():
        async with Client(create_server(runtime)) as client:
            args = {"query": {"text": "APIcast"}}
            if case == "environment":
                args["environment_id"] = "prod"
            if case == "source":
                args["query"]["repository_ids"] = ["missing"]
            if case == "category":
                args["query"]["source_types"] = ["OFFICIAL_DOCUMENTATION"]
            if case == "filter":
                args["query"]["filters"] = {"environment": "prod"}
            response = (
                await client.call_tool("search_internal_knowledge", args)
            ).structured_content
            assert not response["ok"]

    asyncio.run(run())


def test_mcp_json_arrays_and_version_filters(tmp_path):
    runtime, _, _ = ready(tmp_path)

    async def run():
        async with Client(create_server(runtime)) as client:
            result = (
                await client.call_tool(
                    "search_internal_knowledge",
                    {
                        "query": {
                            "text": "APIcast",
                            "repository_ids": ["internal"],
                            "source_types": ["RUNBOOK"],
                            "filters": {"tags": ["tls"], "system": "payments"},
                        }
                    },
                )
            ).structured_content
            assert result["ok"] and result["data"]["results"]
            official = (
                await client.call_tool(
                    "search_official_documentation",
                    {
                        "query": {
                            "text": "Redis",
                            "filters": {"product": "3scale", "product_version": "2.16"},
                        }
                    },
                )
            ).structured_content
            assert official["ok"] and official["data"]["results"]

    asyncio.run(run())
