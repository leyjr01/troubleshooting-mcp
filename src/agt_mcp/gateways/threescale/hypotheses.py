"""3scale declarative extension; no runtime API or SDK access."""

from agt_mcp.core.models import ResourceKind
from agt_mcp.troubleshooting.catalog import definition
from agt_mcp.troubleshooting.models import HypothesisDefinition, RuleKind


class ThreeScaleHypothesisProvider:
    def definitions(self) -> tuple[HypothesisDefinition, ...]:
        apicast = ("APICAST_PRODUCTION", "APICAST_STAGING")
        backend = ("BACKEND_LISTENER", "BACKEND_WORKER", "BACKEND_CRON")
        system = ("SYSTEM_APP", "SYSTEM_SIDEKIQ")
        return (
            definition(
                "APICAST_NO_READY_RUNTIME_ENDPOINT",
                "APIcast runtime has no usable service endpoint",
                RuleKind.ENDPOINT,
                (ResourceKind.SERVICE,),
                apicast,
                "threescale",
            ),
            definition(
                "APICAST_ROUTE_TARGET_UNRESOLVED",
                "APIcast declared Route target is unresolved",
                RuleKind.ROUTING,
                (ResourceKind.ROUTE,),
                apicast,
                "threescale",
            ),
            definition(
                "SYSTEM_COMPONENT_UNAVAILABLE",
                "System component runtime availability is impaired",
                RuleKind.AVAILABILITY,
                components=system,
                gateway="threescale",
            ),
            definition(
                "BACKEND_COMPONENT_UNAVAILABLE",
                "Backend component runtime availability is impaired",
                RuleKind.AVAILABILITY,
                components=backend,
                gateway="threescale",
            ),
            definition(
                "BACKEND_EXTERNAL_REDIS_DEPENDENCY_UNRESOLVED",
                "External Redis may contribute to Backend degradation; connectivity is unverified",
                RuleKind.EXTERNAL,
                components=backend,
                gateway="threescale",
                versions=("2.16",),
                capability="REDIS_CONNECTIVITY_NOT_AVAILABLE",
            ),
            definition(
                "SYSTEM_EXTERNAL_REDIS_DEPENDENCY_UNRESOLVED",
                "External Redis may contribute to System degradation; connectivity is unverified",
                RuleKind.EXTERNAL,
                components=system,
                gateway="threescale",
                versions=("2.16",),
                capability="REDIS_CONNECTIVITY_NOT_AVAILABLE",
            ),
            definition(
                "SYSTEM_DATABASE_DEPENDENCY_UNRESOLVED",
                "External database may contribute to System degradation; "
                "connectivity is unverified",
                RuleKind.EXTERNAL,
                components=system,
                gateway="threescale",
                versions=("2.16",),
                capability="DATABASE_CONNECTIVITY_NOT_AVAILABLE",
            ),
        )
