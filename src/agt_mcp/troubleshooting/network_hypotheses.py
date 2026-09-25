"""Protocol-neutral evidence rules, with no concrete executor dependency."""

from agt_mcp.core.models import ResourceKind
from agt_mcp.troubleshooting.catalog import definition, requirement
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
                "DNS_RESOLUTION_FAILURE",
                "DNS resolution failed for the approved target from the probe vantage point",
                RuleKind.PROBE_DNS,
                kinds,
            ),
            definition(
                "BACKEND_HTTP_ERROR",
                "Approved backend returned an HTTP server error; "
                "underlying application cause unknown",
                RuleKind.PROBE_HTTP,
                kinds,
            ),
            definition(
                "BACKEND_TIMEOUT",
                "HTTP request to the approved backend timed out; underlying latency cause unknown",
                RuleKind.PROBE_TIMEOUT,
                kinds,
            ),
            definition(
                "TLS_VERIFICATION_UNAVAILABLE",
                "TLS verification unavailable from probe vantage point; not an incident root cause",
                RuleKind.PROBE_TLS,
                kinds,
            ).model_copy(
                update={
                    "optional_evidence": (
                        requirement(
                            "tls_verification",
                            "Validate certificate validity, deployed certificate chain "
                            "and reference",
                        ).model_copy(update={"optional": True, "purpose": "strengthen"}),
                    )
                }
            ),
            definition(
                "DEPENDENCY_TCP_UNAVAILABLE",
                "TCP connectivity unavailable from probe vantage point; "
                "no protocol or firewall cause inferred",
                RuleKind.PROBE_TCP,
                kinds,
            ),
        )
