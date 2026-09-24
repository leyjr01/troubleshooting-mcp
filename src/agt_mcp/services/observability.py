"""Normalize scoped telemetry into the existing correlation and hypothesis engines."""

import asyncio
from typing import cast

from pydantic import JsonValue

from agt_mcp.configuration.observability import ObservabilityConfig
from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    ResourceNotFound,
    SanitizationError,
)
from agt_mcp.core.execution import Capability, ExecutionContext, ToolName
from agt_mcp.correlation.models import CorrelationQuery, EvidenceAtom
from agt_mcp.correlation.rules import identity
from agt_mcp.observability.models import (
    AdapterBatch,
    EvidenceTimeline,
    ObservabilityQuery,
    ObservabilityResult,
    SignalType,
    SourceOutcome,
    TimelineEntry,
)
from agt_mcp.observability.normalization import ObservabilityNormalizer
from agt_mcp.observability.ports import ObservabilityAdapter
from agt_mcp.observability.scope import matches
from agt_mcp.probes.models import ProbeEvidence
from agt_mcp.probes.refresh import reevaluate
from agt_mcp.services.correlation import CorrelationService
from agt_mcp.services.trace import TraceService

SIGNAL_PERMISSIONS = {
    SignalType.LOG: Capability.OBSERVABILITY_LOGS,
    SignalType.METRIC: Capability.OBSERVABILITY_METRICS,
    SignalType.TRACE: Capability.OBSERVABILITY_TRACES,
    SignalType.EVENT: Capability.EVENT_READ,
}


class ObservabilityCorrelationService:
    def __init__(
        self,
        config: ObservabilityConfig,
        trace: TraceService,
        adapters: dict[str, ObservabilityAdapter],
    ) -> None:
        self.config, self.trace, self.adapters = config, trace, adapters
        self.normalizer = ObservabilityNormalizer(config.limits)

    async def execute(
        self,
        query: ObservabilityQuery,
        context: ExecutionContext,
        grants: frozenset[Capability],
        semantic: bool,
    ) -> dict[str, JsonValue]:
        engine = self.trace.troubleshooting.engine
        now = engine.correlation.clock.now()
        if query.environment_id != context.environment_id:
            raise AuthorizationError()
        if (
            query.time_window.end - query.time_window.start
        ).total_seconds() > self.config.limits.max_window_seconds:
            raise ConfigurationError()
        expected = {
            ToolName.INSPECT_LOGS: SignalType.LOG,
            ToolName.INSPECT_METRICS: SignalType.METRIC,
            ToolName.INSPECT_TRACE: SignalType.TRACE,
        }.get(context.operation)
        if expected and query.signal_types != (expected,):
            raise ConfigurationError()
        if context.operation == ToolName.INSPECT_TRACE and not query.trace_id:
            raise ConfigurationError()
        warnings: set[str] = set()
        if query.limit > self.config.limits.max_items:
            warnings.add("query_limit_clamped")
            query = query.model_copy(update={"limit": self.config.limits.max_items})
        virtual_trace = None
        probes: tuple[ProbeEvidence, ...] = ()
        requested = set(query.resource_refs)
        if query.virtual_trace_id:
            record = self.trace.cache.get(
                (context.environment_id, context.principal_id, query.virtual_trace_id)
            )
            if (
                record is None
                or (now - record.created).total_seconds()
                > self.trace.planner.policy.config.limits.cache_ttl_seconds
            ):
                raise ResourceNotFound()
            if not record.permissions | {Capability.TRACE_READ} <= grants:
                raise AuthorizationError()
            original, virtual_trace, probes = record.correlation, record.trace, record.trace.probes
            resources = {
                h.reference
                for h in virtual_trace.hops
                if h.kind == "resource" and h.structural_status == "RESOLVED"
            }
        else:
            if not requested and query.trace_id and not query.gateway_component_refs:
                requested = {
                    b.resource_id
                    for s in self.config.sources
                    if s.enabled and s.environment_id == context.environment_id
                    for b in s.bindings
                    if b.keys.trace_id == query.trace_id
                }
            if not requested and not query.gateway_component_refs:
                raise ResourceNotFound()
            if len(query.gateway_component_refs) > 1:
                raise ConfigurationError()
            subject = CorrelationQuery(
                resource_id=sorted(requested)[0] if requested else None,
                component_id=next(iter(query.gateway_component_refs), None),
                time_window=query.time_window,
                include_knowledge=False,
                include_history=False,
            )
            needed = CorrelationService.permissions(subject, semantic) | {
                Capability.CORRELATION_READ
            }
            if not needed <= grants:
                raise AuthorizationError()
            original = await engine.correlation.correlate(subject, context)
            resources = {n.id for n in original.topology_context.nodes}
        if requested and not requested <= resources:
            raise AuthorizationError()
        if query.gateway_component_refs and not set(query.gateway_component_refs) <= {
            c.id for c in original.component_context
        }:
            raise AuthorizationError()
        if query.gateway_component_refs:
            resources &= {
                r
                for c in original.component_context
                if c.id in query.gateway_component_refs
                for r in c.resources
            }
        resources &= requested or resources
        if not resources or len(resources) > self.config.limits.max_resources:
            raise ConfigurationError()
        query = query.model_copy(update={"resource_refs": tuple(sorted(resources))})
        # Validate cached-trace windows too, before contacting an external source.
        engine.correlation.context(
            original.context.request.model_copy(update={"time_window": query.time_window}),
            context,
        )
        outcomes = []
        atoms: dict[str, EvidenceAtom] = {}
        for signal in query.signal_types:
            if signal == SignalType.EVENT:
                outcomes.append(
                    SourceOutcome(source_id="runtime-events", signal=signal, status="OK")
                )
                continue
            sources = [
                s
                for s in self.config.sources
                if s.enabled and s.environment_id == context.environment_id and signal in s.usage
            ]
            if not sources:
                outcomes.append(
                    SourceOutcome(source_id="not-configured", signal=signal, status="UNAVAILABLE")
                )
            for source in sorted(sources, key=lambda s: s.id):
                status = "OK"
                if SIGNAL_PERMISSIONS[signal] not in grants:
                    status = "FORBIDDEN"
                else:
                    adapter = self.adapters.get(source.id)
                    scoped = resources & {b.resource_id for b in source.bindings}
                    if not scoped:
                        status = "UNSUPPORTED"
                    elif adapter is None or signal not in adapter.capabilities():
                        status = "UNAVAILABLE"
                    else:
                        selected_query = query.model_copy(
                            update={
                                "resource_refs": tuple(sorted(scoped)),
                                "signal_types": (signal,),
                            }
                        )
                        try:
                            async with asyncio.timeout(self.config.limits.source_timeout_seconds):
                                if await adapter.health() != "AVAILABLE":
                                    raise ConnectionError()
                                batch = AdapterBatch.model_validate(
                                    (await adapter.query(selected_query)).model_dump()
                                )
                                if len(batch.observations) > selected_query.limit:
                                    raise ValueError("adapter limit violation")
                                source_atoms = {}
                                for row in batch.observations:
                                    if row.signal != signal:
                                        raise ValueError("unexpected signal type")
                                    if (
                                        not query.time_window.start
                                        <= row.timestamp
                                        <= query.time_window.end
                                    ):
                                        warnings.add("out_of_window_signal")
                                        continue
                                    atom = self.normalizer.canonicalize(
                                        row, selected_query, source, now
                                    )
                                    if not matches(row, selected_query):
                                        raise ValueError("adapter filter violation")
                                    source_atoms[atom.evidence.id] = atom
                                warnings.update(batch.warnings)
                                atoms.update(source_atoms)
                        except AuthorizationError:
                            status = "FORBIDDEN"
                        except TimeoutError:
                            status = "TIMEOUT"
                        except (ValueError, KeyError, TypeError, OverflowError):
                            status = "INVALID_DATA"
                        except Exception:
                            status = "UNAVAILABLE"
                outcomes.append(SourceOutcome(source_id=source.id, signal=signal, status=status))
        ordered = sorted(
            atoms.values(),
            key=lambda a: (a.evidence.timestamp, a.evidence.resource_id, a.evidence.id),
        )
        if len(ordered) > query.limit:
            warnings.add("evidence_limit_reached")
        diagnosis = await reevaluate(
            engine,
            original,
            probes,
            context,
            additional=tuple(ordered[: query.limit]),
            time_window=query.time_window,
            resource_scope=frozenset(resources),
        )
        correlated = diagnosis.correlation_result
        # The original engine owns deduplication, bounds and temporal relevance.
        evidence = tuple(e for group in correlated.evidence_sets for e in group.evidence)
        timeline = EvidenceTimeline(
            environment_id=query.environment_id,
            time_window=query.time_window,
            entries=tuple(
                TimelineEntry(
                    evidence_id=t.evidence_id,
                    resource_id=t.resource_id,
                    timestamp=t.timestamp,
                    category=t.event_type,
                    observation=t.observation,
                    provenance=t.provenance,
                )
                for t in sorted(
                    correlated.timeline,
                    key=lambda t: (t.timestamp or now, t.resource_id, t.evidence_id),
                )
                if t.relevant and t.timestamp is not None
            ),
        )
        warnings.update(w.code for w in correlated.warnings)
        if virtual_trace:
            hops = tuple(
                h.model_copy(
                    update={
                        "evidence_refs": tuple(
                            sorted(
                                set(h.evidence_refs)
                                | {e.id for e in evidence if e.resource_id == h.reference}
                            )
                        )
                    }
                )
                for h in virtual_trace.hops
            )
            virtual_trace = virtual_trace.model_copy(update={"hops": hops})
        result = ObservabilityResult(
            id=identity("observability-result", query.model_dump_json(), *(e.id for e in evidence)),
            query=query,
            status="PARTIAL" if warnings or any(s.status != "OK" for s in outcomes) else "COMPLETE",
            evidence=evidence,
            timeline=timeline,
            sources=tuple(outcomes),
            warnings=tuple(sorted(warnings)),
            virtual_trace=virtual_trace,
            diagnosis=diagnosis,
        )
        if len(result.model_dump_json().encode()) > context.max_payload_bytes - 1024:
            raise SanitizationError()
        return cast(dict[str, JsonValue], result.model_dump(mode="json"))
