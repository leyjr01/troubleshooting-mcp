"""Offline reference fakes exercise port lifecycle, dispatch, and canonical outputs."""

import asyncio

import pytest

from agt_mcp.core.errors import ConnectionError, UnsupportedCapabilityError
from agt_mcp.core.models import Gateway
from agt_mcp.core.operations import Health, Operation, OperationContext, Query, SchemaDescription
from agt_mcp.datasources.base.adapter import DataSourceAdapter
from agt_mcp.evidence.bundle import IncidentBundle
from agt_mcp.gateways.base.adapter import GatewayAdapter
from agt_mcp.security.policy import ReadOnlyPolicy, run_read


class FakeSource(DataSourceAdapter):
    def __init__(self, evidence):
        self.evidence = evidence
        self.connected = False

    def capabilities(self):
        return frozenset({Operation.HEALTH, Operation.QUERY})

    async def connect(self, context):
        self.connected = True

    def require_connection(self):
        if not self.connected:
            raise ConnectionError()

    async def health(self, context):
        self.require_connection()
        return Health(status="healthy", detail_code="fake")

    async def query(self, query, context):
        self.require_connection()
        return tuple(e for e in self.evidence if e.environment_id == context.environment_id)[
            : min(query.limit, context.max_items)
        ]

    async def discover_schema(self, context):
        raise UnsupportedCapabilityError()

    async def close(self):
        self.connected = False


class FakeGateway(GatewayAdapter):
    def __init__(self):
        self.connected = False

    def capabilities(self):
        return frozenset({Operation.HEALTH, Operation.DISCOVER_GATEWAY})

    async def connect(self, context):
        self.connected = True

    async def discover_gateway(self, context):
        if not self.connected:
            raise ConnectionError()
        return Gateway(
            id="gateway-fake",
            environment_id=context.environment_id,
            name="Fake",
            provider="fake",
            version="0",
            endpoint_reference="fixture:gateway",
        )

    async def get_health(self, context):
        if not self.connected:
            raise ConnectionError()
        return Health(status="healthy", detail_code="fake")

    async def unsupported(self, context):
        raise UnsupportedCapabilityError()

    get_products = unsupported
    get_backends = unsupported
    get_routes = unsupported
    get_policies = unsupported
    get_dependencies = unsupported
    get_gateway_logs = unsupported

    async def trace_request(self, request_id, context):
        raise UnsupportedCapabilityError()

    async def close(self):
        self.connected = False


def test_source_lifecycle_and_canonical_results(bundle_data):
    bundle = IncidentBundle.model_validate(bundle_data)
    source = FakeSource(bundle.evidence)
    context = OperationContext(
        environment_id="demo",
        principal_id="reader",
        request_id="r1",
        correlation_id="c1",
        timeout_seconds=1,
    )
    policy = ReadOnlyPolicy("reader", frozenset({"demo"}), source.capabilities())

    async def scenario():
        with pytest.raises(ConnectionError):
            await source.query(Query(collection="incidents"), context)
        await source.connect(context)
        try:
            assert (await source.health(context)).status == "healthy"
            result = await run_read(
                policy,
                Operation.QUERY,
                context,
                source.capabilities(),
                lambda: source.query(Query(collection="incidents", limit=1), context),
            )
            assert result == bundle.evidence
            other = context.model_copy(update={"environment_id": "other"})
            assert await source.query(Query(collection="incidents"), other) == ()
            with pytest.raises(UnsupportedCapabilityError):
                await source.discover_schema(context)
        finally:
            await source.close()
            await source.close()
        with pytest.raises(ConnectionError):
            await source.health(context)

    asyncio.run(scenario())


def test_gateway_lifecycle_and_unsupported_operations():
    gateway = FakeGateway()
    context = OperationContext(
        environment_id="demo",
        principal_id="reader",
        request_id="r1",
        correlation_id="c1",
        timeout_seconds=1,
    )

    async def scenario():
        with pytest.raises(ConnectionError):
            await gateway.discover_gateway(context)
        await gateway.connect(context)
        assert (await gateway.discover_gateway(context)).kind == "gateway"
        assert (await gateway.get_health(context)).status == "healthy"
        for method in (
            gateway.get_products,
            gateway.get_backends,
            gateway.get_routes,
            gateway.get_policies,
            gateway.get_dependencies,
            gateway.get_gateway_logs,
        ):
            with pytest.raises(UnsupportedCapabilityError):
                await method(context)
        with pytest.raises(UnsupportedCapabilityError):
            await gateway.trace_request("existing-request", context)
        await gateway.close()
        await gateway.close()
        with pytest.raises(ConnectionError):
            await gateway.get_health(context)

    asyncio.run(scenario())


@pytest.mark.parametrize("port", [DataSourceAdapter, GatewayAdapter])
def test_ports_cannot_be_instantiated(port):
    with pytest.raises(TypeError):
        port()


def test_schema_discovery_shape():
    result = SchemaDescription.model_validate(
        {
            "tables": [
                {
                    "schema_name": "APP",
                    "name": "INCIDENTS",
                    "columns": [{"name": "ID", "data_type": "varchar", "nullable": False}],
                    "relationships": ["SERVICE_ID references SERVICES.ID"],
                    "indexes": ["PK_INCIDENTS"],
                }
            ]
        }
    )
    assert result.tables[0].columns[0].nullable is False
