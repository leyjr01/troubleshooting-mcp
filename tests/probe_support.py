"""Offline approved endpoints and deterministic probe doubles."""

from agt_mcp.configuration.probes import EnvironmentPolicy, ProbePolicyConfig, ProbesConfig
from agt_mcp.probes.models import Endpoint, ProbeCapability, ProbeObservation, ProbeType
from agt_mcp.probes.planner import ProbePlanner
from agt_mcp.probes.policy import ProbePolicy
from agt_mcp.probes.ports import ProbeFailure
from agt_mcp.trace.builder import VirtualTraceBuilder
from tests.correlation_support import NOW
from tests.troubleshooting_support import diagnose


def config(host="backend.example", port=443, protocol="https", **changes):
    endpoint = Endpoint(
        id="backend",
        environment_id="demo",
        resource_id="service",
        host=host,
        port=port,
        protocol=protocol,
    )
    base = ProbesConfig(
        enabled=True,
        execution_mode="execute_allowed",
        endpoints=(endpoint,),
        policy=ProbePolicyConfig(
            environments=(
                EnvironmentPolicy(
                    environment_id="demo",
                    allowed_hosts=(host,),
                    allowed_networks=("10.20.0.0/16", "127.0.0.0/8", "::1/128"),
                    allowed_ports=(port,),
                    allowed_protocols=(protocol,),
                ),
            )
        ),
    )
    return ProbesConfig.model_validate({**base.model_dump(), **changes})


def trace():
    return VirtualTraceBuilder(config().trace).build(diagnose().correlation_result)


def plan(settings=None):
    policy = ProbePolicy(settings or config())
    return ProbePlanner(policy, frozenset(ProbeCapability)).plan(trace(), NOW)


class FakeExecutor:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []

    def capabilities(self):
        return frozenset(ProbeCapability)

    async def execute(self, request, addresses):
        self.calls.append((request.probe_type, addresses))
        if request.probe_type == self.failure:
            observation = (
                ProbeObservation(tcp_connected=True, certificate_verified=False)
                if self.failure == ProbeType.TLS
                else ProbeObservation()
            )
            raise ProbeFailure(
                {
                    ProbeType.DNS: "DNS_RESOLUTION_FAILED",
                    ProbeType.TCP: "CONNECTION_REFUSED",
                    ProbeType.TLS: "TLS_VERIFICATION_FAILED",
                }[self.failure],
                observation,
            )
        return {
            ProbeType.DNS: ProbeObservation(addresses=("10.20.1.2",)),
            ProbeType.TCP: ProbeObservation(tcp_connected=True),
            ProbeType.TLS: ProbeObservation(
                tcp_connected=True,
                tls_handshake=True,
                certificate_verified=True,
                hostname_verified=True,
            ),
            ProbeType.HTTPS: ProbeObservation(http_status=503),
            ProbeType.HTTP: ProbeObservation(http_status=200),
        }[request.probe_type]
