"""Explicit composition root: only opted-in in-memory adapters can be activated."""

from agt_mcp.configuration.models import Configuration
from agt_mcp.core.errors import ConfigurationError
from agt_mcp.core.models import Gateway
from agt_mcp.datasources.base.adapter import DataSourceAdapter
from agt_mcp.datasources.memory import InMemoryDataSourceAdapter
from agt_mcp.gateways.base.adapter import GatewayAdapter
from agt_mcp.gateways.memory import InMemoryGatewayAdapter
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
    return Runtime(configuration, gateways, datasources)
