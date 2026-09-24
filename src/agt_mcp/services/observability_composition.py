"""Provider composition outside neutral contracts and correlation core."""

from agt_mcp.configuration.observability import ObservabilityConfig
from agt_mcp.credentials.providers import EnvironmentVariableCredentialProvider
from agt_mcp.datasources.observability_memory import InMemoryObservabilityAdapter
from agt_mcp.datasources.prometheus import ApprovedMetricsHTTP, PrometheusObservabilityAdapter
from agt_mcp.observability.ports import ObservabilityAdapter


def build_observability(config: ObservabilityConfig) -> dict[str, ObservabilityAdapter]:
    adapters: dict[str, ObservabilityAdapter] = {}
    for source in config.sources:
        if not source.enabled:
            continue
        if source.type == "memory":
            adapters[source.id] = InMemoryObservabilityAdapter(source)
        else:
            provider = EnvironmentVariableCredentialProvider(
                source.environment_id,
                frozenset({source.credentials.reference}) if source.credentials else frozenset(),
            )
            adapters[source.id] = PrometheusObservabilityAdapter(
                source, config.limits, ApprovedMetricsHTTP(source, config.limits, provider)
            )
    return adapters
