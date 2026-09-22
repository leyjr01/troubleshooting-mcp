"""Health-only synthetic datasource, never a SQL/query engine."""

import asyncio

from agt_mcp.core.errors import (
    AuthorizationError,
    ConnectionError,
    DataSourceUnavailable,
    UnsupportedCapabilityError,
)
from agt_mcp.core.models import Evidence
from agt_mcp.core.operations import Health, Operation, OperationContext, Query, SchemaDescription
from agt_mcp.datasources.base.adapter import DataSourceAdapter


class InMemoryDataSourceAdapter(DataSourceAdapter):
    def __init__(
        self, environment_id: str, *, delay_seconds: float = 0, fail: bool = False
    ) -> None:
        self.environment_id = environment_id
        self.delay_seconds = delay_seconds
        self.fail = fail
        self.connected = False

    def capabilities(self) -> frozenset[Operation]:
        return frozenset({Operation.HEALTH})

    def check_scope(self, context: OperationContext) -> None:
        if context.environment_id != self.environment_id:
            raise AuthorizationError()

    async def connect(self, context: OperationContext) -> None:
        self.check_scope(context)
        self.connected = True

    async def health(self, context: OperationContext) -> Health:
        self.check_scope(context)
        if not self.connected:
            raise ConnectionError()
        await asyncio.sleep(self.delay_seconds)
        if self.fail:
            raise DataSourceUnavailable()
        return Health(status="healthy", detail_code="in-memory")

    async def query(self, query: Query, context: OperationContext) -> tuple[Evidence, ...]:
        raise UnsupportedCapabilityError()

    async def discover_schema(self, context: OperationContext) -> SchemaDescription:
        raise UnsupportedCapabilityError()

    async def close(self) -> None:
        self.connected = False
