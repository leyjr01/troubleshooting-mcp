"""Synthetic gateway adapter with explicit lifecycle and injectable failure/delay."""

import asyncio

from agt_mcp.core.errors import (
    AuthorizationError,
    ConnectionError,
    GatewayUnavailable,
    UnsupportedCapabilityError,
)
from agt_mcp.core.models import Evidence, Gateway, Identifier, Resource
from agt_mcp.core.operations import Health, Operation, OperationContext
from agt_mcp.gateways.base.adapter import GatewayAdapter
from agt_mcp.topology.models import Dependency


class InMemoryGatewayAdapter(GatewayAdapter):
    def __init__(self, gateway: Gateway, *, delay_seconds: float = 0, fail: bool = False) -> None:
        self.gateway = gateway
        self.delay_seconds = delay_seconds
        self.fail = fail
        self.connected = False

    def capabilities(self) -> frozenset[Operation]:
        return frozenset({Operation.DISCOVER_GATEWAY, Operation.HEALTH})

    def check_scope(self, context: OperationContext) -> None:
        if context.environment_id != self.gateway.environment_id:
            raise AuthorizationError()

    async def connect(self, context: OperationContext) -> None:
        self.check_scope(context)
        self.connected = True

    async def ready(self, context: OperationContext) -> None:
        self.check_scope(context)
        if not self.connected:
            raise ConnectionError()
        await asyncio.sleep(self.delay_seconds)
        if self.fail:
            raise GatewayUnavailable()

    async def discover_gateway(self, context: OperationContext) -> Gateway:
        await self.ready(context)
        return self.gateway

    async def get_health(self, context: OperationContext) -> Health:
        await self.ready(context)
        return Health(status="healthy", detail_code="in-memory")

    async def get_products(self, context: OperationContext) -> tuple[Resource, ...]:
        raise UnsupportedCapabilityError()

    async def get_backends(self, context: OperationContext) -> tuple[Resource, ...]:
        raise UnsupportedCapabilityError()

    async def get_routes(self, context: OperationContext) -> tuple[Resource, ...]:
        raise UnsupportedCapabilityError()

    async def get_policies(self, context: OperationContext) -> tuple[Evidence, ...]:
        raise UnsupportedCapabilityError()

    async def get_dependencies(self, context: OperationContext) -> tuple[Dependency, ...]:
        raise UnsupportedCapabilityError()

    async def get_gateway_logs(self, context: OperationContext) -> tuple[Evidence, ...]:
        raise UnsupportedCapabilityError()

    async def trace_request(
        self, request_id: Identifier, context: OperationContext
    ) -> tuple[Evidence, ...]:
        raise UnsupportedCapabilityError()

    async def close(self) -> None:
        self.connected = False
