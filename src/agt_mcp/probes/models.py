"""Bounded observations; targets are configured by operators, never tool arguments."""

import ipaddress
import re
from enum import StrEnum
from hashlib import sha256
from typing import Literal, Self

from pydantic import AwareDatetime, Field, field_validator, model_validator

from agt_mcp.core.models import Evidence, Identifier, Model, Provenance


class ProbeType(StrEnum):
    DNS = "DNS"
    TCP = "TCP"
    TLS = "TLS"
    HTTP = "HTTP"
    HTTPS = "HTTPS"


class ProbeStatus(StrEnum):
    # Observation status, not a password or credential.
    PASS = "PASS"  # nosec B105
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NOT_EXECUTED = "NOT_EXECUTED"
    CANCELLED = "CANCELLED"


class ProbeCapability(StrEnum):
    DNS = "dns.resolve"
    TCP = "tcp.connect"
    TLS = "tls.handshake"
    HTTP = "http.request"


CAPABILITIES = {
    ProbeType.DNS: ProbeCapability.DNS,
    ProbeType.TCP: ProbeCapability.TCP,
    ProbeType.TLS: ProbeCapability.TLS,
    ProbeType.HTTP: ProbeCapability.HTTP,
    ProbeType.HTTPS: ProbeCapability.HTTP,
}


class Endpoint(Model):
    id: Identifier
    environment_id: Identifier
    resource_id: Identifier
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(ge=1, le=65535)
    protocol: Literal["tcp", "tls", "http", "https"]
    path: str = Field(default="/", max_length=512)
    method: Literal["HEAD", "GET"] = "HEAD"

    @field_validator("host")
    @classmethod
    def hostname(cls, value: str) -> str:
        value = value.lower().removesuffix(".")
        if "%" in value:
            raise ValueError("scoped IP addresses are not supported")
        try:
            return str(ipaddress.ip_address(value))
        except ValueError:
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", value):
                raise ValueError("invalid host") from None
            if all(c in "0123456789." for c in value) or value.startswith("0x"):
                raise ValueError("ambiguous numeric host") from None
            if any(
                not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", x)
                for x in value.split(".")
            ):
                raise ValueError("invalid host labels") from None
            return value

    @field_validator("path")
    @classmethod
    def safe_path(cls, value: str) -> str:
        if not re.fullmatch(r"/[A-Za-z0-9_./~-]*", value) or "//" in value or ".." in value:
            raise ValueError("invalid path")
        return value


class ProbeTarget(Endpoint):
    derived_from: Literal["configured_approved_endpoint"] = "configured_approved_endpoint"
    provenance: Provenance

    @model_validator(mode="after")
    def scope(self) -> Self:
        if self.provenance.environment_id != self.environment_id:
            raise ValueError("target provenance scope")
        return self


class ProbeRequest(Model):
    id: Identifier
    target: ProbeTarget
    probe_type: ProbeType
    timeout_seconds: float = Field(default=3, gt=0, le=30, allow_inf_nan=False)
    allowed: bool
    reason: Identifier
    required_capability: ProbeCapability


class ProbePlan(Model):
    id: Identifier
    trace_id: Identifier
    environment_id: Identifier
    requests: tuple[ProbeRequest, ...] = Field(max_length=100)
    warnings: tuple[Identifier, ...] = ()
    executed: Literal[False] = False

    @model_validator(mode="after")
    def scope(self) -> Self:
        if any(r.target.environment_id != self.environment_id for r in self.requests):
            raise ValueError("cross-environment probe plan")
        if len({r.id for r in self.requests}) != len(self.requests):
            raise ValueError("duplicate probe request")
        chains: dict[str, list[ProbeType]] = {}
        for request in self.requests:
            chain = chains.setdefault(request.target.id, [])
            expected = [ProbeType.DNS, ProbeType.TCP]
            if request.target.protocol in {"tls", "https"}:
                expected.append(ProbeType.TLS)
            if request.target.protocol in {"http", "https"}:
                expected.append(ProbeType(request.target.protocol.upper()))
            chain.append(request.probe_type)
            if (
                chain != expected[: len(chain)]
                or request.required_capability != CAPABILITIES[request.probe_type]
            ):
                raise ValueError("invalid probe dependency chain")
        return self


class ProbeObservation(Model):
    addresses: tuple[str, ...] = Field(default=(), max_length=16)
    tcp_connected: bool | None = None
    tls_handshake: bool | None = None
    certificate_verified: bool | None = None
    chain_verified: bool | None = None
    hostname_verified: bool | None = None
    tls_protocol: str | None = Field(default=None, max_length=32)
    cipher: str | None = Field(default=None, max_length=128)
    certificate_subject: str | None = Field(default=None, max_length=512)
    certificate_issuer: str | None = Field(default=None, max_length=512)
    sans: tuple[str, ...] = Field(default=(), max_length=16)
    valid_from: str | None = Field(default=None, max_length=64)
    valid_until: str | None = Field(default=None, max_length=64)
    http_status: int | None = Field(default=None, ge=100, le=599)
    headers: dict[str, str] = Field(default_factory=dict, max_length=4)
    redirects: tuple[Identifier, ...] = Field(default=(), max_length=5)


class ProbeResult(Model):
    request_id: Identifier
    target: ProbeTarget
    probe_type: ProbeType
    status: ProbeStatus
    error_category: Identifier | None = None
    timestamp: AwareDatetime
    duration_ms: float = Field(ge=0, allow_inf_nan=False)
    observation: ProbeObservation = ProbeObservation()


class ProbeEvidence(Model):
    result: ProbeResult
    evidence: Evidence

    @model_validator(mode="after")
    def lineage(self) -> Self:
        target, evidence = self.result.target, self.evidence
        if (
            evidence.source.content_sha256
            != sha256(self.result.model_dump_json().encode()).hexdigest()
        ):
            raise ValueError("probe evidence checksum mismatch")
        if (
            evidence.environment_id != target.environment_id
            or evidence.source.environment_id != target.environment_id
            or evidence.resource_id != target.resource_id
            or evidence.timestamp != self.result.timestamp
        ):
            raise ValueError("invalid probe evidence provenance")
        return self
