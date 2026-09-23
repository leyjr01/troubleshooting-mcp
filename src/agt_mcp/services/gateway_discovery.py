"""Semantic queries over scoped gateway adapters, without raw infrastructure data."""

from typing import cast

from pydantic import JsonValue

from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    ResourceNotFound,
    UnsupportedCapabilityError,
)
from agt_mcp.core.execution import ExecutionContext, ToolName
from agt_mcp.gateways.base.adapter import GatewayAdapter
from agt_mcp.gateways.threescale.adapter import ThreeScaleGatewayAdapter
from agt_mcp.gateways.threescale.models import GatewayQuery
from agt_mcp.services.registry import AdapterRegistry


class GatewayDiscoveryService:
    def __init__(self, registry: AdapterRegistry[GatewayAdapter]) -> None:
        self.registry = registry

    def adapters(self, environment_id: str) -> dict[str, ThreeScaleGatewayAdapter]:
        return {
            e.id: e.adapter
            for e in self.registry.entries(environment_id)
            if isinstance(e.adapter, ThreeScaleGatewayAdapter)
        }

    async def execute(self, context: ExecutionContext, query: GatewayQuery) -> dict[str, JsonValue]:
        adapters = self.adapters(context.environment_id)
        if not adapters:
            raise UnsupportedCapabilityError()
        if query.gateway_id in {entry.id for entry in self.registry.entries()}:
            self.registry.resolve(query.gateway_id, context.environment_id)
        if query.namespace and all(
            a.settings.namespace not in {None, query.namespace} for a in adapters.values()
        ):
            raise AuthorizationError()
        binding_ids = set(adapters)
        if query.gateway_id in adapters:
            adapters = {query.gateway_id: adapters[query.gateway_id]}
        records = {}
        snapshots = {}
        policies = {}
        for adapter in adapters.values():
            if query.namespace and adapter.settings.namespace not in {None, query.namespace}:
                continue
            result = await adapter.discover_installations(context, query)
            for installation in result.installations:
                if (
                    query.gateway_id
                    and query.gateway_id not in binding_ids
                    and installation.id != query.gateway_id
                ):
                    continue
                records[installation.id] = installation
                snapshots[installation.id] = result.snapshot
                policies[installation.id] = adapter.settings
        ordered = sorted(records.values(), key=lambda i: i.id)
        if context.operation == ToolName.DISCOVER_GATEWAY:
            return {
                "installations": [
                    {
                        "id": i.id,
                        "environment_id": i.environment_id,
                        "namespace": i.namespace,
                        "version": i.version,
                        "version_profile": i.version_profile,
                        "configuration_summary": i.configuration_summary,
                        "operator_managed": i.operator_managed,
                        "operator_observation": i.operator_observation,
                        "observed_at": i.observed_at.isoformat(),
                        "partial": i.partial,
                        "components": [
                            {
                                "id": c.id,
                                "type": c.type.value,
                                "status": c.status.value,
                                "expected": c.expected,
                                "external": c.external,
                            }
                            for c in i.components
                        ],
                        "warnings": [w.model_dump(mode="json") for w in i.warnings[: query.limit]],
                        "evidence_count": sum(len(c.evidence) for c in i.components),
                        "capabilities": [
                            "gateway.discovery",
                            "gateway.components.read",
                            "gateway.topology.read",
                            *(
                                ["gateway.dependencies.read"]
                                if policies[i.id].include_dependencies
                                else []
                            ),
                        ],
                    }
                    for i in ordered[: query.limit]
                ],
                "truncated": len(ordered) > query.limit,
            }
        if not query.gateway_id:
            raise ConfigurationError()
        if len(ordered) != 1:
            raise ResourceNotFound() if not ordered else ConfigurationError()
        installation = ordered[0]
        snapshot = snapshots[installation.id]
        policy = policies[installation.id]
        runtime = {
            n.id: n for n in snapshot.topology.nodes if n.id in installation.runtime_resources
        }
        common: dict[str, JsonValue] = {
            "gateway_id": installation.id,
            "observed_at": installation.observed_at.isoformat(),
            "partial": installation.partial,
            "evidence": [e.model_dump(mode="json") for e in installation.evidence],
            "warnings": [w.model_dump(mode="json") for w in installation.warnings[: query.limit]],
        }
        if context.operation == ToolName.INSPECT_GATEWAY_COMPONENT:
            component = next(
                (c for c in installation.components if c.id == query.component_id), None
            )
            if component is None:
                raise ResourceNotFound()
            common["component"] = component.model_dump(mode="json")
            common["runtime_resources"] = (
                [
                    runtime[r].model_dump(mode="json")
                    for r in component.runtime_resources[: query.limit]
                ]
                if policy.include_runtime_resources
                else []
            )
            common["truncated"] = len(component.runtime_resources) > query.limit
            common["runtime_evidence"] = cast(
                JsonValue,
                [
                    e.model_dump(mode="json")
                    for e in installation.runtime_evidence
                    if e.resource_id in component.runtime_resources
                ][: query.limit],
            )
            return common
        if context.operation == ToolName.GET_GATEWAY_DEPENDENCIES:
            if not policy.include_dependencies:
                raise UnsupportedCapabilityError()
            relevant = [
                n
                for n in runtime.values()
                if n.reference
                and n.reference.kind
                in {"Service", "Route", "Ingress", "Secret", "ConfigMap", "PersistentVolumeClaim"}
            ]
            common["external_dependencies"] = [
                d.model_dump(mode="json") for d in installation.dependencies[: query.limit]
            ]
            common["runtime_references"] = [
                n.model_dump(mode="json") for n in relevant[: query.limit]
            ]
            common["truncated"] = (
                len(relevant) > query.limit or len(installation.dependencies) > query.limit
            )
            return common
        components = list(installation.components)[: max(0, query.limit - 1)]
        ids = {installation.id, *(c.id for c in components)}
        chosen = []
        if query.depth >= 2 and policy.include_runtime_resources:
            candidates = sorted({r for c in components for r in c.runtime_resources})
            chosen = [runtime[r] for r in candidates[: max(0, query.limit - len(ids))]]
            ids.update(n.id for n in chosen)
        common.update(
            {
                "installation": {
                    "id": installation.id,
                    "type": "threescale-installation",
                    "namespace": installation.namespace,
                    "version": installation.version,
                },
                "semantic_nodes": [c.model_dump(mode="json") for c in components],
                "runtime_nodes": [n.model_dump(mode="json") for n in chosen],
                "relationships": [
                    e.model_dump(mode="json")
                    for e in installation.relationships
                    if e.source in ids and e.target in ids
                ],
                "runtime_relationships": [
                    e.model_dump(mode="json")
                    for e in snapshot.topology.edges
                    if e.source in ids and e.target in ids
                ],
                "external_dependencies": [
                    d.model_dump(mode="json") for d in installation.dependencies if d.id in ids
                ]
                if policy.include_dependencies
                else [],
                "unresolved": cast(
                    JsonValue,
                    [r.model_dump(mode="json") for r in snapshot.unresolved if r.source in ids][
                        : query.limit
                    ],
                ),
                "truncated": len(components) < len(installation.components)
                or (
                    query.depth >= 2
                    and policy.include_runtime_resources
                    and len(chosen) < len(runtime)
                ),
            }
        )
        return common
