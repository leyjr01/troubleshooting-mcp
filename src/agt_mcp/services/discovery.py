"""Application discovery/inspection/topology services consume canonical runtime ports."""

from collections import Counter
from typing import cast

from pydantic import JsonValue

from agt_mcp.core.errors import ConfigurationError, ResourceNotFound, UnsupportedCapabilityError
from agt_mcp.core.execution import ExecutionContext, ToolName
from agt_mcp.core.runtime import RuntimeAdapter, RuntimeQuery, RuntimeSnapshot
from agt_mcp.topology.models import Topology


class TopologyService:
    @staticmethod
    def subgraph(
        snapshot: RuntimeSnapshot, root: str, query: RuntimeQuery
    ) -> tuple[Topology, bool]:
        selected = {root}
        frontier = {root}
        truncated = False
        for _ in range(query.depth):
            adjacent: set[str] = set()
            for edge in snapshot.topology.edges:
                if query.relationship and edge.relationship != query.relationship:
                    continue
                if edge.source in frontier and query.direction in {"both", "dependencies"}:
                    adjacent.add(edge.target)
                if edge.target in frontier and query.direction in {"both", "dependents"}:
                    adjacent.add(edge.source)
            fresh = sorted(adjacent - selected)
            remaining = max(0, query.limit - len(selected))
            if len(fresh) > remaining:
                truncated = True
            frontier = set(fresh[:remaining])
            selected.update(frontier)
        return Topology(
            environment_id=snapshot.environment_id,
            nodes=tuple(n for n in snapshot.topology.nodes if n.id in selected),
            edges=tuple(
                e
                for e in snapshot.topology.edges
                if e.source in selected
                and e.target in selected
                and (not query.relationship or e.relationship == query.relationship)
            ),
        ), truncated


class RuntimeDiscoveryService:
    def __init__(self, adapters: dict[str, RuntimeAdapter]) -> None:
        self.adapters = adapters.copy()

    async def execute(self, context: ExecutionContext, query: RuntimeQuery) -> dict[str, JsonValue]:
        adapter = self.adapters.get(context.environment_id)
        if adapter is None:
            raise UnsupportedCapabilityError()
        if context.operation == ToolName.DISCOVER_ENVIRONMENT:
            snapshot = await adapter.discover(context, query)
            counts = Counter(c.status for c in snapshot.categories)
            resources = Counter(
                n.reference.kind if n.reference else n.kind.value
                for n in snapshot.topology.nodes
                if (not query.kind or (n.reference and n.reference.kind == query.kind))
                and (not query.name or n.name == query.name)
                and (
                    not query.api_version
                    or (n.reference and n.reference.api_version == query.api_version)
                )
            )
            return {
                "environment_id": snapshot.environment_id,
                "cluster": snapshot.cluster,
                "provider": snapshot.provider,
                "observed_at": snapshot.observed_at.isoformat(),
                "status": "PARTIAL" if snapshot.warnings else "COMPLETE",
                "namespaces": list(snapshot.namespaces),
                "resource_counts": dict(resources),
                "capabilities": list(snapshot.capabilities),
                "connection_health": snapshot.connection_health().model_dump(mode="json"),
                "completeness": {
                    "requested": len(snapshot.categories),
                    **{str(k): v for k, v in counts.items()},
                },
                "warnings": [w.model_dump(mode="json") for w in snapshot.warnings[: query.limit]],
                "warnings_truncated": len(snapshot.warnings) > query.limit,
            }
        if not query.kind or not query.name:
            raise ConfigurationError()
        if context.operation == ToolName.INSPECT_EVENTS:
            events = await adapter.events(context, query)
            return {
                "evidence": [e.model_dump(mode="json") for e in events.evidence],
                "limit": events.limit,
                "bounded": True,
                "truncated": events.truncated,
                "ordering": "timestamp-ascending-within-collected-window",
            }
        snapshot = await adapter.inspect(context, query)
        roots = [
            node
            for node in snapshot.topology.nodes
            if node.reference
            and node.name == query.name
            and node.reference.kind == query.kind
            and (query.namespace is None or node.namespace == query.namespace)
            and (not query.api_version or node.reference.api_version == query.api_version)
        ]
        if len(roots) != 1:
            raise ResourceNotFound()
        root = roots[0]
        graph, truncated = TopologyService.subgraph(snapshot, root.id, query)
        result: dict[str, JsonValue] = {
            "topology": graph.model_dump(mode="json"),
            "truncated": truncated,
            "warnings": [w.model_dump(mode="json") for w in snapshot.warnings[: query.limit]],
            "unresolved": cast(
                JsonValue,
                [
                    r.model_dump(mode="json")
                    for r in snapshot.unresolved
                    if r.source in {n.id for n in graph.nodes}
                ][: query.limit],
            ),
            "discovery_status": "PARTIAL" if snapshot.warnings else "COMPLETE",
        }
        if context.operation == ToolName.INSPECT_RESOURCE:
            result["resource"] = root.model_dump(mode="json")
            result["evidence"] = cast(
                JsonValue,
                [e.model_dump(mode="json") for e in snapshot.evidence if e.resource_id == root.id][
                    : query.limit
                ],
            )
        if context.operation == ToolName.FIND_RELATED_RESOURCES:
            result["resources"] = [
                n.model_dump(mode="json") for n in graph.nodes if n.id != root.id
            ]
        return result

    async def close(self) -> None:
        from contextlib import AsyncExitStack

        async with AsyncExitStack() as stack:
            for adapter in self.adapters.values():
                stack.push_async_callback(adapter.close)
