"""Deny-by-default network observation and trace bounds."""

import ipaddress
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from agt_mcp.core.models import Identifier, Model
from agt_mcp.probes.models import Endpoint


class TraceLimits(Model):
    max_hops: int = Field(default=40, ge=1, le=200)
    max_branches: int = Field(default=8, ge=1, le=32)
    max_nodes: int = Field(default=40, ge=1, le=200)
    max_depth: int = Field(default=3, ge=0, le=3)


class ProbeLimits(Model):
    max_probes_per_request: int = Field(default=16, ge=1, le=100)
    max_parallel_probes: int = Field(default=2, ge=1, le=8)
    timeout_seconds: float = Field(default=3, gt=0, le=30, allow_inf_nan=False)
    overall_probe_budget: float = Field(default=15, gt=0, le=60, allow_inf_nan=False)
    max_addresses: int = Field(default=8, ge=1, le=16)
    max_redirects: int = Field(default=0, ge=0, le=5)
    max_header_bytes: int = Field(default=8192, ge=256, le=32768)
    cache_entries: int = Field(default=16, ge=1, le=100)
    cache_ttl_seconds: int = Field(default=300, ge=1, le=3600)


class EnvironmentPolicy(Model):
    environment_id: Identifier
    allowed_hosts: tuple[str, ...] = ()
    allowed_networks: tuple[str, ...] = ()
    denied_networks: tuple[str, ...] = ()
    allowed_ports: tuple[int, ...] = Field(default=(80, 443), max_length=64)
    allowed_protocols: tuple[Literal["tcp", "tls", "http", "https"], ...] = ()

    @field_validator("allowed_networks", "denied_networks")
    @classmethod
    def networks(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(str(ipaddress.ip_network(v)) for v in values)

    @field_validator("allowed_hosts")
    @classmethod
    def hosts(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(Endpoint.hostname(v) for v in values)

    @field_validator("allowed_ports")
    @classmethod
    def ports(cls, values: tuple[int, ...]) -> tuple[int, ...]:
        if any(not 1 <= p <= 65535 for p in values):
            raise ValueError("invalid allowed port")
        return values


class ProbePolicyConfig(Model):
    environments: tuple[EnvironmentPolicy, ...] = ()


class ProbesConfig(Model):
    enabled: bool = False
    execution_mode: Literal["plan_only", "execute_allowed"] = "plan_only"
    limits: ProbeLimits = ProbeLimits()
    policy: ProbePolicyConfig = ProbePolicyConfig()
    endpoints: tuple[Endpoint, ...] = Field(default=(), max_length=100)
    trace: TraceLimits = TraceLimits()

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({e.id for e in self.endpoints}) != len(self.endpoints):
            raise ValueError("duplicate endpoint")
        if len({e.environment_id for e in self.policy.environments}) != len(
            self.policy.environments
        ):
            raise ValueError("duplicate environment policy")
        return self
