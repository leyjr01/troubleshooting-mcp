"""Thin typed runtime tool registration; no Kubernetes SDK objects here."""

from collections.abc import Awaitable, Callable

from fastmcp import FastMCP

from agt_mcp.core.execution import RUNTIME_TOOLS, TOOL_DEFINITIONS, ToolName
from agt_mcp.core.models import Identifier
from agt_mcp.core.runtime import RuntimeQuery
from agt_mcp.mcp.dispatch import Dispatcher
from agt_mcp.mcp.responses import ToolResponse


def register_runtime_tools(server: FastMCP, dispatcher: Dispatcher) -> None:
    def tool(name: ToolName) -> Callable[..., Awaitable[ToolResponse]]:
        async def invoke(
            query: RuntimeQuery,
            environment_id: Identifier | None = None,
            correlation_id: str | None = None,
        ) -> ToolResponse:
            return await dispatcher.call(name, environment_id, correlation_id, runtime_query=query)

        return invoke

    for definition in TOOL_DEFINITIONS:
        if (
            definition.name in RUNTIME_TOOLS
            and definition.name in dispatcher.runtime.configuration.mcp.server.enabled_tools
        ):
            server.tool(
                name=definition.name.value,
                description=definition.description,
                annotations={
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            )(tool(definition.name))
