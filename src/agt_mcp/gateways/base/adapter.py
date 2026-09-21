"""Generic gateway read port; traces inspect existing requests, never replay traffic."""

from abc import ABC, abstractmethod

from agt_mcp.core.models import Evidence, Gateway, Identifier, Resource
from agt_mcp.core.operations import Health, Operation, OperationContext
from agt_mcp.topology.models import Dependency


class GatewayAdapter(ABC):
    @abstractmethod
    def capabilities(self) -> frozenset[Operation]: ...

    @abstractmethod
    async def connect(self, context: OperationContext) -> None: ...

    @abstractmethod
    async def discover_gateway(self, context: OperationContext) -> Gateway: ...

    @abstractmethod
    async def get_products(self, context: OperationContext) -> tuple[Resource, ...]: ...

    @abstractmethod
    async def get_backends(self, context: OperationContext) -> tuple[Resource, ...]: ...

    @abstractmethod
    async def get_routes(self, context: OperationContext) -> tuple[Resource, ...]: ...

    @abstractmethod
    async def get_policies(self, context: OperationContext) -> tuple[Evidence, ...]: ...

    @abstractmethod
    async def get_dependencies(self, context: OperationContext) -> tuple[Dependency, ...]: ...

    @abstractmethod
    async def get_gateway_logs(self, context: OperationContext) -> tuple[Evidence, ...]: ...

    @abstractmethod
    async def get_health(self, context: OperationContext) -> Health: ...

    @abstractmethod
    async def trace_request(
        self, request_id: Identifier, context: OperationContext
    ) -> tuple[Evidence, ...]: ...

    @abstractmethod
    async def close(self) -> None: ...
