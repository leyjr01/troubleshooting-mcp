"""Bounded provider-neutral observations; external text is always untrusted data."""

from datetime import UTC
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, StringConstraints, field_validator, model_validator

from agt_mcp.core.models import Evidence, Identifier, Model, Provenance
from agt_mcp.correlation.models import TimeWindow
from agt_mcp.trace.models import VirtualTrace
from agt_mcp.troubleshooting.models import TroubleshootingResult

SmallText = Annotated[str, StringConstraints(max_length=512)]
MatchValue = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_.:/-]{1,128}$")]
LabelName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")]


class SignalType(StrEnum):
    LOG = "LOG"
    METRIC = "METRIC"
    TRACE = "TRACE"
    EVENT = "EVENT"


class MetricIntent(StrEnum):
    AVAILABILITY = "availability"
    ERROR_RATE = "error_rate"
    LATENCY = "latency"
    RESTARTS = "restarts"
    RESOURCE_USAGE = "resource_usage"


class CorrelationKeys(Model):
    resource_uid: MatchValue | None = None
    namespace: MatchValue | None = None
    pod: MatchValue | None = None
    service: MatchValue | None = None
    gateway_component: MatchValue | None = None
    hostname: MatchValue | None = None
    trace_id: MatchValue | None = None
    request_id: MatchValue | None = None
    correlation_id: MatchValue | None = None


class ObservabilityQuery(Model):
    environment_id: Identifier
    time_window: TimeWindow
    resource_refs: tuple[Identifier, ...] = Field(default=(), max_length=12)
    gateway_component_refs: tuple[Identifier, ...] = Field(default=(), max_length=12)
    virtual_trace_id: Identifier | None = None
    trace_id: MatchValue | None = None
    correlation_id: MatchValue | None = None
    signal_types: tuple[SignalType, ...] = Field(
        default=(SignalType.LOG, SignalType.METRIC, SignalType.TRACE, SignalType.EVENT),
        min_length=1,
        max_length=4,
    )
    filters: CorrelationKeys = CorrelationKeys()
    metric_intent: MetricIntent = MetricIntent.AVAILABILITY
    metric_mode: Literal["instant", "range"] = "range"
    step_seconds: int = Field(default=60, ge=1, le=3600)
    limit: int = Field(default=50, ge=1, le=200)

    @field_validator("time_window")
    @classmethod
    def utc_window(cls, window: TimeWindow) -> TimeWindow:
        return TimeWindow(start=window.start.astimezone(UTC), end=window.end.astimezone(UTC))

    @model_validator(mode="after")
    def scoped(self) -> Self:
        if not (
            self.resource_refs
            or self.gateway_component_refs
            or self.virtual_trace_id
            or self.trace_id
        ):
            raise ValueError("resource or trusted trace context required")
        if len(set(self.signal_types)) != len(self.signal_types):
            raise ValueError("duplicate signal type")
        return self


class Observation(Model):
    id: Identifier
    environment_id: Identifier
    source_id: Identifier
    resource_id: Identifier
    timestamp: AwareDatetime
    keys: CorrelationKeys = CorrelationKeys()
    labels: dict[LabelName, SmallText] = Field(default_factory=dict, max_length=32)

    @field_validator("timestamp")
    @classmethod
    def utc_timestamp(cls, value: AwareDatetime) -> AwareDatetime:
        return value.astimezone(UTC)


class LogObservation(Observation):
    signal: Literal[SignalType.LOG] = SignalType.LOG
    severity: Literal["DEBUG", "INFO", "WARNING", "ERROR", "UNKNOWN"] = "UNKNOWN"
    message: str = Field(max_length=65536)


class MetricObservation(Observation):
    signal: Literal[SignalType.METRIC] = SignalType.METRIC
    metric: LabelName
    value: float = Field(allow_inf_nan=False)


class TraceObservation(Observation):
    signal: Literal[SignalType.TRACE] = SignalType.TRACE
    trace_id: MatchValue
    span_id: MatchValue
    parent_span_id: MatchValue | None = None
    service: SmallText
    operation: SmallText
    duration_ms: float = Field(ge=0, allow_inf_nan=False)
    status: Literal["OK", "ERROR", "UNSET"]
    attributes: dict[LabelName, SmallText] = Field(default_factory=dict, max_length=32)

    @model_validator(mode="after")
    def trace_identity(self) -> Self:
        if self.keys.trace_id is not None and self.keys.trace_id != self.trace_id:
            raise ValueError("conflicting trace identity")
        return self


SignalObservation = Annotated[
    LogObservation | MetricObservation | TraceObservation, Field(discriminator="signal")
]


class AdapterBatch(Model):
    observations: tuple[SignalObservation, ...] = Field(default=(), max_length=200)
    warnings: tuple[
        Literal[
            "source_truncated",
            "source_limit_reached",
            "metric_intent_unavailable",
            "provider_warning",
            "out_of_window_signal",
        ],
        ...,
    ] = Field(default=(), max_length=5)


class SourceOutcome(Model):
    source_id: Identifier
    signal: SignalType
    status: Literal["OK", "FORBIDDEN", "UNAVAILABLE", "TIMEOUT", "INVALID_DATA", "UNSUPPORTED"]


class TimelineEntry(Model):
    evidence_id: Identifier
    resource_id: Identifier
    timestamp: AwareDatetime
    category: Identifier
    observation: str = Field(max_length=16384)
    provenance: Provenance


class EvidenceTimeline(Model):
    environment_id: Identifier
    time_window: TimeWindow
    entries: tuple[TimelineEntry, ...] = Field(max_length=200)
    descriptive_only: Literal[True] = True


class ObservabilityResult(Model):
    id: Identifier
    query: ObservabilityQuery
    status: Literal["COMPLETE", "PARTIAL"]
    evidence: tuple[Evidence, ...] = Field(max_length=200)
    timeline: EvidenceTimeline
    sources: tuple[SourceOutcome, ...]
    warnings: tuple[Identifier, ...]
    virtual_trace: VirtualTrace | None = None
    diagnosis: TroubleshootingResult

    @model_validator(mode="after")
    def lineage(self) -> Self:
        env = self.query.environment_id
        ids = {e.id for e in self.evidence}
        if self.timeline.environment_id != env or self.diagnosis.context.environment_id != env:
            raise ValueError("result environment mismatch")
        if any(e.environment_id != env or e.source.environment_id != env for e in self.evidence):
            raise ValueError("evidence scope mismatch")
        if any(
            t.evidence_id not in ids or t.provenance.environment_id != env
            for t in self.timeline.entries
        ):
            raise ValueError("timeline lineage mismatch")
        if self.virtual_trace and self.virtual_trace.environment_id != env:
            raise ValueError("virtual trace scope mismatch")
        return self
