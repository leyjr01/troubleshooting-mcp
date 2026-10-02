"""3scale GatewayAdapter composed exclusively over the canonical RuntimeAdapter."""

from datetime import UTC, datetime
from time import monotonic

from agt_mcp.configuration.gateway import GatewayDiscoveryConfig
from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    ConnectionError,
    UnsupportedCapabilityError,
)
from agt_mcp.core.execution import ExecutionContext, ToolName
from agt_mcp.core.models import Evidence, Gateway, Identifier, Resource
from agt_mcp.core.operations import Health, Operation, OperationContext
from agt_mcp.core.runtime import RuntimeAdapter, RuntimeQuery
from agt_mcp.gateways.base.adapter import GatewayAdapter
from agt_mcp.gateways.threescale.classifier import ThreeScaleComponentClassifier
from agt_mcp.gateways.threescale.models import GatewayDiscovery, GatewayQuery
from agt_mcp.topology.models import Dependency


class ThreeScaleGatewayAdapter(GatewayAdapter):
    def __init__(
        self,
        environment_id: str,
        runtime: RuntimeAdapter,
        discovery: GatewayDiscoveryConfig | None = None,
        *,
        max_edges: int = 1000,
        max_components: int = 200,
    ) -> None:
        self.environment_id, self.runtime, self.settings = (
            environment_id,
            runtime,
            discovery or GatewayDiscoveryConfig(),
        )
        self.max_edges, self.max_components = max_edges, max_components
        self.connected = False

    def capabilities(self) -> frozenset[Operation]:
        return frozenset(
            {
                Operation.DISCOVER_GATEWAY,
                Operation.HEALTH,
                Operation.ROUTES,
                Operation.COMPONENTS,
                Operation.GATEWAY_TOPOLOGY,
            }
            | ({Operation.DEPENDENCIES} if self.settings.include_dependencies else set())
        )

    def check_scope(self, context: OperationContext) -> None:
        if context.environment_id != self.environment_id:
            raise AuthorizationError()

    async def connect(self, context: OperationContext) -> None:
        self.check_scope(context)
        self.connected = True

    async def discover_installations(
        self, context: OperationContext, query: GatewayQuery | None = None
    ) -> GatewayDiscovery:
        self.check_scope(context)
        if not self.connected:
            raise ConnectionError()
        query = query or GatewayQuery()
        if (
            query.namespace
            and self.settings.namespace
            and query.namespace != self.settings.namespace
        ):
            raise AuthorizationError()
        primary_namespace = query.namespace or self.settings.namespace
        execution = (
            context
            if isinstance(context, ExecutionContext)
            else ExecutionContext(
                **context.model_dump(),
                operation=ToolName.DISCOVER_GATEWAY,
                start_time=datetime.now(UTC),
                deadline=monotonic() + context.timeout_seconds,
            )
        )
        snapshot = await self.runtime.discover(
            execution,
            RuntimeQuery(
                # Namespace selection belongs to the runtime allowlist.  The gateway
                # namespace identifies the APIManager, not the complete installation:
                # APIcast resources may live in another authorized namespace.
                namespace=None,
                limit=query.limit,
                depth=query.depth,
            ),
        )
        if (
            snapshot.environment_id != context.environment_id
            or snapshot.topology.environment_id != context.environment_id
            or any(n.environment_id != context.environment_id for n in snapshot.topology.nodes)
            or any(
                e.environment_id != context.environment_id
                or e.source.environment_id != context.environment_id
                for e in snapshot.evidence
            )
        ):
            raise AuthorizationError()
        authorized_namespaces = set(snapshot.namespaces)
        if primary_namespace and primary_namespace not in authorized_namespaces:
            raise AuthorizationError()
        if any(
            n.namespace is not None and n.namespace not in authorized_namespaces
            for n in snapshot.topology.nodes
        ):
            raise AuthorizationError()
        classifier = ThreeScaleComponentClassifier(
            snapshot,
            primary_namespace=primary_namespace,
            version_profile=self.settings.version_profile,
            max_edges=self.max_edges,
            max_components=self.max_components,
        )
        return GatewayDiscovery(installations=classifier.classify(), snapshot=snapshot)

    async def discover_gateway(self, context: OperationContext) -> Gateway:
        result = await self.discover_installations(context)
        if len(result.installations) != 1:
            raise ConfigurationError()
        installation = result.installations[0]
        return Gateway(
            id=installation.id,
            name=installation.id,
            environment_id=self.environment_id,
            namespace=installation.namespace,
            provider="threescale",
            version=installation.version,
            endpoint_reference=installation.id,
        )

    async def get_health(self, context: OperationContext) -> Health:
        result = await self.discover_installations(context)
        return Health(
            status="unknown"
            if not result.installations or any(i.partial for i in result.installations)
            else "healthy",
            detail_code="structural-discovery-only",
        )

    async def get_routes(self, context: OperationContext) -> tuple[Resource, ...]:
        result = await self.discover_installations(context)
        ids = {rid for i in result.installations for rid in i.runtime_resources}
        return tuple(
            n
            for n in result.snapshot.topology.nodes
            if n.id in ids and n.reference and n.reference.kind in {"Route", "Ingress"}
        )

    async def get_dependencies(self, context: OperationContext) -> tuple[Dependency, ...]:
        if not self.settings.include_dependencies:
            raise UnsupportedCapabilityError()
        result = await self.discover_installations(context)
        groups = [set(i.runtime_resources) for i in result.installations]
        return tuple(
            e
            for e in result.snapshot.topology.edges
            if any(e.source in ids and e.target in ids for ids in groups)
        )

    async def get_products(self, context: OperationContext) -> tuple[Resource, ...]:
        raise UnsupportedCapabilityError()

    async def get_backends(self, context: OperationContext) -> tuple[Resource, ...]:
        raise UnsupportedCapabilityError()

    async def get_policies(self, context: OperationContext) -> tuple[Evidence, ...]:
        raise UnsupportedCapabilityError()

    async def get_gateway_logs(self, context: OperationContext) -> tuple[Evidence, ...]:
        raise UnsupportedCapabilityError()

    async def trace_request(
        self, request_id: Identifier, context: OperationContext
    ) -> tuple[Evidence, ...]:
        raise UnsupportedCapabilityError()

    async def close(self) -> None:
        # Runtime ownership/lifecycle belongs to bootstrap, not this composed adapter.
        self.connected = False
