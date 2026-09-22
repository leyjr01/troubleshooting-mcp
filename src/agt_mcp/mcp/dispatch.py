"""Single request boundary for safe structured responses and audit envelopes."""

import asyncio
import json
import logging
from time import monotonic

from agt_mcp.core.errors import SanitizationError
from agt_mcp.core.execution import ToolName
from agt_mcp.mcp.context import create_context
from agt_mcp.mcp.error_mapping import error_code
from agt_mcp.mcp.responses import ToolResponse
from agt_mcp.services.runtime import Runtime


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
    ) -> ToolResponse:
        context = create_context(self.runtime.configuration, tool, environment_id, correlation_id)
        started = monotonic()
        status = "error"
        code: str | None = None
        try:
            data = await self.runtime.execute(context, resource_id)
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
                        "adapter": "in-memory"
                        if tool in {ToolName.DISCOVER_GATEWAY, ToolName.INSPECT_DATASOURCE}
                        else "application",
                        "datasource": datasource,
                        "duration_ms": round((monotonic() - started) * 1000, 3),
                        "result_status": status,
                        "error_category": code,
                    }
                )
            )
