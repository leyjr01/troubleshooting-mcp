"""Explicitly configured read-only smoke; no cluster preparation or fault injection."""

import asyncio
import json
import os
from pathlib import Path

import pytest
from fastmcp import Client

from agt_mcp.configuration.loader import load_configuration
from agt_mcp.mcp.bootstrap import build_runtime
from agt_mcp.mcp.server import create_server

pytestmark = pytest.mark.real_lab


def test_read_only_cluster_smoke():
    location = os.environ.get("AGT_REAL_LAB_CONFIG")
    if not location:
        pytest.skip("AGT_REAL_LAB_CONFIG not configured; real cluster NOT EXECUTED")
    config = load_configuration([Path(location)])
    runtime = build_runtime(config)
    assert not config.probes.enabled, "read-only smoke requires probes disabled"
    assert config.environments and all(
        not e.runtime.discovery.cluster_scoped for e in config.environments if e.runtime
    )

    async def run():
        async with Client(create_server(runtime)) as client:

            async def call(name, **args):
                response = (await client.call_tool(name, args)).structured_content
                assert response["ok"], response.get("error")
                return response["data"]

            await call("system_health")
            await call("list_capabilities")
            discovered = await call("discover_environment", query={})
            assert discovered["namespaces"] and discovered["resource_counts"], (
                "No observable runtime resources"
            )
            selector = json.loads(os.environ.get("AGT_REAL_LAB_QUERY", "{}"))
            assert selector.get("kind") and selector.get("name"), (
                "AGT_REAL_LAB_QUERY needs kind/name/namespace"
            )
            inspected = await call("inspect_resource", query=selector)
            resource_id = inspected["resource"]["id"]
            await call("inspect_events", query=selector)
            await call("get_resource_topology", query=selector)
            await call("trace_resource", query={"resource_id": resource_id})
            await call("diagnose_api", query={"resource_id": resource_id})
            gateway = os.environ.get("AGT_REAL_LAB_GATEWAY_ID")
            if gateway:
                await call("discover_gateway", gateway_id=gateway)
                await call("get_gateway_topology", query={"gateway_id": gateway})

    asyncio.run(run())
