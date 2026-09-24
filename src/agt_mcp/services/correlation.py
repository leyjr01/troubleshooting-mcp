"""Authorized correlation orchestration and bounded environment/principal-scoped cache."""

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
from agt_mcp.correlation.engine import EvidenceCorrelationEngine
from agt_mcp.correlation.models import CorrelationOperation, CorrelationQuery, CorrelationResult


class CorrelationService:
    def __init__(self, engine: EvidenceCorrelationEngine) -> None:
        self.engine = engine
        self.cache: OrderedDict[
            tuple[str, str, str], tuple[CorrelationResult, frozenset[Capability]]
        ] = OrderedDict()

    @staticmethod
    def permissions(query: CorrelationQuery, semantic: bool) -> frozenset[Capability]:
        needed = {Capability.RESOURCE_READ, Capability.EVENT_READ, Capability.TOPOLOGY_READ}
        if semantic or query.gateway_id or query.component_id:
            needed.update(
                {
                    Capability.GATEWAY_DISCOVER,
                    Capability.GATEWAY_COMPONENTS,
                    Capability.GATEWAY_TOPOLOGY,
                }
            )
        if query.include_knowledge:
            needed.update({Capability.KNOWLEDGE_INTERNAL, Capability.KNOWLEDGE_OFFICIAL})
        if query.include_history:
            needed.add(Capability.KNOWLEDGE_ISSUES)
        return frozenset(needed)

    async def execute(
        self,
        operation: CorrelationOperation,
        context: ExecutionContext,
        grants: frozenset[Capability],
        semantic: bool,
    ) -> dict[str, JsonValue]:
        now = self.engine.clock.now()
        for key, (result, _) in list(self.cache.items()):
            if (
                now - result.context.correlated_at
            ).total_seconds() > self.engine.config.cache_ttl_seconds:
                del self.cache[key]
        if context.operation == ToolName.CORRELATE_EVIDENCE:
            if operation.query is None:
                raise ConfigurationError()
            needed = self.permissions(operation.query, semantic)
            if not needed <= grants:
                raise AuthorizationError()
            result = await self.engine.correlate(operation.query, context)
            if len(result.model_dump_json().encode()) > context.max_payload_bytes - 1024:
                raise SanitizationError()
            key = (context.environment_id, context.principal_id, result.id)
            self.cache[key] = result, needed
            self.cache.move_to_end(key)
            while len(self.cache) > self.engine.config.cache_entries:
                self.cache.popitem(last=False)
            return cast(dict[str, JsonValue], result.model_dump(mode="json"))
        record = self.cache.get(
            (context.environment_id, context.principal_id, operation.result_id or "")
        )
        if record is None:
            raise ResourceNotFound()
        result, needed = record
        if not needed <= grants:
            raise AuthorizationError()
        if context.operation == ToolName.GET_CORRELATION_TIMELINE:
            return {
                "result_id": result.id,
                "timeline": [t.model_dump(mode="json") for t in result.timeline],
            }
        candidates = [c for c in result.candidates if operation.candidate_id in {None, c.id}]
        if not candidates:
            raise ResourceNotFound()
        return {
            "result_id": result.id,
            "engine_version": result.context.engine_version,
            "correlated_at": result.context.correlated_at.isoformat(),
            "candidates": [c.model_dump(mode="json") for c in candidates],
        }
