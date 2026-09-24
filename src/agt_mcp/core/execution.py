"""Transport-neutral request identity and governance vocabulary."""

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field

from agt_mcp.core.models import Identifier, Model, Text
from agt_mcp.core.operations import OperationContext


class Capability(StrEnum):
    OBSERVABILITY_LOGS = "observability.logs.read"
    OBSERVABILITY_METRICS = "observability.metrics.read"
    OBSERVABILITY_TRACES = "observability.traces.read"
    OBSERVABILITY_TIMELINE = "observability.timeline.read"
    TRACE_READ = "trace.read"
    PROBE_PLAN = "probe.plan"
    PROBE_EXECUTE = "probe.execute.active_readonly"
    TROUBLESHOOTING_READ = "troubleshooting.read"
    CORRELATION_READ = "correlation.read"
    KNOWLEDGE_INTERNAL = "knowledge.search.internal"
    KNOWLEDGE_OFFICIAL = "knowledge.search.official"
    KNOWLEDGE_ISSUES = "knowledge.issues.read"
    KNOWLEDGE_SOURCES = "knowledge.sources.read"
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
    INSPECT_OBSERVABILITY = "inspect_observability"
    INSPECT_LOGS = "inspect_logs"
    INSPECT_METRICS = "inspect_metrics"
    INSPECT_TRACE = "inspect_trace"
    BUILD_EVIDENCE_TIMELINE = "build_evidence_timeline"
    TRACE_RESOURCE = "trace_resource"
    TRACE_GATEWAY_COMPONENT = "trace_gateway_component"
    PLAN_PROBES = "plan_probes"
    EXECUTE_PROBE_PLAN = "execute_probe_plan"
    EXPLAIN_TRACE = "explain_trace"
    DIAGNOSE_COMPONENT = "diagnose_component"
    DIAGNOSE_GATEWAY = "diagnose_gateway"
    DIAGNOSE_API = "diagnose_api"
    EXPLAIN_HYPOTHESIS = "explain_hypothesis"
    GET_TROUBLESHOOTING_PLAN = "get_troubleshooting_plan"
    CORRELATE_EVIDENCE = "correlate_evidence"
    GET_CORRELATION_TIMELINE = "get_correlation_timeline"
    EXPLAIN_CORRELATION = "explain_correlation"
    SEARCH_INTERNAL_KNOWLEDGE = "search_internal_knowledge"
    SEARCH_OFFICIAL_DOCUMENTATION = "search_official_documentation"
    FIND_KNOWN_ISSUE = "find_known_issue"
    LIST_KNOWLEDGE_SOURCES = "list_knowledge_sources"
    GET_KNOWLEDGE_SOURCE_HEALTH = "get_knowledge_source_health"
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
KNOWLEDGE_TOOLS = frozenset(
    {
        ToolName.SEARCH_INTERNAL_KNOWLEDGE,
        ToolName.SEARCH_OFFICIAL_DOCUMENTATION,
        ToolName.FIND_KNOWN_ISSUE,
        ToolName.LIST_KNOWLEDGE_SOURCES,
        ToolName.GET_KNOWLEDGE_SOURCE_HEALTH,
    }
)
CORRELATION_TOOLS = frozenset(
    {ToolName.CORRELATE_EVIDENCE, ToolName.GET_CORRELATION_TIMELINE, ToolName.EXPLAIN_CORRELATION}
)
LEGACY_TOOLS = (
    frozenset(ToolName) - RUNTIME_TOOLS - SEMANTIC_TOOLS - KNOWLEDGE_TOOLS - CORRELATION_TOOLS
)
TROUBLESHOOTING_TOOLS = frozenset(
    {
        ToolName.DIAGNOSE_COMPONENT,
        ToolName.DIAGNOSE_GATEWAY,
        ToolName.DIAGNOSE_API,
        ToolName.EXPLAIN_HYPOTHESIS,
        ToolName.GET_TROUBLESHOOTING_PLAN,
    }
)
LEGACY_TOOLS -= TROUBLESHOOTING_TOOLS
TRACE_TOOLS = frozenset(
    {
        ToolName.TRACE_RESOURCE,
        ToolName.TRACE_GATEWAY_COMPONENT,
        ToolName.PLAN_PROBES,
        ToolName.EXECUTE_PROBE_PLAN,
        ToolName.EXPLAIN_TRACE,
    }
)
LEGACY_TOOLS -= TRACE_TOOLS
OBSERVABILITY_TOOLS = frozenset(
    {
        ToolName.INSPECT_OBSERVABILITY,
        ToolName.INSPECT_LOGS,
        ToolName.INSPECT_METRICS,
        ToolName.INSPECT_TRACE,
        ToolName.BUILD_EVIDENCE_TIMELINE,
    }
)
LEGACY_TOOLS -= OBSERVABILITY_TOOLS

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
        description="Read bounded scoped observability evidence",
        category="observability",
        required_capabilities=frozenset({capability}),
        required_permissions=frozenset({capability}),
    )
    for name, capability in (
        (ToolName.INSPECT_OBSERVABILITY, Capability.OBSERVABILITY_TIMELINE),
        (ToolName.BUILD_EVIDENCE_TIMELINE, Capability.OBSERVABILITY_TIMELINE),
        (ToolName.INSPECT_LOGS, Capability.OBSERVABILITY_LOGS),
        (ToolName.INSPECT_METRICS, Capability.OBSERVABILITY_METRICS),
        (ToolName.INSPECT_TRACE, Capability.OBSERVABILITY_TRACES),
    )
)

TOOL_DEFINITIONS += tuple(
    ToolDefinition(
        name=name,
        description="Structural trace or policy-controlled network observation",
        category="trace",
        required_capabilities=frozenset({capability}),
        required_permissions=frozenset({capability}),
    )
    for name, capability in (
        (ToolName.TRACE_RESOURCE, Capability.TRACE_READ),
        (ToolName.TRACE_GATEWAY_COMPONENT, Capability.TRACE_READ),
        (ToolName.EXPLAIN_TRACE, Capability.TRACE_READ),
        (ToolName.PLAN_PROBES, Capability.PROBE_PLAN),
        (ToolName.EXECUTE_PROBE_PLAN, Capability.PROBE_EXECUTE),
    )
)

TOOL_DEFINITIONS += tuple(
    ToolDefinition(
        name=name,
        description="Read-only evidence-based hypothesis evaluation and planning",
        category="troubleshooting",
        required_capabilities=frozenset({Capability.TROUBLESHOOTING_READ}),
        required_permissions=frozenset({Capability.TROUBLESHOOTING_READ}),
    )
    for name in sorted(TROUBLESHOOTING_TOOLS)
)

TOOL_DEFINITIONS += tuple(
    ToolDefinition(
        name=name,
        description=description,
        category="correlation",
        required_capabilities=frozenset({Capability.CORRELATION_READ}),
        required_permissions=frozenset({Capability.CORRELATION_READ}),
    )
    for name, description in (
        (
            ToolName.CORRELATE_EVIDENCE,
            "Correlate bounded evidence and references without causal diagnosis",
        ),
        (ToolName.GET_CORRELATION_TIMELINE, "Read a scoped cached correlation timeline"),
        (ToolName.EXPLAIN_CORRELATION, "Explain deterministic rules, support and contradictions"),
    )
)

TOOL_DEFINITIONS += tuple(
    ToolDefinition(
        name=name,
        description=description,
        category="knowledge",
        required_capabilities=frozenset({capability}),
        required_permissions=frozenset({capability}),
    )
    for name, description, capability in (
        (
            ToolName.SEARCH_INTERNAL_KNOWLEDGE,
            "Search indexed internal untrusted knowledge",
            Capability.KNOWLEDGE_INTERNAL,
        ),
        (
            ToolName.SEARCH_OFFICIAL_DOCUMENTATION,
            "Search curated indexed versioned documentation",
            Capability.KNOWLEDGE_OFFICIAL,
        ),
        (
            ToolName.FIND_KNOWN_ISSUE,
            "Find prior incidents, known errors and runbooks; no causal conclusion",
            Capability.KNOWLEDGE_ISSUES,
        ),
        (
            ToolName.LIST_KNOWLEDGE_SOURCES,
            "List authorized knowledge source metadata",
            Capability.KNOWLEDGE_SOURCES,
        ),
        (
            ToolName.GET_KNOWLEDGE_SOURCE_HEALTH,
            "Read source and derived index freshness",
            Capability.KNOWLEDGE_SOURCES,
        ),
    )
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
