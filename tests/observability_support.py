"""Offline telemetry fixtures sharing the existing canonical runtime snapshot."""

from datetime import timedelta

from agt_mcp.configuration.observability import (
    ObservabilityConfig,
    ObservabilitySource,
    ResourceBinding,
)
from agt_mcp.correlation.models import TimeWindow
from agt_mcp.datasources.observability_memory import InMemoryObservabilityAdapter
from agt_mcp.observability.models import (
    CorrelationKeys,
    LogObservation,
    MetricObservation,
    ObservabilityQuery,
    SignalType,
    TraceObservation,
)
from agt_mcp.services.observability import ObservabilityCorrelationService
from tests.correlation_support import NOW
from tests.unit.test_trace_service import service as trace_service


def source(id="telemetry", **changes):
    base = ObservabilitySource(
        id=id,
        type="memory",
        enabled=True,
        environment_id="demo",
        usage=(SignalType.LOG, SignalType.METRIC, SignalType.TRACE),
        bindings=tuple(
            ResourceBinding(
                environment_id="demo",
                resource_id=r,
                keys=CorrelationKeys(namespace="example", service=r),
                selectors={"namespace": "example", "service": r},
            )
            for r in ("service", "pod", "slice")
        ),
    )
    return ObservabilitySource.model_validate({**base.model_dump(), **changes})


def query(**changes):
    base = ObservabilityQuery(
        environment_id="demo",
        resource_refs=("service", "pod", "slice"),
        time_window=TimeWindow(start=NOW - timedelta(minutes=5), end=NOW),
    )
    return ObservabilityQuery.model_validate({**base.model_dump(), **changes})


def log(id="log-one", **changes):
    base = dict(
        id=id,
        environment_id="demo",
        source_id="telemetry",
        resource_id="pod",
        timestamp=NOW - timedelta(seconds=90),
        severity="ERROR",
        message="APIcast readiness failed; backend returned 503",
        keys=CorrelationKeys(namespace="example", service="pod"),
    )
    return LogObservation(**(base | changes))


def metric(**changes):
    base = dict(
        id="metric-one",
        environment_id="demo",
        source_id="telemetry",
        resource_id="service",
        timestamp=NOW - timedelta(seconds=60),
        metric="backend_latency_seconds",
        value=3.2,
        keys=CorrelationKeys(namespace="example", service="service"),
    )
    return MetricObservation(**(base | changes))


def span(**changes):
    base = dict(
        id="span-one",
        environment_id="demo",
        source_id="telemetry",
        resource_id="service",
        timestamp=NOW - timedelta(seconds=30),
        trace_id="trace-123",
        span_id="span-456",
        service="backend",
        operation="GET /api",
        duration_ms=3200,
        status="ERROR",
        keys=CorrelationKeys(namespace="example", service="service", trace_id="trace-123"),
    )
    return TraceObservation(**(base | changes))


def service(rows=None, settings=None):
    settings = settings or ObservabilityConfig(sources=(source(),))
    return ObservabilityCorrelationService(
        settings,
        trace_service(),
        {s.id: InMemoryObservabilityAdapter(s, rows or ()) for s in settings.sources},
    )
