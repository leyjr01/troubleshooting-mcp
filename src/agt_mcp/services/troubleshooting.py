"""Permission-scoped bounded diagnostic cache. No action or probe execution."""

from collections import OrderedDict
from typing import cast

from pydantic import JsonValue

from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    ResourceNotFound,
    SanitizationError,
)
from agt_mcp.core.execution import Capability, ExecutionContext, ToolName
from agt_mcp.services.correlation import CorrelationService
from agt_mcp.troubleshooting.engine import TroubleshootingEngine
from agt_mcp.troubleshooting.models import TroubleshootingOperation, TroubleshootingResult


class TroubleshootingService:
    def __init__(self, engine: TroubleshootingEngine) -> None:
        self.engine = engine
        self.cache: OrderedDict[
            tuple[str, str, str], tuple[TroubleshootingResult, frozenset[Capability]]
        ] = OrderedDict()

    async def execute(
        self,
        operation: TroubleshootingOperation,
        context: ExecutionContext,
        grants: frozenset[Capability],
        semantic: bool,
    ) -> dict[str, JsonValue]:
        now = self.engine.correlation.clock.now()
        for key, (result, _) in list(self.cache.items()):
            if (
                now - result.correlation_result.context.correlated_at
            ).total_seconds() > self.engine.config.cache_ttl_seconds:
                del self.cache[key]
        if context.operation in {
            ToolName.DIAGNOSE_COMPONENT,
            ToolName.DIAGNOSE_GATEWAY,
            ToolName.DIAGNOSE_API,
        }:
            query = operation.query
            if (
                query is None
                or (context.operation == ToolName.DIAGNOSE_COMPONENT and not query.component_id)
                or (context.operation == ToolName.DIAGNOSE_GATEWAY and not query.gateway_id)
                or (context.operation == ToolName.DIAGNOSE_API and not query.resource_id)
            ):
                raise ConfigurationError()
            needed = CorrelationService.permissions(query, semantic) | {Capability.CORRELATION_READ}
            if not needed <= grants:
                raise AuthorizationError()
            try:
                result = await self.engine.diagnose(query, context)
            except ResourceNotFound:
                if context.operation != ToolName.DIAGNOSE_API:
                    raise
                return {
                    "status": "LIMITED",
                    "hypotheses": [],
                    "root_cause_candidates": [],
                    "missing_capabilities": ["API_MAPPING_NOT_AVAILABLE"],
                    "warnings": ["API_RESOURCE_NOT_ASSOCIATED_WITH_RUNTIME"],
                    "troubleshooting_plan": {"steps": [], "executed": False},
                }
            if len(result.model_dump_json().encode()) > context.max_payload_bytes - 1024:
                raise SanitizationError()
            key = (context.environment_id, context.principal_id, result.id)
            self.cache[key] = result, needed
            self.cache.move_to_end(key)
            while len(self.cache) > self.engine.config.cache_entries:
                self.cache.popitem(last=False)
            return cast(dict[str, JsonValue], result.model_dump(mode="json"))
        records = [
            record
            for (env, principal, identifier), record in self.cache.items()
            if env == context.environment_id
            and principal == context.principal_id
            and operation.result_id in {None, identifier}
        ]
        if context.operation == ToolName.EXPLAIN_HYPOTHESIS:
            for result, needed in records:
                for hypothesis in result.hypotheses:
                    if hypothesis.id == operation.hypothesis_id:
                        if not needed <= grants:
                            raise AuthorizationError()
                        return {
                            "result_id": result.id,
                            "definition": self.engine.catalog.by_id[
                                hypothesis.definition_id
                            ].model_dump(mode="json"),
                            "hypothesis": hypothesis.model_dump(mode="json"),
                        }
            raise ResourceNotFound()
        if operation.result_id is None or len(records) != 1:
            raise ResourceNotFound()
        result, needed = records[0]
        if not needed <= grants:
            raise AuthorizationError()
        return {
            "result_id": result.id,
            "troubleshooting_plan": result.troubleshooting_plan.model_dump(mode="json"),
            "missing_capabilities": list(result.missing_capabilities),
        }
