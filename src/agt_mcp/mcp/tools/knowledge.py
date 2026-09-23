"""Five read-only MCP tools over existing knowledge indexes; no public refresh."""

from collections.abc import Awaitable, Callable

from fastmcp import FastMCP

from agt_mcp.core.execution import KNOWLEDGE_TOOLS, TOOL_DEFINITIONS, ToolName
from agt_mcp.core.models import Identifier
from agt_mcp.mcp.dispatch import Dispatcher
from agt_mcp.mcp.responses import ToolResponse
from agt_mcp.rag.contracts import RetrievalQuery


def register_knowledge_tools(server: FastMCP, dispatcher: Dispatcher) -> None:
    def search_factory(name: ToolName) -> Callable[..., Awaitable[ToolResponse]]:
        async def search(
            query: RetrievalQuery,
            environment_id: Identifier | None = None,
            correlation_id: str | None = None,
        ) -> ToolResponse:
            return await dispatcher.call(
                name, environment_id, correlation_id, knowledge_query=query
            )

        return search

    async def list_sources(
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.LIST_KNOWLEDGE_SOURCES, environment_id, correlation_id
        )

    async def health(
        source_id: Identifier,
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.GET_KNOWLEDGE_SOURCE_HEALTH, environment_id, correlation_id, source_id
        )

    for definition in TOOL_DEFINITIONS:
        if (
            definition.name not in KNOWLEDGE_TOOLS
            or definition.name not in dispatcher.runtime.configuration.mcp.server.enabled_tools
        ):
            continue
        handler = (
            list_sources
            if definition.name == ToolName.LIST_KNOWLEDGE_SOURCES
            else health
            if definition.name == ToolName.GET_KNOWLEDGE_SOURCE_HEALTH
            else search_factory(definition.name)
        )
        server.tool(
            name=definition.name.value,
            description=definition.description,
            annotations={
                "readOnlyHint": True,
                "destructiveHint": False,
                "idempotentHint": True,
                "openWorldHint": False,
            },
        )(handler)
