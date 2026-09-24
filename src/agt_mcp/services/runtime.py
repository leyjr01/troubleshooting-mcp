"""Read-only application services and lifecycle, with no framework objects."""

import asyncio
import builtins
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from time import monotonic
from typing import cast
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
from agt_mcp.core.execution import (
    CORRELATION_TOOLS,
    KNOWLEDGE_TOOLS,
    RUNTIME_TOOLS,
    SEMANTIC_TOOLS,
    TOOL_DEFINITIONS,
    TRACE_TOOLS,
    TROUBLESHOOTING_TOOLS,
    Capability,
    ExecutionContext,
    ToolName,
)
from agt_mcp.core.operations import Operation, OperationContext
from agt_mcp.core.runtime import RuntimeQuery
from agt_mcp.correlation.engine import EvidenceCorrelationEngine
from agt_mcp.correlation.models import CorrelationOperation
from agt_mcp.datasources.base.adapter import DataSourceAdapter
from agt_mcp.datasources.probe_network import NetworkProbeExecutor
from agt_mcp.gateways.base.adapter import GatewayAdapter
from agt_mcp.gateways.threescale.hypotheses import ThreeScaleHypothesisProvider
from agt_mcp.gateways.threescale.models import GatewayQuery
from agt_mcp.knowledge.composition import build_knowledge
from agt_mcp.knowledge.models import SourceType
from agt_mcp.probes.planner import ProbePlanner
from agt_mcp.probes.policy import ProbePolicy
from agt_mcp.probes.runner import ProbeRunner
from agt_mcp.rag.contracts import RetrievalQuery
from agt_mcp.services.correlation import CorrelationService
from agt_mcp.services.correlation_providers import (
    HistoryBridge,
    KnowledgeBridge,
    RuntimeCorrelationProvider,
)
from agt_mcp.services.discovery import RuntimeDiscoveryService
from agt_mcp.services.gateway_discovery import GatewayDiscoveryService
from agt_mcp.services.registry import AdapterRegistry
from agt_mcp.services.trace import TraceService
from agt_mcp.services.troubleshooting import TroubleshootingService
from agt_mcp.trace.models import TraceOperation
from agt_mcp.troubleshooting.catalog import (
    GenericHypothesisProvider,
    HypothesisCatalog,
    KubernetesHypothesisProvider,
)
from agt_mcp.troubleshooting.engine import TroubleshootingEngine
from agt_mcp.troubleshooting.models import TroubleshootingOperation
from agt_mcp.troubleshooting.network_hypotheses import NetworkHypothesisProvider


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
        self.discovery = RuntimeDiscoveryService({})
        self.gateway_discovery = GatewayDiscoveryService(gateways)
        self.knowledge = build_knowledge(configuration)
        self.correlation = CorrelationService(
            EvidenceCorrelationEngine(
                RuntimeCorrelationProvider(self.discovery, self.gateway_discovery),
                KnowledgeBridge(self.knowledge, configuration.correlation.max_knowledge_results),
                HistoryBridge(self.knowledge, configuration.correlation.max_knowledge_results),
                configuration.correlation,
            )
        )

        self.troubleshooting = TroubleshootingService(
            TroubleshootingEngine(
                self.correlation.engine,
                HypothesisCatalog(
                    (
                        GenericHypothesisProvider(),
                        KubernetesHypothesisProvider(),
                        ThreeScaleHypothesisProvider(),
                        NetworkHypothesisProvider(),
                    )
                ),
                configuration.troubleshooting,
            )
        )

        policy = ProbePolicy(configuration.probes)
        executor = NetworkProbeExecutor(policy)
        self.trace = TraceService(
            self.troubleshooting,
            ProbePlanner(policy, executor.capabilities()),
            ProbeRunner(policy, executor),
        )

    @asynccontextmanager
    async def lifespan(self) -> AsyncIterator[None]:
        if self.ready:
            raise ConnectionError()
        self.gateways.seal()
        self.datasources.seal()
        async with AsyncExitStack() as stack:
            stack.push_async_callback(self.discovery.close)
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
                if tool.name in TRACE_TOOLS and (
                    Operation.DIAGNOSE not in self.configuration.application.allowed_operations
                    or (
                        tool.name == ToolName.EXECUTE_PROBE_PLAN
                        and (
                            not self.configuration.probes.enabled
                            or self.configuration.probes.execution_mode != "execute_allowed"
                        )
                    )
                ):
                    continue
                if (
                    tool.name in TROUBLESHOOTING_TOOLS
                    and Operation.DIAGNOSE not in self.configuration.application.allowed_operations
                ):
                    continue
                if (
                    tool.name in CORRELATION_TOOLS
                    and Operation.CORRELATE not in self.configuration.application.allowed_operations
                ):
                    continue
                if tool.name in KNOWLEDGE_TOOLS:
                    operation = (
                        Operation.KNOWLEDGE_SOURCES
                        if tool.name
                        in {
                            ToolName.LIST_KNOWLEDGE_SOURCES,
                            ToolName.GET_KNOWLEDGE_SOURCE_HEALTH,
                        }
                        else Operation.KNOWLEDGE_SEARCH
                    )
                    if (
                        operation not in self.configuration.application.allowed_operations
                        or not any(
                            s.config.metadata.environment in {"global", environment_id}
                            for s in self.knowledge.sources.values()
                        )
                    ):
                        continue
                if tool.name in RUNTIME_TOOLS and environment_id not in self.discovery.adapters:
                    continue
                if tool.name in SEMANTIC_TOOLS:
                    required = {
                        ToolName.GET_GATEWAY_TOPOLOGY: Operation.GATEWAY_TOPOLOGY,
                        ToolName.INSPECT_GATEWAY_COMPONENT: Operation.COMPONENTS,
                        ToolName.GET_GATEWAY_DEPENDENCIES: Operation.DEPENDENCIES,
                    }[tool.name]
                    if required not in self.configuration.application.allowed_operations or not any(
                        required in adapter.capabilities()
                        for adapter in self.gateway_discovery.adapters(environment_id).values()
                    ):
                        continue
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
        self,
        context: ExecutionContext,
        resource_id: str | None = None,
        runtime_query: RuntimeQuery | None = None,
        gateway_query: GatewayQuery | None = None,
        knowledge_query: RetrievalQuery | None = None,
        correlation_operation: CorrelationOperation | None = None,
        troubleshooting_operation: TroubleshootingOperation | None = None,
        trace_operation: TraceOperation | None = None,
    ) -> dict[str, JsonValue]:
        self.authorize(context)
        if not self.ready:
            raise ConnectionError()
        remaining = min(context.timeout_seconds, context.deadline - monotonic())
        if remaining <= 0:
            raise TimeoutError()
        try:
            async with asyncio.timeout(remaining):
                if context.operation in TRACE_TOOLS:
                    if Operation.DIAGNOSE not in self.configuration.application.allowed_operations:
                        raise UnsupportedCapabilityError()
                    return await self.trace.execute(
                        trace_operation or TraceOperation(),
                        context,
                        self.configuration.mcp.server.authorization.permissions,
                        bool(self.gateway_discovery.adapters(context.environment_id)),
                    )
                if context.operation in TROUBLESHOOTING_TOOLS:
                    if Operation.DIAGNOSE not in self.configuration.application.allowed_operations:
                        raise UnsupportedCapabilityError()
                    return await self.troubleshooting.execute(
                        troubleshooting_operation or TroubleshootingOperation(),
                        context,
                        self.configuration.mcp.server.authorization.permissions,
                        bool(self.gateway_discovery.adapters(context.environment_id)),
                    )
                if context.operation in CORRELATION_TOOLS:
                    if Operation.CORRELATE not in self.configuration.application.allowed_operations:
                        raise UnsupportedCapabilityError()
                    return await self.correlation.execute(
                        correlation_operation or CorrelationOperation(),
                        context,
                        self.configuration.mcp.server.authorization.permissions,
                        bool(self.gateway_discovery.adapters(context.environment_id)),
                    )
                if context.operation in KNOWLEDGE_TOOLS:
                    return await self.execute_knowledge(context, resource_id, knowledge_query)
                if context.operation in SEMANTIC_TOOLS or (
                    context.operation == ToolName.DISCOVER_GATEWAY
                    and (
                        gateway_query is not None
                        or (
                            bool(self.gateway_discovery.adapters(context.environment_id))
                            and resource_id
                            not in {
                                e.id
                                for e in self.gateways.entries(context.environment_id)
                                if e.id
                                not in self.gateway_discovery.adapters(context.environment_id)
                            }
                        )
                    )
                ):
                    operation = {
                        ToolName.DISCOVER_GATEWAY: Operation.DISCOVER_GATEWAY,
                        ToolName.GET_GATEWAY_TOPOLOGY: Operation.GATEWAY_TOPOLOGY,
                        ToolName.INSPECT_GATEWAY_COMPONENT: Operation.COMPONENTS,
                        ToolName.GET_GATEWAY_DEPENDENCIES: Operation.DEPENDENCIES,
                    }[context.operation]
                    if operation not in self.configuration.application.allowed_operations:
                        raise UnsupportedCapabilityError()
                    return await self.gateway_discovery.execute(
                        context, gateway_query or GatewayQuery(gateway_id=resource_id)
                    )
                if context.operation in RUNTIME_TOOLS:
                    return await self.discovery.execute(context, runtime_query or RuntimeQuery())
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

    async def execute_knowledge(
        self, context: ExecutionContext, source_id: str | None, query: RetrievalQuery | None
    ) -> dict[str, JsonValue]:
        tool = context.operation
        inventory = tool in {ToolName.LIST_KNOWLEDGE_SOURCES, ToolName.GET_KNOWLEDGE_SOURCE_HEALTH}
        operation = Operation.KNOWLEDGE_SOURCES if inventory else Operation.KNOWLEDGE_SEARCH
        if operation not in self.configuration.application.allowed_operations:
            raise UnsupportedCapabilityError()
        if tool == ToolName.LIST_KNOWLEDGE_SOURCES:
            return {
                "sources": [s.model_dump(mode="json") for s in self.knowledge.list_sources(context)]
            }
        if tool == ToolName.GET_KNOWLEDGE_SOURCE_HEALTH:
            return cast(
                dict[str, JsonValue],
                (await self.knowledge.health(source_id or "", context)).model_dump(mode="json"),
            )
        categories = {
            ToolName.SEARCH_INTERNAL_KNOWLEDGE: (
                SourceType.INTERNAL_KNOWLEDGE,
                SourceType.ARCHITECTURE,
                SourceType.RUNBOOK,
                SourceType.KNOWN_ERROR,
                SourceType.CMDB,
            ),
            ToolName.SEARCH_OFFICIAL_DOCUMENTATION: (SourceType.OFFICIAL_DOCUMENTATION,),
            ToolName.FIND_KNOWN_ISSUE: (
                SourceType.HISTORICAL_INCIDENT,
                SourceType.KNOWN_ERROR,
                SourceType.RUNBOOK,
            ),
        }[tool]
        if query is None:
            raise UnsupportedCapabilityError()
        if query.source_types and not set(query.source_types) <= set(categories):
            raise AuthorizationError()
        query = query.model_copy(update={"source_types": query.source_types or categories})
        result = await self.knowledge.search(query, context)
        return cast(dict[str, JsonValue], result.model_dump(mode="json"))

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
