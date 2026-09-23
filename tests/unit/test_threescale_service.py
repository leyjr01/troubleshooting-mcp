import asyncio

import pytest

from agt_mcp.configuration.gateway import GatewayDiscoveryConfig
from agt_mcp.core.errors import AuthorizationError, UnsupportedCapabilityError
from agt_mcp.core.execution import ToolName
from agt_mcp.core.operations import Operation
from agt_mcp.gateways.threescale.models import GatewayQuery
from agt_mcp.mcp.context import create_context
from tests.integration.test_threescale_mcp import setup


@pytest.mark.parametrize("depth,limit", [(1, 1), (1, 10), (2, 20), (3, 200)])
def test_topology_limits_and_closed_edges(depth, limit):
    runtime, adapter = setup()
    context = create_context(runtime.configuration, ToolName.GET_GATEWAY_TOPOLOGY, "dev", None)

    async def run():
        async with runtime.lifespan():
            result = await runtime.execute(
                context,
                gateway_query=GatewayQuery(gateway_id="threescale-auto", depth=depth, limit=limit),
            )
            ids = {
                result["installation"]["id"],
                *(n["id"] for n in result["semantic_nodes"]),
                *(n["id"] for n in result["runtime_nodes"]),
            }
            assert len(ids) <= limit
            assert all(
                e["source"] in ids and e["target"] in ids
                for e in result["relationships"] + result["runtime_relationships"]
            )
            if depth == 1:
                assert not result["runtime_nodes"]
            if limit == 1:
                assert result["truncated"]

    asyncio.run(run())


def test_dependency_payload_can_be_disabled():
    runtime, adapter = setup()
    adapter.settings = GatewayDiscoveryConfig(
        include_dependencies=False, include_runtime_resources=False
    )
    from agt_mcp.core.execution import Capability

    assert Capability.GATEWAY_DEPENDENCIES not in runtime.available_capabilities("dev")
    context = create_context(runtime.configuration, ToolName.GET_GATEWAY_DEPENDENCIES, "dev", None)

    async def run():
        async with runtime.lifespan():
            with pytest.raises(UnsupportedCapabilityError):
                await runtime.execute(
                    context, gateway_query=GatewayQuery(gateway_id="threescale-auto")
                )
            with pytest.raises(UnsupportedCapabilityError):
                await adapter.get_dependencies(context)

    asyncio.run(run())


def test_binding_namespace_is_checked_before_runtime():
    runtime, adapter = setup()
    adapter.settings = GatewayDiscoveryConfig(namespace="example")
    context = create_context(runtime.configuration, ToolName.DISCOVER_GATEWAY, "dev", None)

    async def run():
        async with runtime.lifespan():
            with pytest.raises(AuthorizationError):
                await runtime.execute(context, gateway_query=GatewayQuery(namespace="other"))

    asyncio.run(run())
    assert not adapter.runtime.calls


def test_operation_allowlist_still_applies():
    runtime, _ = setup()
    runtime.configuration = runtime.configuration.model_copy(
        update={
            "application": runtime.configuration.application.model_copy(
                update={"allowed_operations": (Operation.HEALTH,)}
            )
        }
    )
    context = create_context(runtime.configuration, ToolName.GET_GATEWAY_TOPOLOGY, "dev", None)

    async def run():
        async with runtime.lifespan():
            with pytest.raises(UnsupportedCapabilityError):
                await runtime.execute(
                    context, gateway_query=GatewayQuery(gateway_id="threescale-auto")
                )

    asyncio.run(run())
