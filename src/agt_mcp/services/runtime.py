"""Read-only application services and lifecycle, with no framework objects."""

import asyncio
import builtins
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from time import monotonic
from uuid import uuid4

from pydantic import JsonValue

from agt_mcp import __version__
from agt_mcp.configuration.models import Configuration, DataSourceConfig
from agt_mcp.core.errors import (
    AuthorizationError,
    ConnectionError,
    TimeoutError,
    UnsupportedCapabilityError,
)
from agt_mcp.core.execution import TOOL_DEFINITIONS, Capability, ExecutionContext, ToolName
from agt_mcp.core.operations import Operation, OperationContext
from agt_mcp.datasources.base.adapter import DataSourceAdapter
from agt_mcp.gateways.base.adapter import GatewayAdapter
from agt_mcp.services.registry import AdapterRegistry


class Runtime:
    def __init__(
        self,
        configuration: Configuration,
        gateways: AdapterRegistry[GatewayAdapter],
        datasources: AdapterRegistry[DataSourceAdapter],
    ) -> None:
        self.configuration = configuration
        self.gateways = gateways
        self.datasources = datasources
        self.started_at: float | None = None
        self.ready = False

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        if self.ready:
            raise ConnectionError()
        self.gateways.seal()
        self.datasources.seal()
        async with AsyncExitStack() as stack:
            adapters: list[tuple[str, GatewayAdapter | DataSourceAdapter]] = [
                (entry.environment_id, entry.adapter) for entry in self.gateways.entries()
            ]
            adapters.extend(
                (entry.environment_id, entry.adapter) for entry in self.datasources.entries()
            )
            for environment_id, adapter in adapters:
                timeout = self.configuration.mcp.server.request_timeout_seconds
                context = OperationContext(
                    environment_id=environment_id,
                    principal_id="bootstrap",
                    request_id=str(uuid4()),
                    correlation_id=str(uuid4()),
                    timeout_seconds=timeout,
                )
                # Register cleanup before connect: partially initialized adapters also close.
                stack.push_async_callback(adapter.close)
                try:
                    async with asyncio.timeout(timeout):
                        await adapter.connect(context)
                except builtins.TimeoutError:
                    raise TimeoutError() from None
            self.started_at = monotonic()
            self.ready = True
            try:
                yield
            finally:
                self.ready = False

    def authorize(self, context: ExecutionContext) -> None:
        settings = self.configuration.mcp.server
        grant = settings.authorization
        definition = next(item for item in TOOL_DEFINITIONS if item.name == context.operation)
        if (
            grant.mode != "local-read-only"
            or context.principal_id != grant.principal
            or context.environment_id not in grant.environment_ids
            or context.environment_id not in {e.id for e in self.configuration.environments}
            or not definition.required_permissions <= grant.permissions
        ):
            raise AuthorizationError()
        if context.operation not in settings.enabled_tools:
            raise UnsupportedCapabilityError()

    def available_capabilities(self, environment_id: str) -> frozenset[Capability]:
        settings = self.configuration.mcp.server
        available: set[Capability] = set()
        for tool in TOOL_DEFINITIONS:
            if tool.name in settings.enabled_tools:
                available.update(tool.required_capabilities)
        if not any(
            Operation.DISCOVER_GATEWAY in e.adapter.capabilities()
            for e in self.gateways.entries(environment_id)
        ) or (Operation.DISCOVER_GATEWAY not in self.configuration.application.allowed_operations):
            available.discard(Capability.GATEWAY_DISCOVER)
        if (
            ToolName.INSPECT_DATASOURCE in settings.enabled_tools
            and Operation.HEALTH in self.configuration.application.allowed_operations
            and any(
                Operation.HEALTH in e.adapter.capabilities()
                for e in self.datasources.entries(environment_id)
            )
        ):
            available.add(Capability.DATASOURCE_HEALTH)
        return frozenset(available) & settings.authorization.permissions

    async def execute(
        self, context: ExecutionContext, resource_id: str | None = None
    ) -> dict[str, JsonValue]:
        self.authorize(context)
        if not self.ready:
            raise ConnectionError()
        remaining = min(context.timeout_seconds, context.deadline - monotonic())
        if remaining <= 0:
            raise TimeoutError()
        try:
            async with asyncio.timeout(remaining):
                return await self._dispatch(context, resource_id)
        except builtins.TimeoutError:
            raise TimeoutError() from None

    async def _dispatch(
        self, context: ExecutionContext, resource_id: str | None
    ) -> dict[str, JsonValue]:
        environment = context.environment_id
        operation = context.operation
        if operation == ToolName.SYSTEM_HEALTH:
            return {
                "server": self.configuration.mcp.server.name,
                "version": __version__,
                "status": "healthy",
                "uptime_seconds": monotonic() - (self.started_at or monotonic()),
                "configured_environment": environment,
                "registered_gateways": len(self.gateways.entries(environment)),
                "registered_datasources": len(self.datasources.entries(environment)),
            }
        if operation == ToolName.LIST_CAPABILITIES:
            available = self.available_capabilities(environment)
            tools: list[JsonValue] = []
            for definition in TOOL_DEFINITIONS:
                if (
                    definition.name in self.configuration.mcp.server.enabled_tools
                    and definition.required_permissions <= available
                ):
                    tools.append(definition.model_dump(mode="json"))
            return {
                "capabilities": [capability.value for capability in sorted(available)],
                "tools": tools,
            }
        if operation == ToolName.LIST_ENVIRONMENTS:
            return {
                "environments": [
                    {"id": e.id, "name": e.name, "type": e.type}
                    for e in self.configuration.environments
                    if e.id in self.configuration.mcp.server.authorization.environment_ids
                ]
            }
        if operation == ToolName.LIST_GATEWAYS:
            return {
                "gateways": [
                    {
                        "id": e.id,
                        "environment_id": e.environment_id,
                        "type": "in-memory",
                        "status": "ready",
                        "capabilities": [
                            capability.value
                            for capability in sorted(
                                e.adapter.capabilities()
                                & frozenset(self.configuration.application.allowed_operations)
                            )
                        ],
                    }
                    for e in self.gateways.entries(environment)
                ]
            }
        if operation == ToolName.LIST_DATASOURCES:
            return {
                "datasources": [
                    self.datasource_metadata(source)
                    for source in self.configuration.datasources
                    if source.environment_id == environment
                ]
            }
        if operation == ToolName.INSPECT_DATASOURCE:
            source = next(
                (
                    s
                    for s in self.configuration.datasources
                    if s.id == resource_id and s.environment_id == environment
                ),
                None,
            )
            if source is None:
                raise UnsupportedCapabilityError()
            metadata = self.datasource_metadata(source)
            if source.enabled:
                self.require_adapter_capability(Capability.DATASOURCE_HEALTH, context)
                adapter = self.datasources.resolve(source.id, environment)
                if Operation.HEALTH not in adapter.capabilities():
                    raise UnsupportedCapabilityError()
                status = (await adapter.health(context)).status
                metadata["health_state"] = (
                    status if status in {"healthy", "unhealthy"} else "unknown"
                )
            return metadata
        self.require_adapter_capability(Capability.GATEWAY_DISCOVER, context)
        adapter_gateway = self.gateways.resolve(resource_id or "", environment)
        if Operation.DISCOVER_GATEWAY not in adapter_gateway.capabilities():
            raise UnsupportedCapabilityError()
        gateway = await adapter_gateway.discover_gateway(context)
        if gateway.environment_id != environment:
            raise AuthorizationError()
        # Explicit safe projection, never labels/annotations/raw endpoints.
        return {
            "id": gateway.id,
            "environment_id": gateway.environment_id,
            "kind": gateway.kind,
            "name": gateway.name,
            "provider": gateway.provider,
            "version": gateway.version,
        }

    def require_adapter_capability(self, capability: Capability, context: ExecutionContext) -> None:
        if capability not in self.configuration.mcp.server.authorization.permissions:
            raise AuthorizationError()
        if capability not in self.available_capabilities(context.environment_id):
            raise UnsupportedCapabilityError()

    @staticmethod
    def datasource_metadata(source: DataSourceConfig) -> dict[str, JsonValue]:
        return {
            "id": source.id,
            "environment_id": source.environment_id,
            "type": source.type,
            "provider": source.provider,
            "enabled": source.enabled,
            "usage": list(source.usage),
            "health_state": "unknown" if source.enabled else "disabled",
        }
