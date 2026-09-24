"""Read-only correlation tools; cached results are scoped to the caller."""

from fastmcp import FastMCP

from agt_mcp.core.execution import ToolName
from agt_mcp.core.models import Identifier
from agt_mcp.correlation.models import CorrelationOperation, CorrelationQuery
from agt_mcp.mcp.dispatch import Dispatcher
from agt_mcp.mcp.responses import ToolResponse


def register_correlation_tools(server: FastMCP, dispatcher: Dispatcher) -> None:
    async def correlate_evidence(
        query: CorrelationQuery,
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.CORRELATE_EVIDENCE,
            environment_id,
            correlation_id,
            correlation_operation=CorrelationOperation(query=query),
        )

    async def get_correlation_timeline(
        result_id: Identifier,
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.GET_CORRELATION_TIMELINE,
            environment_id,
            correlation_id,
            correlation_operation=CorrelationOperation(result_id=result_id),
        )

    async def explain_correlation(
        result_id: Identifier,
        candidate_id: Identifier | None = None,
        environment_id: Identifier | None = None,
        correlation_id: str | None = None,
    ) -> ToolResponse:
        return await dispatcher.call(
            ToolName.EXPLAIN_CORRELATION,
            environment_id,
            correlation_id,
            correlation_operation=CorrelationOperation(
                result_id=result_id, candidate_id=candidate_id
            ),
        )

    for name, handler in (
        (ToolName.CORRELATE_EVIDENCE, correlate_evidence),
        (ToolName.GET_CORRELATION_TIMELINE, get_correlation_timeline),
        (ToolName.EXPLAIN_CORRELATION, explain_correlation),
    ):
        if name in dispatcher.runtime.configuration.mcp.server.enabled_tools:
            server.tool(
                name=name.value,
                description="Bounded evidence correlation; no causal finding.",
                annotations={
                    "readOnlyHint": True,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            )(handler)
