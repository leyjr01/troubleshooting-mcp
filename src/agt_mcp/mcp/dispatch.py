"""Single request boundary for safe structured responses and audit envelopes."""

import asyncio
import json
import logging
from time import monotonic

from agt_mcp.core.errors import SanitizationError
from agt_mcp.core.execution import KNOWLEDGE_TOOLS, SEMANTIC_TOOLS, ToolName
from agt_mcp.core.runtime import RuntimeQuery
from agt_mcp.correlation.models import CorrelationOperation
from agt_mcp.gateways.threescale.models import GatewayQuery
from agt_mcp.mcp.context import create_context
from agt_mcp.mcp.error_mapping import error_code
from agt_mcp.mcp.responses import ToolResponse
from agt_mcp.rag.contracts import RetrievalQuery
from agt_mcp.services.runtime import Runtime
from agt_mcp.trace.models import TraceOperation
from agt_mcp.troubleshooting.models import TroubleshootingOperation


class Dispatcher:
    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.logger = logging.getLogger("agt_mcp.audit")

    async def call(
        self,
        tool: ToolName,
        environment_id: str | None = None,
        correlation_id: str | None = None,
        resource_id: str | None = None,
        runtime_query: RuntimeQuery | None = None,
        gateway_query: GatewayQuery | None = None,
        knowledge_query: RetrievalQuery | None = None,
        correlation_operation: CorrelationOperation | None = None,
        troubleshooting_operation: TroubleshootingOperation | None = None,
        trace_operation: TraceOperation | None = None,
    ) -> ToolResponse:
        context = create_context(self.runtime.configuration, tool, environment_id, correlation_id)
        started = monotonic()
        status = "error"
        code: str | None = None
        try:
            data = (
                await self.runtime.execute(context, resource_id, trace_operation=trace_operation)
                if trace_operation is not None
                else await self.runtime.execute(
                    context, resource_id, troubleshooting_operation=troubleshooting_operation
                )
                if troubleshooting_operation is not None
                else await self.runtime.execute(
                    context, resource_id, correlation_operation=correlation_operation
                )
                if correlation_operation is not None
                else await self.runtime.execute(
                    context, resource_id, knowledge_query=knowledge_query
                )
                if knowledge_query is not None
                else await self.runtime.execute(context, resource_id, runtime_query, gateway_query)
                if gateway_query is not None
                else await self.runtime.execute(context, resource_id, runtime_query)
                if runtime_query is not None
                else await self.runtime.execute(context, resource_id)
            )
            result = ToolResponse(
                ok=True,
                request_id=context.request_id,
                correlation_id=context.correlation_id,
                environment_id=context.environment_id,
                data=data,
            )
            if len(result.model_dump_json().encode("utf-8")) > context.max_payload_bytes:
                raise SanitizationError()
            status = "ok"
            return result
        except asyncio.CancelledError:
            status = "cancelled"
            raise
        except Exception as exc:
            # Deliberately broad only at the public transport boundary.
            code = error_code(exc)
            return ToolResponse(
                ok=False,
                request_id=context.request_id,
                correlation_id=context.correlation_id,
                environment_id=context.environment_id,
                error=code,
            )
        finally:
            # Only configured identities may appear in audit; never raw arguments.
            known_environment = context.environment_id in {
                environment.id for environment in self.runtime.configuration.environments
            }
            datasource = next(
                (
                    source.id
                    for source in self.runtime.configuration.datasources
                    if source.id == resource_id and source.environment_id == context.environment_id
                ),
                None,
            )
            semantic_adapters = self.runtime.gateway_discovery.adapters(context.environment_id)
            legacy_gateway_ids = {
                entry.id
                for entry in self.runtime.gateways.entries(context.environment_id)
                if entry.id not in semantic_adapters
            }
            semantic_request = tool in SEMANTIC_TOOLS or (
                tool == ToolName.DISCOVER_GATEWAY
                and (
                    gateway_query is not None
                    or (bool(semantic_adapters) and resource_id not in legacy_gateway_ids)
                )
            )
            self.logger.info(
                json.dumps(
                    {
                        "event": "tool_finished",
                        "operation": tool.value,
                        "request_id": context.request_id,
                        "correlation_id": context.correlation_id,
                        "environment_id": context.environment_id
                        if known_environment
                        else "unrecognized",
                        "adapter": "knowledge"
                        if tool in KNOWLEDGE_TOOLS
                        else "threescale"
                        if semantic_request
                        else "kubernetes-runtime"
                        if runtime_query is not None
                        else "in-memory"
                        if tool in {ToolName.DISCOVER_GATEWAY, ToolName.INSPECT_DATASOURCE}
                        else "application",
                        "datasource": datasource,
                        "duration_ms": round((monotonic() - started) * 1000, 3),
                        "result_status": status,
                        "error_category": code,
                    }
                )
            )
