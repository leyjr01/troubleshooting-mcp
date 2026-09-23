"""FastMCP construction only; no module-level server or adapter singleton."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP

from agt_mcp import __version__
from agt_mcp.mcp.dispatch import Dispatcher
from agt_mcp.mcp.tools.gateway import register_gateway_tools
from agt_mcp.mcp.tools.inventory import register_tools
from agt_mcp.mcp.tools.knowledge import register_knowledge_tools
from agt_mcp.mcp.tools.runtime import register_runtime_tools
from agt_mcp.services.runtime import Runtime


def create_server(runtime: Runtime) -> FastMCP:
    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[None]:
        async with runtime.lifespan():
            yield

    server = FastMCP(
        name=runtime.configuration.mcp.server.name,
        version=__version__,
        lifespan=lifespan,
        mask_error_details=True,
        strict_input_validation=True,
        tasks=False,
    )
    register_tools(server, Dispatcher(runtime))
    register_gateway_tools(server, Dispatcher(runtime))
    register_runtime_tools(server, Dispatcher(runtime))
    register_knowledge_tools(server, Dispatcher(runtime))
    return server
