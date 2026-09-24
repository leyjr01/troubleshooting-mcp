"""Scoped trace/plan lifecycle; tool inputs never contain network destinations."""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from pydantic import JsonValue

from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    ResourceNotFound,
    SanitizationError,
)
from agt_mcp.core.execution import Capability, ExecutionContext, ToolName
from agt_mcp.correlation.models import CorrelationResult
from agt_mcp.probes.models import ProbePlan
from agt_mcp.probes.planner import ProbePlanner
from agt_mcp.probes.refresh import reevaluate
from agt_mcp.probes.runner import ProbeRunner
from agt_mcp.services.correlation import CorrelationService
from agt_mcp.services.troubleshooting import TroubleshootingService
from agt_mcp.trace.builder import VirtualTraceBuilder
from agt_mcp.trace.models import TraceOperation, VirtualTrace
from agt_mcp.troubleshooting.models import TroubleshootingResult


@dataclass
class TraceRecord:
    trace: VirtualTrace
    correlation: CorrelationResult
    created: datetime
    permissions: frozenset[Capability]
    diagnosis: TroubleshootingResult | None = None
    plan: ProbePlan | None = None


class TraceService:
    def __init__(
        self, troubleshooting: TroubleshootingService, planner: ProbePlanner, runner: ProbeRunner
    ) -> None:
        self.troubleshooting, self.planner, self.runner = troubleshooting, planner, runner
        self.builder = VirtualTraceBuilder(planner.policy.config.trace)
        self.cache: OrderedDict[tuple[str, str, str], TraceRecord] = OrderedDict()

    async def execute(
        self,
        operation: TraceOperation,
        context: ExecutionContext,
        grants: frozenset[Capability],
        semantic: bool,
    ) -> dict[str, JsonValue]:
        engine = self.troubleshooting.engine
        now = engine.correlation.clock.now()
        limits = self.planner.policy.config.limits
        for key, record in list(self.cache.items()):
            if (now - record.created).total_seconds() > limits.cache_ttl_seconds:
                del self.cache[key]
        if (
            context.operation in {ToolName.TRACE_RESOURCE, ToolName.TRACE_GATEWAY_COMPONENT}
            or operation.troubleshooting_id
        ):
            diagnosis = None
            if operation.troubleshooting_id:
                cached = self.troubleshooting.cache.get(
                    (context.environment_id, context.principal_id, operation.troubleshooting_id)
                )
                if cached is None:
                    raise ResourceNotFound()
                diagnosis, needed = cached
                correlation = diagnosis.correlation_result
                if (
                    now - correlation.context.correlated_at
                ).total_seconds() > engine.config.cache_ttl_seconds:
                    raise ResourceNotFound()
                needed |= {Capability.TROUBLESHOOTING_READ, Capability.TRACE_READ}
                if not needed <= grants:
                    raise AuthorizationError()
            else:
                query = operation.query
                if (
                    query is None
                    or (context.operation == ToolName.TRACE_RESOURCE and not query.resource_id)
                    or (
                        context.operation == ToolName.TRACE_GATEWAY_COMPONENT
                        and not query.component_id
                    )
                ):
                    raise ConfigurationError()
                needed = CorrelationService.permissions(query, semantic) | {
                    Capability.CORRELATION_READ,
                    Capability.TRACE_READ,
                }
                if not needed <= grants:
                    raise AuthorizationError()
                correlation = await engine.correlation.correlate(query, context)
            trace = self.builder.build(correlation, operation.direction, operation.max_depth)
            record = TraceRecord(trace, correlation, now, frozenset(needed), diagnosis)
            key = (context.environment_id, context.principal_id, trace.id)
            self.cache[key] = record
            self.cache.move_to_end(key)
            while len(self.cache) > limits.cache_entries:
                self.cache.popitem(last=False)
        else:
            matches = [
                record
                for (env, principal, identifier), record in self.cache.items()
                if env == context.environment_id
                and principal == context.principal_id
                and (
                    identifier == operation.trace_id
                    or (
                        operation.plan_id is not None
                        and record.plan is not None
                        and record.plan.id == operation.plan_id
                    )
                )
            ]
            if len(matches) != 1:
                raise ResourceNotFound()
            record = matches[0]
            if not record.permissions <= grants:
                raise AuthorizationError()
        data: dict[str, JsonValue]
        if context.operation == ToolName.PLAN_PROBES:
            record.plan = self.planner.plan(record.trace, now, record.diagnosis)
            data = cast(dict[str, JsonValue], record.plan.model_dump(mode="json"))
        elif context.operation == ToolName.EXECUTE_PROBE_PLAN:
            if record.plan is None or record.plan.id != operation.plan_id:
                raise ResourceNotFound()
            if not {Capability.PROBE_PLAN, Capability.PROBE_EXECUTE} <= grants:
                raise AuthorizationError()
            probes = await self.runner.execute(record.plan, context)
            trace = self.builder.attach(record.trace, probes)
            diagnosis = await reevaluate(engine, record.correlation, probes, context)
            record.trace = trace
            record.diagnosis = diagnosis
            data = {
                "trace": trace.model_dump(mode="json"),
                "diagnosis": diagnosis.model_dump(mode="json"),
            }
        else:
            data = cast(dict[str, JsonValue], record.trace.model_dump(mode="json"))
            if context.operation == ToolName.EXPLAIN_TRACE:
                data["probe_plan"] = record.plan.model_dump(mode="json") if record.plan else None
        if len(str(data).encode()) > context.max_payload_bytes - 1024:
            self.cache.pop((context.environment_id, context.principal_id, record.trace.id), None)
            raise SanitizationError()
        return data
