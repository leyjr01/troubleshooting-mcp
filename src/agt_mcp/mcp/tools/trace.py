"""Typed MCP wrappers; IDs reference scoped server-side plans, never raw targets."""

from collections.abc import Awaitable, Callable
from typing import Literal

from fastmcp import FastMCP

from agt_mcp.core.execution import TRACE_TOOLS, ToolName
from agt_mcp.core.models import Identifier
from agt_mcp.correlation.models import CorrelationQuery
from agt_mcp.mcp.dispatch import Dispatcher
from agt_mcp.mcp.responses import ToolResponse
from agt_mcp.trace.models import TraceOperation


def register_trace_tools(server: FastMCP, dispatcher: Dispatcher) -> None:
    def factory(name: ToolName) -> Callable[..., Awaitable[ToolResponse]]:
        async def trace(
            query: CorrelationQuery,
            direction: Literal["outgoing", "incoming", "both"] = "outgoing",
            max_depth: int | None = None,
            environment_id: Identifier | None = None,
            correlation_id: str | None = None,
        ) -> ToolResponse:
            return await dispatcher.call(
                name,
                environment_id,
                correlation_id,
                trace_operation=TraceOperation(
                    query=query, direction=direction, max_depth=max_depth
                ),
            )

        return trace

    async def plan(
        trace_id: Identifier | None = None,
        troubleshooting_id: Identifier | None = None,
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.PLAN_PROBES,
            environment_id,
            correlation_id,
            trace_operation=TraceOperation(
                trace_id=trace_id, troubleshooting_id=troubleshooting_id
            ),
        )

    async def execute(
        plan_id: Identifier,
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.EXECUTE_PROBE_PLAN,
            environment_id,
            correlation_id,
            trace_operation=TraceOperation(plan_id=plan_id),
        )

    async def explain(
        trace_id: Identifier,
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.EXPLAIN_TRACE,
            environment_id,
            correlation_id,
            trace_operation=TraceOperation(trace_id=trace_id),
        )

    handlers = {
        ToolName.TRACE_RESOURCE: factory(ToolName.TRACE_RESOURCE),
        ToolName.TRACE_GATEWAY_COMPONENT: factory(ToolName.TRACE_GATEWAY_COMPONENT),
        ToolName.PLAN_PROBES: plan,
        ToolName.EXECUTE_PROBE_PLAN: execute,
        ToolName.EXPLAIN_TRACE: explain,
    }
    for name in sorted(TRACE_TOOLS):
        if name in dispatcher.runtime.configuration.mcp.server.enabled_tools:
            server.tool(
                name=name.value,
                description="Bounded trace/probe operation; network execution requires "
                "explicit policy and permission",
                annotations={
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": name != ToolName.EXECUTE_PROBE_PLAN,
                    "openWorldHint": name == ToolName.EXECUTE_PROBE_PLAN,
                },
            )(handlers[name])
