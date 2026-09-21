"""Async read-only data port. Ownership and deadlines are documented in contracts."""

from abc import ABC, abstractmethod

from agt_mcp.core.models import Evidence
from agt_mcp.core.operations import Health, Operation, OperationContext, Query, SchemaDescription


class DataSourceAdapter(ABC):
    @abstractmethod
    def capabilities(self) -> frozenset[Operation]: ...

    @abstractmethod
    async def connect(self, context: OperationContext) -> None: ...

    @abstractmethod
    async def health(self, context: OperationContext) -> Health: ...

    @abstractmethod
    async def query(self, query: Query, context: OperationContext) -> tuple[Evidence, ...]: ...

    @abstractmethod
    async def discover_schema(self, context: OperationContext) -> SchemaDescription: ...

    @abstractmethod
    async def close(self) -> None: ...
