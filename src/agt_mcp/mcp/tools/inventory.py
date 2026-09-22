"""Typed MCP inputs and read-only annotations for seven application operations."""

from fastmcp import FastMCP

from agt_mcp.core.execution import TOOL_DEFINITIONS, ToolName
from agt_mcp.core.models import Identifier
from agt_mcp.mcp.dispatch import Dispatcher
from agt_mcp.mcp.responses import ToolResponse


def register_tools(server: FastMCP, dispatcher: Dispatcher) -> None:
    async def system_health(
        environment_id: Identifier | None = None, correlation_id: str | None = None
    ) -> ToolResponse:
        return await dispatcher.call(ToolName.SYSTEM_HEALTH, environment_id, correlation_id)

    async def list_capabilities(
        environment_id: Identifier | None = None, correlation_id: str | None = None
    ) -> ToolResponse:
        return await dispatcher.call(ToolName.LIST_CAPABILITIES, environment_id, correlation_id)

    async def list_environments(
        environment_id: Identifier | None = None, correlation_id: str | None = None
    ) -> ToolResponse:
        return await dispatcher.call(ToolName.LIST_ENVIRONMENTS, environment_id, correlation_id)

    async def list_gateways(
        environment_id: Identifier | None = None, correlation_id: str | None = None
    ) -> ToolResponse:
        return await dispatcher.call(ToolName.LIST_GATEWAYS, environment_id, correlation_id)

    async def list_datasources(
        environment_id: Identifier | None = None, correlation_id: str | None = None
    ) -> ToolResponse:
        return await dispatcher.call(ToolName.LIST_DATASOURCES, environment_id, correlation_id)

    async def inspect_datasource(
        datasource_id: Identifier,
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.INSPECT_DATASOURCE, environment_id, correlation_id, datasource_id
        )

    async def discover_gateway(
        gateway_id: Identifier,
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.DISCOVER_GATEWAY, environment_id, correlation_id, gateway_id
        )

    functions = {
        function.__name__: function
        for function in (
            system_health,
            list_capabilities,
            list_environments,
            list_gateways,
            list_datasources,
            inspect_datasource,
            discover_gateway,
        )
    }
    settings = dispatcher.runtime.configuration.mcp.server
    for definition in TOOL_DEFINITIONS:
        if definition.name in settings.enabled_tools and definition.name in functions:
            server.tool(
                name=definition.name.value,
                description=definition.description,
                annotations={
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            )(functions[definition.name])
