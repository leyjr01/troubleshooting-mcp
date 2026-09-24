"""Protocol-neutral evidence rules, with no concrete executor dependency."""

from agt_mcp.core.models import ResourceKind
from agt_mcp.troubleshooting.catalog import definition
from agt_mcp.troubleshooting.models import HypothesisDefinition, RuleKind


class NetworkHypothesisProvider:
    def definitions(self) -> tuple[HypothesisDefinition, ...]:
        kinds = (
            ResourceKind.SERVICE,
            ResourceKind.ROUTE,
            ResourceKind.BACKEND,
            ResourceKind.EXTERNAL_SERVICE,
            ResourceKind.GATEWAY,
            ResourceKind.POD,
        )
        return (
            definition(
                "TLS_VERIFICATION_UNAVAILABLE",
                "TLS verification unavailable from probe vantage point; not an incident root cause",
                RuleKind.PROBE_TLS,
                kinds,
            ),
            definition(
                "DEPENDENCY_TCP_UNAVAILABLE",
                "TCP connectivity unavailable from probe vantage point; "
                "no protocol or firewall cause inferred",
                RuleKind.PROBE_TCP,
                kinds,
            ),
        )
