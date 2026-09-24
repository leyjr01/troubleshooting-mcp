"""Pinned-address standard-library networking. No proxies, cookies or credentials."""

import asyncio
import ipaddress
import socket
import ssl
from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlsplit

from agt_mcp.probes.models import (
    ProbeCapability,
    ProbeObservation,
    ProbeRequest,
    ProbeTarget,
    ProbeType,
)
from agt_mcp.probes.planner import target_from
from agt_mcp.probes.policy import ProbePolicy
from agt_mcp.probes.ports import ProbeFailure

Resolver = Callable[[str, int], Awaitable[tuple[str, ...]]]


async def resolve(host: str, port: int) -> tuple[str, ...]:
    try:
        return (str(ipaddress.ip_address(host)),)
    except ValueError:
        records = await asyncio.get_running_loop().getaddrinfo(host, port, type=socket.SOCK_STREAM)
        return tuple(sorted({str(r[4][0]) for r in records}))


class NetworkProbeExecutor:
    def __init__(
        self,
        policy: ProbePolicy,
        resolver: Resolver = resolve,
        tls_context: ssl.SSLContext | None = None,
    ) -> None:
        self.policy, self.resolver = policy, resolver
        self.tls_context = tls_context or ssl.create_default_context()
        if not self.tls_context.check_hostname or self.tls_context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError("TLS verification must remain enabled")

    def capabilities(self) -> frozenset[ProbeCapability]:
        return frozenset(ProbeCapability)

    async def dns(self, target: ProbeTarget) -> tuple[str, ...]:
        try:
            addresses = await self.resolver(target.host, target.port)
        except (OSError, ValueError):
            raise ProbeFailure("DNS_RESOLUTION_FAILED") from None
        reason = self.policy.addresses(target, addresses)
        if reason != "ALLOWED":
            raise ProbeFailure("TARGET_BLOCKED_BY_POLICY", blocked=True)
        return addresses

    async def connect(
        self, target: ProbeTarget, addresses: tuple[str, ...]
    ) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        if self.policy.addresses(target, addresses) != "ALLOWED":
            raise ProbeFailure("TARGET_BLOCKED_BY_POLICY", blocked=True)
        # Never resolve again in socket creation: DNS rebinding cannot change the destination.
        return await asyncio.open_connection(
            addresses[0], target.port, limit=self.policy.config.limits.max_header_bytes + 1
        )

    async def tls(self, writer: asyncio.StreamWriter, target: ProbeTarget) -> ProbeObservation:
        try:
            await writer.start_tls(self.tls_context, server_hostname=target.host)
        except ssl.SSLCertVerificationError as exc:
            raise ProbeFailure(
                "TLS_VERIFICATION_FAILED",
                ProbeObservation(
                    tcp_connected=True,
                    certificate_verified=False,
                    chain_verified=None if exc.verify_code in {62, 64} else False,
                    hostname_verified=False if exc.verify_code in {62, 64} else None,
                ),
            ) from None
        except (ssl.SSLError, ConnectionError):
            raise ProbeFailure(
                "TLS_HANDSHAKE_FAILED", ProbeObservation(tcp_connected=True, tls_handshake=False)
            ) from None
        obj = writer.get_extra_info("ssl_object")
        cert = obj.getpeercert()
        # Only fixed TLS metadata; no raw certificate, application headers or subject text logs.
        from agt_mcp.knowledge.security import KnowledgeRedactor

        redactor = KnowledgeRedactor()
        return ProbeObservation(
            tcp_connected=True,
            tls_handshake=True,
            certificate_verified=True,
            chain_verified=True,
            hostname_verified=True,
            tls_protocol=obj.version(),
            cipher=obj.cipher()[0],
            certificate_subject=redactor.redact(str(cert.get("subject", ()))[:512]),
            certificate_issuer=redactor.redact(str(cert.get("issuer", ()))[:512]),
            sans=tuple(
                redactor.redact(str(v))[:253] for _, v in cert.get("subjectAltName", ())[:16]
            ),
            valid_from=cert.get("notBefore"),
            valid_until=cert.get("notAfter"),
        )

    async def close(self, writer: asyncio.StreamWriter) -> None:
        writer.close()
        try:
            async with asyncio.timeout(0.2):
                await writer.wait_closed()
        except (OSError, TimeoutError):
            return  # close() already released the transport; bounded shutdown is best effort.

    async def http(self, target: ProbeTarget, addresses: tuple[str, ...]) -> ProbeObservation:
        redirects: list[str] = []
        for _ in range(self.policy.config.limits.max_redirects + 1):
            reader, writer = await self.connect(target, addresses)
            observation = ProbeObservation(tcp_connected=True)
            try:
                if target.protocol == "https":
                    observation = await self.tls(writer, target)
                host = f"[{target.host}]" if ":" in target.host else target.host
                request = (
                    f"{target.method} {target.path} HTTP/1.1\r\n"
                    f"Host: {host}:{target.port}\r\nConnection: close\r\n\r\n"
                )
                writer.write(request.encode("ascii"))
                await writer.drain()
                try:
                    headers = await reader.readuntil(b"\r\n\r\n")
                    if len(headers) > self.policy.config.limits.max_header_bytes:
                        raise ValueError("headers too large")
                    lines = headers.decode("ascii").split("\r\n")
                    version, code, *_ = lines[0].split(" ")
                    status = int(code)
                    if version not in {"HTTP/1.0", "HTTP/1.1"} or not 100 <= status <= 599:
                        raise ValueError("invalid status")
                    fields: dict[str, str] = {}
                    for line in lines[1:-2]:
                        key, value = line.split(":", 1)
                        key = key.lower()
                        if key in fields or any(ord(c) < 32 for c in value.strip()):
                            raise ValueError("ambiguous header")
                        fields[key] = value.strip()
                except (
                    ValueError,
                    UnicodeError,
                    asyncio.IncompleteReadError,
                    asyncio.LimitOverrunError,
                ):
                    raise ProbeFailure("HTTP_PROTOCOL_ERROR", observation) from None
            finally:
                await self.close(writer)
            safe: dict[str, Any] = {"http_status": status, "redirects": tuple(redirects)}
            # Numeric metadata only: response headers may themselves contain secrets.
            safe["headers"] = (
                {"content-length": fields["content-length"]}
                if fields.get("content-length", "").isdigit()
                and len(fields["content-length"]) <= 12
                else {}
            )
            observation = observation.model_copy(update=safe)
            if status not in {301, 302, 303, 307, 308}:
                return observation
            if len(redirects) >= self.policy.config.limits.max_redirects:
                raise ProbeFailure("REDIRECT_LIMIT", observation, blocked=True)
            location = fields.get("location", "")
            # Redirect URL is never returned or logged; credentials/query/fragment are rejected.
            try:
                parsed = urlsplit(location)
                if (
                    parsed.username
                    or parsed.password
                    or parsed.query
                    or parsed.fragment
                    or "\\" in location
                ):
                    raise ValueError("unsafe redirect")
                endpoint = next(
                    (
                        e
                        for e in self.policy.config.endpoints
                        if e.environment_id == target.environment_id
                        and e.resource_id == target.resource_id
                        and e.host == parsed.hostname
                        and e.protocol == parsed.scheme
                        and e.port == (parsed.port or (443 if parsed.scheme == "https" else 80))
                        and e.path == (parsed.path or "/")
                    ),
                    None,
                )
                if endpoint is None or (
                    target.protocol == "https" and endpoint.protocol != "https"
                ):
                    raise ValueError("unapproved redirect")
                redirected = target_from(endpoint, target.provenance.retrieved_at)
                if (
                    self.policy.target(
                        redirected,
                        target.environment_id,
                        ProbeType(redirected.protocol.upper()),
                        self.policy.config.limits.timeout_seconds,
                    )
                    != "ALLOWED"
                ):
                    raise ValueError("policy denied redirect")
            except ValueError:
                raise ProbeFailure("REDIRECT_BLOCKED", observation, blocked=True) from None
            addresses = await self.dns(redirected)
            redirects.append(redirected.id)
            target = redirected
        raise ProbeFailure("REDIRECT_LIMIT", blocked=True)

    async def execute(self, request: ProbeRequest, addresses: tuple[str, ...]) -> ProbeObservation:
        target = request.target
        if (
            self.policy.target(
                target, target.environment_id, request.probe_type, request.timeout_seconds
            )
            != "ALLOWED"
        ):
            raise ProbeFailure("TARGET_BLOCKED_BY_POLICY", blocked=True)
        try:
            if request.probe_type == ProbeType.DNS:
                return ProbeObservation(addresses=await self.dns(target))
            if request.probe_type in {ProbeType.HTTP, ProbeType.HTTPS}:
                return await self.http(target, addresses)
            _, writer = await self.connect(target, addresses)
            try:
                if request.probe_type == ProbeType.TLS:
                    return await self.tls(writer, target)
                return ProbeObservation(tcp_connected=True)
            finally:
                await self.close(writer)
        except ConnectionRefusedError:
            raise ProbeFailure("CONNECTION_REFUSED") from None
        except OSError:
            raise ProbeFailure("NETWORK_ERROR") from None
