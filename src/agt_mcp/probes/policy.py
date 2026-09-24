"""Pure target authorization. DNS answers must pass this policy before socket creation."""

import ipaddress
from hashlib import sha256

from agt_mcp.configuration.probes import ProbesConfig
from agt_mcp.probes.models import Endpoint, ProbeTarget, ProbeType


class ProbePolicy:
    def __init__(self, config: ProbesConfig) -> None:
        self.config = config

    def target(self, target: ProbeTarget, environment: str, kind: ProbeType, timeout: float) -> str:
        # Exact configured object equality prevents forged origin/provenance declarations.
        approved = next((e for e in self.config.endpoints if e.id == target.id), None)
        endpoint = Endpoint.model_validate(
            target.model_dump(exclude={"derived_from", "provenance"})
        )
        if target.environment_id != environment or target.provenance.environment_id != environment:
            return "ENVIRONMENT_DENIED"
        if (
            approved != endpoint
            or target.provenance.source_id != "approved-probe-endpoints"
            or target.provenance.content_sha256
            != sha256(endpoint.model_dump_json().encode()).hexdigest()
            or target.provenance.source_reference != f"configuration/probes/endpoints/{target.id}"
        ):
            return "TARGET_ORIGIN_DENIED"
        policy = next(
            (e for e in self.config.policy.environments if e.environment_id == environment), None
        )
        if policy is None or target.host not in policy.allowed_hosts:
            return "HOST_DENIED"
        if (
            target.port not in policy.allowed_ports
            or target.protocol not in policy.allowed_protocols
        ):
            return "PROTOCOL_OR_PORT_DENIED"
        allowed = {ProbeType.DNS, ProbeType.TCP}
        if target.protocol in {"tls", "https"}:
            allowed.add(ProbeType.TLS)
        if target.protocol == "https":
            allowed.add(ProbeType.HTTPS)
        if target.protocol == "http":
            allowed.add(ProbeType.HTTP)
        if kind not in allowed or not 0 < timeout <= self.config.limits.timeout_seconds:
            return "PROBE_CONSTRAINT_DENIED"
        try:
            ipaddress.ip_address(target.host)
        except ValueError:
            return "ALLOWED"
        return self.addresses(target, (target.host,))

    def addresses(self, target: ProbeTarget, values: tuple[str, ...]) -> str:
        policy = next(
            (
                e
                for e in self.config.policy.environments
                if e.environment_id == target.environment_id
            ),
            None,
        )
        if policy is None or not values or len(values) > self.config.limits.max_addresses:
            return "DNS_ADDRESS_LIMIT_OR_SCOPE"
        for value in values:
            if "%" in value:
                return "INVALID_ADDRESS"
            try:
                ip = ipaddress.ip_address(value)
            except ValueError:
                return "INVALID_ADDRESS"
            if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
                ip = ip.ipv4_mapped
            if (
                ip.is_unspecified
                or ip.is_multicast
                or (ip.is_reserved and not ip.is_loopback)
                or str(ip) in {"169.254.169.254", "169.254.170.2", "100.100.100.200"}
                or ip in ipaddress.ip_network("fd00:ec2::254/128")
            ):
                return "SPECIAL_ADDRESS_DENIED"
            if any(ip in ipaddress.ip_network(n) for n in policy.denied_networks):
                return "ADDRESS_DENIED"
            matches = [
                ipaddress.ip_network(n)
                for n in policy.allowed_networks
                if ip in ipaddress.ip_network(n)
            ]
            if not matches:
                return "ADDRESS_NOT_APPROVED"
            # Broad public CIDRs cannot accidentally authorize local/private targets.
            if (ip.is_loopback or ip.is_link_local or ip.is_private) and not any(
                n.is_loopback
                if ip.is_loopback
                else n.is_link_local
                if ip.is_link_local
                else n.is_private
                for n in matches
            ):
                return "SPECIAL_RANGE_NOT_EXPLICIT"
            if ip.version == 4 and any(
                ip == n.broadcast_address and n.prefixlen < 31 for n in matches
            ):
                return "BROADCAST_DENIED"
        return "ALLOWED"
