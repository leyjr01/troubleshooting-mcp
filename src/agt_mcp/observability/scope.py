"""Exact typed identifier matching; never infer identifiers from free text."""

from agt_mcp.observability.models import ObservabilityQuery, SignalObservation, TraceObservation


def matches(item: SignalObservation, query: ObservabilityQuery) -> bool:
    keys = item.keys.model_dump()
    if isinstance(item, TraceObservation):
        keys["trace_id"] = item.trace_id
    return (
        item.environment_id == query.environment_id
        and item.resource_id in query.resource_refs
        and query.time_window.start <= item.timestamp <= query.time_window.end
        and item.signal in query.signal_types
        and (not query.trace_id or keys["trace_id"] == query.trace_id)
        and (not query.correlation_id or keys["correlation_id"] == query.correlation_id)
        and all(keys[k] == v for k, v in query.filters.model_dump(exclude_none=True).items())
    )
