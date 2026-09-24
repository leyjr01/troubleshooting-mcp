"""Small Prometheus v1 GET client with pinned addresses and no arbitrary expressions."""

import asyncio
import json
import math
import re
import ssl
from datetime import UTC, datetime
from typing import Literal, Protocol
from urllib.parse import urlencode, urlsplit

from agt_mcp.configuration.observability import ObservabilityLimits, ObservabilitySource
from agt_mcp.configuration.probes import ProbePolicyConfig, ProbesConfig
from agt_mcp.core.errors import AuthenticationError, AuthorizationError
from agt_mcp.correlation.rules import identity
from agt_mcp.credentials.providers import CredentialProvider
from agt_mcp.datasources.probe_network import NetworkProbeExecutor
from agt_mcp.observability.models import (
    AdapterBatch,
    MetricIntent,
    MetricObservation,
    ObservabilityQuery,
    SignalType,
)
from agt_mcp.probes.models import Endpoint, ProbeType
from agt_mcp.probes.planner import target_from
from agt_mcp.probes.policy import ProbePolicy


class MetricsHTTP(Protocol):
    async def get(self, path: str, parameters: dict[str, str]) -> tuple[int, bytes]: ...


class ApprovedMetricsHTTP:
    def __init__(
        self,
        config: ObservabilitySource,
        limits: ObservabilityLimits,
        credentials: CredentialProvider | None = None,
        tls_context: ssl.SSLContext | None = None,
    ) -> None:
        self.config, self.limits, self.credentials = config, limits, credentials
        parsed = urlsplit(config.url or "")
        endpoint = Endpoint(
            id=config.id,
            environment_id=config.environment_id,
            resource_id="observability-source",
            host=parsed.hostname or "invalid",
            port=parsed.port or (443 if parsed.scheme == "https" else 80),
            protocol=parsed.scheme,
            path=parsed.path or "/",
        )
        self.target = target_from(endpoint, datetime.now(UTC))
        if config.network_policy is None:
            raise ValueError("network policy required")
        self.policy = ProbePolicy(
            ProbesConfig(
                endpoints=(endpoint,),
                policy=ProbePolicyConfig(environments=(config.network_policy,)),
            )
        )
        # Injecting a verified SSLContext is the extension point for operator-managed mTLS.
        context = tls_context or ssl.create_default_context(cafile=config.tls.ca_reference)
        self.network = NetworkProbeExecutor(self.policy, tls_context=context)

    async def get(self, path: str, parameters: dict[str, str]) -> tuple[int, bytes]:
        if path not in {"/api/v1/query", "/api/v1/query_range", "/-/ready"}:
            raise AuthorizationError()
        target = self.target
        kind = ProbeType.HTTPS if target.protocol == "https" else ProbeType.HTTP
        if self.policy.target(target, self.config.environment_id, kind, 3) != "ALLOWED":
            raise AuthorizationError()
        async with asyncio.timeout(self.limits.source_timeout_seconds):
            addresses = await self.network.dns(target)
            reader, writer = await self.network.connect(target, addresses)
            try:
                if target.protocol == "https":
                    await self.network.tls(writer, target)
                authorization = ""
                token: str | None = None
                if self.config.credentials:
                    if self.credentials is None:
                        raise AuthenticationError()
                    token = (
                        await self.credentials.resolve(self.config.credentials)
                    ).get_secret_value()
                    if not re.fullmatch(r"[A-Za-z0-9._~+/-]{1,8192}=*", token):
                        raise AuthenticationError()
                    authorization = f"Authorization: Bearer {token}\r\n"
                host = f"[{target.host}]" if ":" in target.host else target.host
                url_path = target.path.rstrip("/") + path
                if parameters:
                    url_path += "?" + urlencode(parameters)
                writer.write(
                    (
                        f"GET {url_path} HTTP/1.1\r\nHost: {host}:{target.port}\r\n"
                        + authorization
                        + "Accept: application/json\r\nConnection: close\r\n\r\n"
                    ).encode("ascii")
                )
                await writer.drain()
                headers = await reader.readuntil(b"\r\n\r\n")
                if len(headers) > 8192:
                    raise ValueError("header limit")
                lines = headers.decode("ascii").split("\r\n")
                version, status_text, *_ = lines[0].split(" ")
                status = int(status_text)
                if version not in {"HTTP/1.0", "HTTP/1.1"} or not 100 <= status <= 599:
                    raise ValueError("invalid HTTP status")
                fields: dict[str, str] = {}
                for line in lines[1:-2]:
                    key, value = line.split(":", 1)
                    key = key.lower()
                    if key in fields:
                        raise ValueError("duplicate HTTP header")
                    fields[key] = value.strip()
                if status != 200:
                    return status, b""  # Includes all redirects; never follow or return Location.
                if fields.get("content-encoding", "identity").lower() != "identity":
                    raise ValueError("compressed responses unsupported")
                if "transfer-encoding" in fields:
                    if (
                        fields["transfer-encoding"].lower() != "chunked"
                        or "content-length" in fields
                    ):
                        raise ValueError("unsupported framing")
                    body = bytearray()
                    while True:
                        size = int((await reader.readline()).strip(), 16)
                        if size < 0 or len(body) + size > self.limits.max_response_bytes:
                            raise ValueError("body limit")
                        if size == 0:
                            break
                        body.extend(await reader.readexactly(size))
                        if await reader.readexactly(2) != b"\r\n":
                            raise ValueError("invalid chunk")
                    raw = bytes(body)
                elif "content-length" in fields:
                    length = int(fields["content-length"])
                    if not 0 <= length <= self.limits.max_response_bytes:
                        raise ValueError("body limit")
                    raw = await reader.readexactly(length)
                else:
                    parts = bytearray()
                    while chunk := await reader.read(
                        min(8192, self.limits.max_response_bytes + 1 - len(parts))
                    ):
                        parts.extend(chunk)
                        if len(parts) > self.limits.max_response_bytes:
                            raise ValueError("body limit")
                    raw = bytes(parts)
                if token:
                    # Decode JSON escapes before removing an echoed credential.
                    try:
                        raw = json.dumps(json.loads(raw), ensure_ascii=False).encode()
                    except (ValueError, UnicodeError):
                        pass  # Readiness may return plain text; it is never Evidence.
                    raw = raw.replace(token.encode(), b"[REDACTED]")
                return status, raw
            finally:
                await self.network.close(writer)


class PrometheusObservabilityAdapter:
    def __init__(
        self, config: ObservabilitySource, limits: ObservabilityLimits, transport: MetricsHTTP
    ) -> None:
        self.config, self.limits, self.transport = config, limits, transport

    def capabilities(self) -> frozenset[SignalType]:
        return frozenset({SignalType.METRIC})

    async def health(self) -> Literal["AVAILABLE", "UNAVAILABLE"]:
        try:
            status, _ = await self.transport.get("/-/ready", {})
            if status in {401, 403}:
                raise AuthorizationError()
            return "AVAILABLE" if status == 200 else "UNAVAILABLE"
        except AuthorizationError:
            raise
        except Exception:
            return "UNAVAILABLE"

    async def query(self, query: ObservabilityQuery) -> AdapterBatch:
        if (
            not self.config.enabled
            or query.environment_id != self.config.environment_id
            or not query.resource_refs
            or query.signal_types != (SignalType.METRIC,)
        ):
            raise AuthorizationError()
        if (
            query.time_window.end - query.time_window.start
        ).total_seconds() > self.limits.max_window_seconds:
            raise ValueError("window limit")
        rows: list[MetricObservation] = []
        bound = min(query.limit, self.limits.max_items)
        warnings: set[str] = set()
        metric = self.config.metric_names.get(query.metric_intent)
        if metric is None:
            return AdapterBatch(warnings=("metric_intent_unavailable",))
        for resource in sorted(set(query.resource_refs)):
            binding = next((b for b in self.config.bindings if b.resource_id == resource), None)
            if binding is None:
                raise AuthorizationError()
            filters = query.filters.model_dump(exclude_none=True)
            if query.trace_id:
                filters["trace_id"] = query.trace_id
            if query.correlation_id:
                filters["correlation_id"] = query.correlation_id
            if any(binding.keys.model_dump()[k] != v for k, v in filters.items()):
                continue
            selectors = ",".join(f'{k}="{v}"' for k, v in sorted(binding.selectors.items()))
            duration = (query.time_window.end - query.time_window.start).total_seconds()
            if query.metric_intent == MetricIntent.ERROR_RATE:
                selectors += f',{self.config.error_status_label}=~"5.."'
            expression = f"{metric}{{{selectors}}}"
            if query.metric_intent == MetricIntent.ERROR_RATE:
                expression = f"rate({expression}[{max(1, min(300, int(duration)))}s])"
            step = max(query.step_seconds, math.ceil(duration / max(1, query.limit - 1)))
            parameters = {
                "query": expression,
                "timeout": f"{self.limits.source_timeout_seconds}s",
                "limit": str(min(query.limit, self.limits.max_items)),
            }
            if query.metric_mode == "instant":
                path = "/api/v1/query"
                parameters["time"] = str(query.time_window.end.timestamp())
            else:
                path = "/api/v1/query_range"
                parameters.update(
                    start=str(query.time_window.start.timestamp()),
                    end=str(query.time_window.end.timestamp()),
                    step=str(step),
                )
            status, raw = await self.transport.get(path, parameters)
            if status in {401, 403}:
                raise AuthorizationError()
            if status != 200:
                raise ConnectionError()
            if len(raw) > self.limits.max_response_bytes:
                raise ValueError("response limit")
            data = json.loads(raw)
            if data.get("status") != "success":
                raise ValueError("invalid provider response")
            if data.get("warnings"):
                warnings.add("provider_warning")
            result = data["data"]
            if result["resultType"] != ("vector" if query.metric_mode == "instant" else "matrix"):
                raise ValueError("unsupported metric representation")
            series = result["result"]
            if not isinstance(series, list):
                raise ValueError("invalid result")
            for item in series:
                labels = item["metric"]
                if any(labels.get(k) != v for k, v in binding.selectors.items()):
                    raise AuthorizationError()
                values = [item["value"]] if query.metric_mode == "instant" else item["values"]
                for timestamp, value in values:
                    when = datetime.fromtimestamp(float(timestamp), UTC)
                    if not query.time_window.start <= when <= query.time_window.end:
                        warnings.add("out_of_window_signal")
                        continue
                    row = MetricObservation(
                        id=identity(
                            "metric",
                            self.config.id,
                            resource,
                            json.dumps(labels, sort_keys=True),
                            str(timestamp),
                            str(value),
                        ),
                        environment_id=query.environment_id,
                        source_id=self.config.id,
                        resource_id=resource,
                        timestamp=when,
                        keys=binding.keys,
                        labels=labels,
                        metric=metric,
                        value=float(value),
                    )
                    if row.id not in {r.id for r in rows}:
                        rows.append(row)
                        rows.sort(key=lambda r: (r.timestamp, r.resource_id, r.id))
                    if len(rows) > bound:
                        warnings.add("source_limit_reached")
                        rows.pop()
        return AdapterBatch(observations=tuple(rows), warnings=tuple(sorted(warnings)))
