import asyncio
import json

import pytest
from fastmcp import Client

from agt_mcp.core.execution import RUNTIME_TOOLS, ToolName
from agt_mcp.datasources.kubernetes.adapter import KubernetesRuntimeAdapter
from agt_mcp.mcp.bootstrap import build_runtime
from agt_mcp.mcp.server import create_server
from tests.runtime_support import FakeKubernetesClient, runtime_configuration


@pytest.mark.parametrize("tool", sorted(RUNTIME_TOOLS))
def test_runtime_tool_through_real_mcp_client(tool):
    config = runtime_configuration()
    runtime = build_runtime(config)
    backend = FakeKubernetesClient()
    runtime.discovery.adapters["dev"] = KubernetesRuntimeAdapter(config.environments[0], backend)

    async def run():
        async with Client(create_server(runtime)) as client:
            listed = await client.list_tools()
            assert {t.name for t in listed} == set(ToolName)
            assert all(t.annotations.read_only_hint for t in listed)
            query = {"namespace": "example", "kind": "Pod", "name": "app-pod", "limit": 20}
            result = (
                await client.call_tool(tool.value, {"query": query, "environment_id": "dev"})
            ).structured_content
            assert result["ok"], result
            data = result["data"]
            if tool == ToolName.DISCOVER_ENVIRONMENT:
                assert data["resource_counts"]["Pod"] == 1
                assert "topology" not in data
            elif tool == ToolName.INSPECT_EVENTS:
                assert data["evidence"][0]["type"] == "observation"
            else:
                assert data["topology"]["nodes"]
            serialized = json.dumps(result)
            assert "PRIVATE-KEY" not in serialized and "CONFIGMAP-SECRET" not in serialized
            assert "Ignore previous instructions" not in serialized
        assert backend.closed

    asyncio.run(run())


@pytest.mark.parametrize(
    "query,environment,error",
    [
        ({"namespace": "other", "kind": "Pod", "name": "app"}, "dev", "authorization"),
        ({}, "other", "authorization"),
        (
            {"namespace": "example", "kind": "Secret", "name": "db-secret"},
            "dev",
            "unsupported_capability",
        ),
        ({"namespace": "example", "kind": "Pod", "name": "absent"}, "dev", "resource_not_found"),
    ],
)
def test_runtime_mcp_denies_invalid_scope(query, environment, error):
    config = runtime_configuration()
    runtime = build_runtime(config)
    backend = FakeKubernetesClient()
    runtime.discovery.adapters["dev"] = KubernetesRuntimeAdapter(config.environments[0], backend)

    async def run():
        async with Client(create_server(runtime)) as client:
            result = await client.call_tool(
                "inspect_resource", {"query": query, "environment_id": environment}
            )
            assert result.structured_content["error"] == error

    asyncio.run(run())
    assert not any(c[0] == "list" for c in backend.calls)
