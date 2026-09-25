"""FastMCP construction only; no module-level server or adapter singleton."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from agt_mcp import __version__
from agt_mcp.mcp.authentication import ConfiguredTokenVerifier
from agt_mcp.mcp.dispatch import Dispatcher
from agt_mcp.mcp.tools.correlation import register_correlation_tools
from agt_mcp.mcp.tools.gateway import register_gateway_tools
from agt_mcp.mcp.tools.inventory import register_tools
from agt_mcp.mcp.tools.knowledge import register_knowledge_tools
from agt_mcp.mcp.tools.observability import register_observability_tools
from agt_mcp.mcp.tools.runtime import register_runtime_tools
from agt_mcp.mcp.tools.trace import register_trace_tools
from agt_mcp.mcp.tools.troubleshooting import register_troubleshooting_tools
from agt_mcp.services.runtime import Runtime


def create_server(runtime: Runtime) -> FastMCP:
    reference = runtime.configuration.mcp.server.http_token
    authentication = ConfiguredTokenVerifier(reference) if reference else None

    @asynccontextmanager
    async def lifespan(server: FastMCP) -> AsyncIterator[None]:
        if authentication:
            await authentication.initialize()
        async with runtime.lifespan():
            yield

    server = FastMCP(
        name=runtime.configuration.mcp.server.name,
        version=__version__,
        lifespan=lifespan,
        mask_error_details=True,
        strict_input_validation=True,
        tasks=False,
        auth=authentication,
    )

    @server.custom_route("/livez", methods=["GET"], include_in_schema=False)
    async def liveness(request: Request) -> Response:
        return JSONResponse({"status": "alive"})

    @server.custom_route("/readyz", methods=["GET"], include_in_schema=False)
    async def readiness(request: Request) -> Response:
        return JSONResponse(
            {"status": runtime.health_status()}, status_code=200 if runtime.ready else 503
        )

    register_tools(server, Dispatcher(runtime))
    register_gateway_tools(server, Dispatcher(runtime))
    register_runtime_tools(server, Dispatcher(runtime))
    register_knowledge_tools(server, Dispatcher(runtime))
    register_correlation_tools(server, Dispatcher(runtime))
    register_troubleshooting_tools(server, Dispatcher(runtime))
    register_trace_tools(server, Dispatcher(runtime))
    register_observability_tools(server, Dispatcher(runtime))
    return server
