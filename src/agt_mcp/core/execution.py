"""Transport-neutral request identity and governance vocabulary."""

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field

from agt_mcp.core.models import Identifier, Model, Text
from agt_mcp.core.operations import OperationContext


class Capability(StrEnum):
    GATEWAY_COMPONENTS = "gateway.components.read"
    GATEWAY_TOPOLOGY = "gateway.topology.read"
    GATEWAY_DEPENDENCIES = "gateway.dependencies.read"
    RUNTIME_DISCOVER = "runtime.discover"
    RESOURCE_READ = "resource.read"
    EVENT_READ = "event.read"
    TOPOLOGY_READ = "topology.read"
    SYSTEM_READ = "system.read"
    CAPABILITY_READ = "capability.read"
    ENVIRONMENT_READ = "environment.read"
    GATEWAY_READ = "gateway.read"
    GATEWAY_DISCOVER = "gateway.discover"
    DATASOURCE_READ = "datasource.read"
    DATASOURCE_HEALTH = "datasource.health"


class ToolName(StrEnum):
    GET_GATEWAY_TOPOLOGY = "get_gateway_topology"
    INSPECT_GATEWAY_COMPONENT = "inspect_gateway_component"
    GET_GATEWAY_DEPENDENCIES = "get_gateway_dependencies"
    DISCOVER_ENVIRONMENT = "discover_environment"
    INSPECT_RESOURCE = "inspect_resource"
    INSPECT_EVENTS = "inspect_events"
    FIND_RELATED_RESOURCES = "find_related_resources"
    GET_RESOURCE_TOPOLOGY = "get_resource_topology"
    SYSTEM_HEALTH = "system_health"
    LIST_CAPABILITIES = "list_capabilities"
    LIST_ENVIRONMENTS = "list_environments"
    LIST_GATEWAYS = "list_gateways"
    LIST_DATASOURCES = "list_datasources"
    INSPECT_DATASOURCE = "inspect_datasource"
    DISCOVER_GATEWAY = "discover_gateway"


class ExecutionContext(OperationContext):
    operation: ToolName
    start_time: AwareDatetime
    deadline: float = Field(allow_inf_nan=False)
    metadata: dict[str, str] = Field(default_factory=dict)


class ToolDefinition(Model):
    name: ToolName
    description: Text
    category: Identifier
    required_capabilities: frozenset[Capability]
    required_permissions: frozenset[Capability]
    read_only: Literal[True] = True
    enabled: bool = True
    version: Literal["1.0.0"] = "1.0.0"


RUNTIME_TOOLS = frozenset(
    {
        ToolName.DISCOVER_ENVIRONMENT,
        ToolName.INSPECT_RESOURCE,
        ToolName.INSPECT_EVENTS,
        ToolName.FIND_RELATED_RESOURCES,
        ToolName.GET_RESOURCE_TOPOLOGY,
    }
)
SEMANTIC_TOOLS = frozenset(
    {
        ToolName.GET_GATEWAY_TOPOLOGY,
        ToolName.INSPECT_GATEWAY_COMPONENT,
        ToolName.GET_GATEWAY_DEPENDENCIES,
    }
)
LEGACY_TOOLS = frozenset(ToolName) - RUNTIME_TOOLS - SEMANTIC_TOOLS

TOOL_DEFINITIONS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        name=ToolName.SYSTEM_HEALTH,
        description="Health of this MCP runtime only",
        category="system",
        required_capabilities=frozenset({Capability.SYSTEM_READ}),
        required_permissions=frozenset({Capability.SYSTEM_READ}),
    ),
    ToolDefinition(
        name=ToolName.LIST_CAPABILITIES,
        description="Authorized capabilities and tools",
        category="system",
        required_capabilities=frozenset({Capability.CAPABILITY_READ}),
        required_permissions=frozenset({Capability.CAPABILITY_READ}),
    ),
    ToolDefinition(
        name=ToolName.LIST_ENVIRONMENTS,
        description="Configured authorized environments",
        category="environment",
        required_capabilities=frozenset({Capability.ENVIRONMENT_READ}),
        required_permissions=frozenset({Capability.ENVIRONMENT_READ}),
    ),
    ToolDefinition(
        name=ToolName.LIST_GATEWAYS,
        description="Registered gateway metadata",
        category="gateway",
        required_capabilities=frozenset({Capability.GATEWAY_READ}),
        required_permissions=frozenset({Capability.GATEWAY_READ}),
    ),
    ToolDefinition(
        name=ToolName.LIST_DATASOURCES,
        description="Safe datasource inventory",
        category="datasource",
        required_capabilities=frozenset({Capability.DATASOURCE_READ}),
        required_permissions=frozenset({Capability.DATASOURCE_READ}),
    ),
    ToolDefinition(
        name=ToolName.INSPECT_DATASOURCE,
        description="Safe datasource metadata and mock health",
        category="datasource",
        required_capabilities=frozenset({Capability.DATASOURCE_READ}),
        required_permissions=frozenset({Capability.DATASOURCE_READ}),
    ),
    ToolDefinition(
        name=ToolName.DISCOVER_GATEWAY,
        description="Discover authorized gateway installations",
        category="gateway",
        required_capabilities=frozenset({Capability.GATEWAY_DISCOVER}),
        required_permissions=frozenset({Capability.GATEWAY_DISCOVER}),
    ),
)

TOOL_DEFINITIONS += tuple(
    ToolDefinition(
        name=name,
        description=description,
        category="runtime",
        required_capabilities=frozenset({capability}),
        required_permissions=frozenset({capability}),
    )
    for name, description, capability in (
        (
            ToolName.DISCOVER_ENVIRONMENT,
            "Discover bounded runtime inventory summary",
            Capability.RUNTIME_DISCOVER,
        ),
        (
            ToolName.INSPECT_RESOURCE,
            "Inspect a canonical runtime resource",
            Capability.RESOURCE_READ,
        ),
        (
            ToolName.INSPECT_EVENTS,
            "Inspect bounded related Event observations",
            Capability.EVENT_READ,
        ),
        (
            ToolName.FIND_RELATED_RESOURCES,
            "Find neighbors in observed runtime topology",
            Capability.TOPOLOGY_READ,
        ),
        (
            ToolName.GET_RESOURCE_TOPOLOGY,
            "Return a bounded runtime subgraph",
            Capability.TOPOLOGY_READ,
        ),
    )
)

TOOL_DEFINITIONS += tuple(
    ToolDefinition(
        name=name,
        description=description,
        category="gateway",
        required_capabilities=frozenset({capability}),
        required_permissions=frozenset({capability}),
    )
    for name, description, capability in (
        (
            ToolName.GET_GATEWAY_TOPOLOGY,
            "Read bounded gateway semantic topology",
            Capability.GATEWAY_TOPOLOGY,
        ),
        (
            ToolName.INSPECT_GATEWAY_COMPONENT,
            "Inspect gateway component classification and evidence",
            Capability.GATEWAY_COMPONENTS,
        ),
        (
            ToolName.GET_GATEWAY_DEPENDENCIES,
            "Read structural gateway dependencies without connectivity probes",
            Capability.GATEWAY_DEPENDENCIES,
        ),
    )
)
