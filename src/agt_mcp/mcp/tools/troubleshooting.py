"""Opt-in read-only troubleshooting tools; no step execution endpoint."""

from collections.abc import Awaitable, Callable

from fastmcp import FastMCP

from agt_mcp.core.execution import ToolName
from agt_mcp.core.models import Identifier
from agt_mcp.correlation.models import CorrelationQuery
from agt_mcp.mcp.dispatch import Dispatcher
from agt_mcp.mcp.responses import ToolResponse
from agt_mcp.troubleshooting.models import TroubleshootingOperation


def register_troubleshooting_tools(server: FastMCP, dispatcher: Dispatcher) -> None:
    def factory(name: ToolName) -> Callable[..., Awaitable[ToolResponse]]:
        async def diagnose(
            query: CorrelationQuery,
            environment_id: Identifier | None = None,
            correlation_id: str | None = None,
        ) -> ToolResponse:
            return await dispatcher.call(
                name,
                environment_id,
                correlation_id,
                troubleshooting_operation=TroubleshootingOperation(query=query),
            )

        return diagnose

    async def explain(
        hypothesis_id: Identifier,
        result_id: Identifier | None = None,
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.EXPLAIN_HYPOTHESIS,
            environment_id,
            correlation_id,
            troubleshooting_operation=TroubleshootingOperation(
                hypothesis_id=hypothesis_id, result_id=result_id
            ),
        )

    async def plan(
        result_id: Identifier,
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.GET_TROUBLESHOOTING_PLAN,
            environment_id,
            correlation_id,
            troubleshooting_operation=TroubleshootingOperation(result_id=result_id),
        )

    handlers = {
        ToolName.DIAGNOSE_COMPONENT: factory(ToolName.DIAGNOSE_COMPONENT),
        ToolName.DIAGNOSE_GATEWAY: factory(ToolName.DIAGNOSE_GATEWAY),
        ToolName.DIAGNOSE_API: factory(ToolName.DIAGNOSE_API),
        ToolName.EXPLAIN_HYPOTHESIS: explain,
        ToolName.GET_TROUBLESHOOTING_PLAN: plan,
    }
    for name, handler in handlers.items():
        if name in dispatcher.runtime.configuration.mcp.server.enabled_tools:
            server.tool(
                name=name.value,
                description="Evaluate hypotheses or read an inspection plan; never execute actions",
                annotations={
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            )(handler)
