"""Bounded runtime discovery through the official SDK; namespace and environment scoped."""

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from time import monotonic
from typing import Any

from pydantic import TypeAdapter

from agt_mcp.configuration.runtime import RuntimeEnvironment
from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    DataSourceUnavailable,
    ResourceNotFound,
    SanitizationError,
    TimeoutError,
    UnsupportedCapabilityError,
)
from agt_mcp.core.execution import ExecutionContext
from agt_mcp.core.runtime import (
    CategoryResult,
    DiscoveryWarning,
    RuntimeAdapter,
    RuntimeEvents,
    RuntimeName,
    RuntimeQuery,
    RuntimeSnapshot,
)
from agt_mcp.datasources.kubernetes.catalog import DISCOVERY_APIS, ROUTE, TYPES, ResourceType
from agt_mcp.datasources.kubernetes.client import KubernetesClient, RuntimeClient
from agt_mcp.datasources.kubernetes.graph import GraphBuilder


class KubernetesRuntimeAdapter(RuntimeAdapter):
    def __init__(
        self, environment: RuntimeEnvironment, client: RuntimeClient | None = None
    ) -> None:
        if environment.runtime is None:
            raise ConfigurationError()
        self.environment, self.settings = environment, environment.runtime
        self.client: RuntimeClient = client or KubernetesClient(environment)
        self._open = False
        self._lock = asyncio.Lock()
        self._default_namespace = environment.namespace or "default"
        self.types: tuple[ResourceType, ...] = (
            *TYPES,
            *((ROUTE,) if self.settings.provider == "openshift" else ()),
            *(
                ResourceType(
                    c.kind, f"{c.group}/{c.version}", c.plural, "CustomObjectsApi", c.namespaced
                )
                for c in self.settings.discovery.custom_resources
            ),
        )

    async def _prepare(self, context: ExecutionContext, query: RuntimeQuery) -> tuple[str, ...]:
        if context.environment_id != self.environment.id or not self.environment.enabled:
            raise AuthorizationError()
        if query.depth > self.settings.discovery.limits.max_topology_depth:
            raise ConfigurationError()
        scope = self.settings.discovery.namespaces
        # Explicit forbidden requests fail before credentials are even loaded.
        if query.namespace and (
            query.namespace in scope.exclude
            or (scope.include and query.namespace not in scope.include)
        ):
            raise AuthorizationError()
        async with self._lock:
            if not self._open:
                self._default_namespace = TypeAdapter(RuntimeName).validate_python(
                    await self.client.open()
                )
                self._open = True
        allowed = tuple(
            sorted(set(scope.include or (self._default_namespace,)) - set(scope.exclude))
        )
        if query.namespace:
            if query.namespace not in allowed:
                raise AuthorizationError()
            return (query.namespace,)
        return allowed

    def _resolve_type(self, query: RuntimeQuery) -> ResourceType:
        types = [
            t
            for t in self.types
            if t.kind == query.kind
            and (not query.api_version or t.api_version == query.api_version)
        ]
        if len(types) != 1:
            raise UnsupportedCapabilityError()
        if not types[0].namespaced and not self.settings.discovery.cluster_scoped:
            raise AuthorizationError()
        return types[0]

    async def _capabilities(
        self, context: ExecutionContext
    ) -> tuple[dict[str, set[str]], list[DiscoveryWarning]]:
        result: dict[str, set[str]] = {}
        warnings: list[DiscoveryWarning] = []
        for version in sorted(set(DISCOVERY_APIS) | {t.api_version for t in self.types}):
            try:
                data = await self.client.api_resources(version, context)
                resources = data.get("resources", [])
                if not isinstance(resources, list) or any(
                    not isinstance(r, dict) for r in resources
                ):
                    raise SanitizationError()
                result[version] = {
                    r["name"]
                    for r in resources
                    if isinstance(r.get("name"), str)
                    and "/" not in r["name"]
                    and "list" in r.get("verbs", [])
                }
            except ResourceNotFound:
                # Absent optional APIs are normal; requested categories report unsupported.
                continue
            except AuthorizationError:
                warnings.append(DiscoveryWarning(code="forbidden_resource", kind="api-discovery"))
            except (DataSourceUnavailable, TimeoutError, SanitizationError):
                warnings.append(DiscoveryWarning(code="unavailable", kind="api-discovery"))
        return result, warnings

    async def _collect(
        self,
        resource: ResourceType,
        namespace: str | None,
        context: ExecutionContext,
        budget: int,
        field_selector: str | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        items: list[dict[str, Any]] = []
        continuation: str | None = None
        seen: set[str] = set()
        while len(items) < budget:
            page = await self.client.list_resources(
                resource,
                namespace,
                min(self.settings.discovery.limits.page_size, budget - len(items)),
                continuation,
                context,
                field_selector,
            )
            received = page.get("items", [])
            if (
                not isinstance(received, list)
                or any(not isinstance(r, dict) for r in received)
                or not isinstance(page.get("metadata", {}), dict)
            ):
                raise SanitizationError()
            remaining = budget - len(items)
            items.extend(received[:remaining])
            continuation = page.get("metadata", {}).get("continue")
            if len(received) > remaining or (
                continuation
                and (
                    not isinstance(continuation, str)
                    or len(continuation) > 4096
                    or continuation in seen
                )
            ):
                return items, "truncated"
            if not continuation:
                return items, "completed"
            seen.add(continuation)
        return items, "truncated"

    async def discover(self, context: ExecutionContext, query: RuntimeQuery) -> RuntimeSnapshot:
        return await self._snapshot(context, query)

    async def inspect(self, context: ExecutionContext, query: RuntimeQuery) -> RuntimeSnapshot:
        namespaces = await self._prepare(context, query)
        resource = self._resolve_type(query)
        if not query.name or (resource.namespaced and len(namespaces) != 1):
            raise ConfigurationError()
        namespace = namespaces[0] if resource.namespaced else None
        raw = await self.client.read_resource(resource, namespace, query.name, context)
        self._validate_read(raw, resource, namespace, query.name)
        return await self._snapshot(context, query, raw)

    @staticmethod
    def _validate_read(
        raw: dict[str, Any], resource: ResourceType, namespace: str | None, name: str
    ) -> None:
        metadata = raw.get("metadata", {})
        if (
            raw.get("kind") != resource.kind
            or raw.get("apiVersion") != resource.api_version
            or not isinstance(metadata, dict)
            or metadata.get("namespace") != namespace
            or metadata.get("name") != name
        ):
            raise SanitizationError()

    async def _snapshot(
        self, context: ExecutionContext, query: RuntimeQuery, root: dict[str, Any] | None = None
    ) -> RuntimeSnapshot:
        namespaces = await self._prepare(context, query)
        limits = self.settings.discovery.limits
        warnings: list[DiscoveryWarning] = []
        if len(namespaces) > limits.max_namespaces:
            warnings.append(DiscoveryWarning(code="truncated_discovery"))
        namespaces = namespaces[: limits.max_namespaces]
        apis, api_warnings = await self._capabilities(context)
        warnings.extend(api_warnings)
        observed = datetime.now(UTC)
        categories: list[CategoryResult] = []
        builder = GraphBuilder(
            self.environment.id, self.environment.cluster, observed, limits, categories
        )
        if root is not None:
            builder.add(root)
        for resource in self.types:
            if not resource.namespaced and not self.settings.discovery.cluster_scoped:
                continue
            for namespace in namespaces if resource.namespaced else (None,):
                started = monotonic()
                state, count = "completed", 0
                try:
                    if resource.plural not in apis.get(resource.api_version, set()):
                        state = "unsupported"
                    else:
                        budget = min(
                            limits.max_resources_per_type,
                            limits.max_topology_nodes - len(builder.nodes),
                        )
                        if resource.kind == "Event":
                            budget = min(budget, limits.max_events)
                        items, state = await self._collect(resource, namespace, context, budget)
                        for raw in items:
                            # Reject responses outside the requested namespace/type.
                            if (
                                raw.get("kind") != resource.kind
                                or raw.get("apiVersion") != resource.api_version
                                or not isinstance(raw.get("metadata", {}), dict)
                                or raw.get("metadata", {}).get("namespace") != namespace
                            ):
                                builder.warn("invalid_resource")
                                continue
                            builder.add(raw)
                        count = len(items)
                except AuthorizationError:
                    state = "forbidden"
                except ResourceNotFound:
                    state = "unsupported"
                except (DataSourceUnavailable, TimeoutError, SanitizationError):
                    state = "unavailable"
                if state != "completed":
                    code = {
                        "forbidden": "forbidden_resource",
                        "unsupported": "unsupported_api",
                        "truncated": "truncated_discovery",
                        "unavailable": "unavailable",
                    }[state]
                    warnings.append(
                        DiscoveryWarning(code=code, namespace=namespace, kind=resource.kind)
                    )
                categories.append(
                    CategoryResult(
                        namespace=namespace, kind=resource.kind, status=state, count=count
                    )
                )
                logging.getLogger("agt_mcp.audit").info(
                    json.dumps(
                        {
                            "event": "runtime_read",
                            "request_id": context.request_id,
                            "correlation_id": context.correlation_id,
                            "environment_id": self.environment.id,
                            "cluster": self.environment.cluster,
                            "namespace": namespace,
                            "operation": "list",
                            "kind": resource.kind,
                            "duration_ms": round((monotonic() - started) * 1000, 3),
                            "result": state,
                        }
                    )
                )
        topology = builder.build()
        return RuntimeSnapshot(
            environment_id=self.environment.id,
            cluster=self.environment.cluster,
            provider=self.settings.provider,
            observed_at=observed,
            namespaces=namespaces,
            capabilities=tuple(sorted(apis)),
            topology=topology,
            evidence=tuple(sorted(builder.evidence.values(), key=lambda e: (e.timestamp, e.id))),
            warnings=tuple(warnings + builder.warnings),
            unresolved=tuple(builder.unresolved),
            categories=tuple(categories),
        )

    async def events(self, context: ExecutionContext, query: RuntimeQuery) -> RuntimeEvents:
        namespaces = await self._prepare(context, query)
        resource = self._resolve_type(query)
        if not query.name or (resource.namespaced and len(namespaces) != 1):
            raise ConfigurationError()
        namespace = namespaces[0] if resource.namespaced else None
        raw = await self.client.read_resource(resource, namespace, query.name, context)
        self._validate_read(raw, resource, namespace, query.name)
        uid = raw.get("metadata", {}).get("uid")
        if not uid or not isinstance(uid, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,128}", uid):
            raise SanitizationError()
        event_type = next(t for t in TYPES if t.kind == "Event")
        raw_events: list[dict[str, Any]] = []
        limit = min(query.limit, self.settings.discovery.limits.max_events)
        truncated = len(namespaces) > self.settings.discovery.limits.max_namespaces
        for selected in namespaces[: self.settings.discovery.limits.max_namespaces]:
            remaining = limit - len(raw_events)
            if remaining <= 0:
                truncated = True
                break
            events, state = await self._collect(
                event_type, selected, context, remaining, f"involvedObject.uid={uid}"
            )
            truncated |= state == "truncated"
            for event in events:
                self._validate_read(
                    event, event_type, selected, event.get("metadata", {}).get("name", "")
                )
                if event.get("involvedObject", {}).get("uid") == uid:
                    raw_events.append(event)
        builder = GraphBuilder(
            self.environment.id,
            self.environment.cluster,
            datetime.now(UTC),
            self.settings.discovery.limits,
            [],
        )
        builder.add(raw)
        for event in raw_events:
            builder.add(event)
        for identifier, event in builder.raw.items():
            if event["kind"] == "Event":
                builder.observations(builder.nodes[identifier], event)
        evidence = tuple(
            sorted(
                (
                    e
                    for e in builder.evidence.values()
                    if e.raw_reference != e.resource_id
                    and (query.since is None or e.timestamp >= query.since)
                ),
                key=lambda e: (e.timestamp, e.id),
            )
        )[: query.limit]
        return RuntimeEvents(
            evidence=evidence,
            limit=limit,
            truncated=truncated or any(w.code == "truncated_discovery" for w in builder.warnings),
        )

    async def close(self) -> None:
        await self.client.close()
        self._open = False
