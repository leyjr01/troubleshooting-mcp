"""Explicit composition root for opted-in local and runtime-backed adapters."""

from agt_mcp.configuration.models import Configuration
from agt_mcp.core.errors import ConfigurationError
from agt_mcp.core.models import Gateway
from agt_mcp.datasources.base.adapter import DataSourceAdapter
from agt_mcp.datasources.kubernetes.adapter import KubernetesRuntimeAdapter
from agt_mcp.datasources.memory import InMemoryDataSourceAdapter
from agt_mcp.gateways.base.adapter import GatewayAdapter
from agt_mcp.gateways.memory import InMemoryGatewayAdapter
from agt_mcp.gateways.threescale.adapter import ThreeScaleGatewayAdapter
from agt_mcp.services.discovery import RuntimeDiscoveryService
from agt_mcp.services.registry import AdapterEntry, AdapterRegistry
from agt_mcp.services.runtime import Runtime


def build_runtime(configuration: Configuration) -> Runtime:
    known = {environment.id for environment in configuration.environments}
    if (
        configuration.application.environment not in known
        or not set(configuration.mcp.server.authorization.environment_ids) <= known
    ):
        raise ConfigurationError()
    gateways = AdapterRegistry[GatewayAdapter]()
    datasources = AdapterRegistry[DataSourceAdapter]()
    runtime_adapters = {
        e.id: KubernetesRuntimeAdapter(e)
        for e in configuration.environments
        if e.enabled and e.runtime is not None
    }
    for source in configuration.datasources:
        if source.environment_id not in known:
            raise ConfigurationError()
        if not source.enabled:
            continue
        if source.type != "memory" or source.provider != "in-memory" or source.credentials:
            raise ConfigurationError()
        datasources.register(
            AdapterEntry(
                id=source.id,
                environment_id=source.environment_id,
                adapter=InMemoryDataSourceAdapter(source.environment_id),
            )
        )
    for gateway in configuration.gateways:
        if gateway.environment_id not in known:
            raise ConfigurationError()
        if not gateway.enabled:
            continue
        if gateway.adapter == "threescale":
            runtime_adapter = runtime_adapters.get(gateway.environment_id)
            if runtime_adapter is None or gateway.datasource_id is not None:
                raise ConfigurationError()
            gateways.register(
                AdapterEntry(
                    id=gateway.id,
                    environment_id=gateway.environment_id,
                    adapter=ThreeScaleGatewayAdapter(
                        gateway.environment_id,
                        runtime_adapter,
                        gateway.discovery,
                        max_edges=runtime_adapter.settings.discovery.limits.max_relationships,
                        max_components=min(
                            200, runtime_adapter.settings.discovery.limits.max_topology_nodes
                        ),
                    ),
                )
            )
            continue
        if gateway.adapter != "in-memory":
            raise ConfigurationError()
        model = Gateway(
            id=gateway.id,
            name=gateway.id,
            environment_id=gateway.environment_id,
            provider="in-memory",
            version="synthetic-1",
            endpoint_reference="memory:gateway",
        )
        gateways.register(
            AdapterEntry(
                id=gateway.id,
                environment_id=gateway.environment_id,
                adapter=InMemoryGatewayAdapter(model),
            )
        )
    runtime = Runtime(configuration, gateways, datasources)
    runtime.discovery = RuntimeDiscoveryService(runtime_adapters)
    return runtime
