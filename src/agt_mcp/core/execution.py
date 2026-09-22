"""Transport-neutral request identity and governance vocabulary."""

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field

from agt_mcp.core.models import Identifier, Model, Text
from agt_mcp.core.operations import OperationContext


class Capability(StrEnum):
    SYSTEM_READ = "system.read"
    CAPABILITY_READ = "capability.read"
    ENVIRONMENT_READ = "environment.read"
    GATEWAY_READ = "gateway.read"
    GATEWAY_DISCOVER = "gateway.discover"
    DATASOURCE_READ = "datasource.read"
    DATASOURCE_HEALTH = "datasource.health"


class ToolName(StrEnum):
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


TOOL_DEFINITIONS = (
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
        description="Discover an in-memory gateway",
        category="gateway",
        required_capabilities=frozenset({Capability.GATEWAY_DISCOVER}),
        required_permissions=frozenset({Capability.GATEWAY_DISCOVER}),
    ),
)
