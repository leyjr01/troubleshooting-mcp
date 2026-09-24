"""Approved sources and exact resource-to-provider bindings, disabled by default."""

from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, model_validator

from agt_mcp.configuration.probes import EnvironmentPolicy
from agt_mcp.core.models import Identifier, Model
from agt_mcp.credentials.providers import CredentialReference
from agt_mcp.observability.models import (
    CorrelationKeys,
    LabelName,
    MatchValue,
    MetricIntent,
    SignalType,
)
from agt_mcp.probes.models import Endpoint


class ObservabilityTLS(Model):
    verify: Literal[True] = True
    ca_reference: str | None = Field(default=None, max_length=1024)


class ResourceBinding(Model):
    environment_id: Identifier
    resource_id: Identifier
    keys: CorrelationKeys = CorrelationKeys()
    selectors: dict[LabelName, MatchValue] = Field(min_length=1, max_length=8)


class ObservabilitySource(Model):
    id: Identifier
    type: Literal["memory", "prometheus"]
    enabled: bool = False
    environment_id: Identifier
    usage: tuple[SignalType, ...] = (SignalType.METRIC,)
    url: str | None = Field(default=None, max_length=1024)
    tls: ObservabilityTLS = ObservabilityTLS()
    credentials: CredentialReference | None = None
    network_policy: EnvironmentPolicy | None = None
    bindings: tuple[ResourceBinding, ...] = Field(default=(), max_length=100)
    error_status_label: LabelName = "code"
    metric_names: dict[MetricIntent, LabelName] = Field(
        default_factory=lambda: {
            MetricIntent.AVAILABILITY: "up",
            MetricIntent.RESTARTS: "kube_pod_container_status_restarts_total",
            MetricIntent.RESOURCE_USAGE: "container_cpu_usage_seconds_total",
            MetricIntent.LATENCY: "http_request_duration_seconds",
            MetricIntent.ERROR_RATE: "http_requests_total",
        }
    )

    @model_validator(mode="after")
    def scope(self) -> Self:
        if any(b.environment_id != self.environment_id for b in self.bindings):
            raise ValueError("cross-environment binding")
        if len({b.resource_id for b in self.bindings}) != len(self.bindings):
            raise ValueError("duplicate binding")
        if self.credentials and self.credentials.environment_id != self.environment_id:
            raise ValueError("cross-environment credential")
        if self.network_policy and self.network_policy.environment_id != self.environment_id:
            raise ValueError("cross-environment endpoint policy")
        if self.type == "prometheus":
            parsed = urlsplit(self.url or "")
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("invalid configured endpoint")
            Endpoint(
                id=self.id,
                environment_id=self.environment_id,
                resource_id="observability-source",
                host=parsed.hostname,
                port=parsed.port or (443 if parsed.scheme == "https" else 80),
                protocol=parsed.scheme,
                path=parsed.path or "/",
            )
            if self.credentials and parsed.scheme != "https":
                raise ValueError("credentials require verified HTTPS")
            if self.network_policy is None or set(self.usage) != {SignalType.METRIC}:
                raise ValueError("metrics source requires explicit network policy")
        return self


class ObservabilityLimits(Model):
    max_window_seconds: int = Field(default=3600, ge=1, le=86400)
    max_items: int = Field(default=100, ge=1, le=200)
    max_resources: int = Field(default=12, ge=1, le=12)
    max_text_chars: int = Field(default=2048, ge=64, le=8192)
    max_log_lines: int = Field(default=8, ge=1, le=64)
    max_response_bytes: int = Field(default=262144, ge=1024, le=1048576)
    source_timeout_seconds: float = Field(default=3, gt=0, le=15, allow_inf_nan=False)


class ObservabilityConfig(Model):
    sources: tuple[ObservabilitySource, ...] = Field(default=(), max_length=8)
    limits: ObservabilityLimits = ObservabilityLimits()

    @model_validator(mode="after")
    def unique(self) -> Self:
        if len({s.id for s in self.sources}) != len(self.sources):
            raise ValueError("duplicate observability source")
        return self
