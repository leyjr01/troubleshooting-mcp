"""Composition bridges existing runtime, gateway and knowledge services to neutral ports."""

from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    DataSourceUnavailable,
    ResourceNotFound,
)
from agt_mcp.core.execution import ExecutionContext
from agt_mcp.core.models import Evidence, Resource
from agt_mcp.core.runtime import RuntimeQuery
from agt_mcp.correlation.models import (
    ComponentContext,
    CorrelatedKnowledge,
    CorrelationContext,
    CorrelationLink,
    CorrelationQuery,
    CorrelationSnapshot,
    CorrelationWarning,
    EvidenceAtom,
    HistoricalSimilarity,
    SignalCode,
)
from agt_mcp.correlation.rules import identity
from agt_mcp.gateways.threescale.models import GatewayQuery
from agt_mcp.knowledge.models import KnowledgeMetadata, SourceType
from agt_mcp.rag.contracts import RetrievalQuery
from agt_mcp.services.discovery import RuntimeDiscoveryService
from agt_mcp.services.gateway_discovery import GatewayDiscoveryService
from agt_mcp.services.knowledge import KnowledgeService
from agt_mcp.topology.models import Topology


def atom(item: Evidence, resource: Resource) -> EvidenceAtom:
    event = item.metadata.get("evidence_kind") == "event"
    state = "unknown"
    signals: list[SignalCode] = []
    if not event:
        if item.metadata.get("signal") == "no_ready_endpoints":
            state = "unavailable"
        elif resource.kind.value == "endpointslice":
            endpoints = resource.details.get("endpoints", [])
            if isinstance(endpoints, list):
                if not endpoints:
                    signals.append(SignalCode.ENDPOINTS_EMPTY)
                flags = [e.get("ready") for e in endpoints if isinstance(e, dict)]
                state = (
                    "ready"
                    if True in flags
                    else "unavailable"
                    if flags and all(v is False for v in flags)
                    else "unknown"
                )
        elif resource.kind.value == "pod":
            containers = resource.details.get("containers", [])
            if isinstance(containers, list):
                if any(
                    isinstance(c, dict) and c.get("waiting_reason") == "CrashLoopBackOff"
                    for c in containers
                ):
                    signals.append(SignalCode.CRASH_LOOP)
                flags = [c.get("ready") for c in containers if isinstance(c, dict)]
                state = (
                    "unavailable"
                    if False in flags
                    else "ready"
                    if flags and all(v is True for v in flags)
                    else "unknown"
                )
        elif resource.kind.value == "persistentvolumeclaim":
            if resource.status in {"Pending", "Lost"}:
                signals.append(SignalCode.PVC_NOT_BOUND)
            elif resource.status == "Bound":
                signals.append(SignalCode.PVC_BOUND)
        elif resource.kind.value == "deployment":
            unavailable, ready = (
                resource.details.get("unavailableReplicas"),
                resource.details.get("availableReplicas"),
            )
            state = (
                "unavailable"
                if isinstance(unavailable, int) and unavailable > 0
                else "ready"
                if isinstance(ready, int) and ready > 0
                else "unknown"
            )
    from typing import Literal, cast

    return EvidenceAtom(
        evidence=item,
        occurred_at=None
        if event and item.metadata.get("timestamp_origin") != "source"
        else item.timestamp,
        kind="event" if event else "status",
        state=cast(Literal["unavailable", "ready", "unknown"], state),
        origin=identity("origin", item.source.source_id, item.resource_id),
        signals=tuple(signals),
    )


class RuntimeCorrelationProvider:
    def __init__(self, runtime: RuntimeDiscoveryService, gateways: GatewayDiscoveryService) -> None:
        self.runtime, self.gateways = runtime, gateways

    async def collect(
        self, query: CorrelationQuery, context: ExecutionContext
    ) -> CorrelationSnapshot:
        adapters = self.gateways.adapters(context.environment_id)
        components: tuple[ComponentContext, ...] = ()
        links: tuple[CorrelationLink, ...] = ()
        installation = None
        if adapters:
            if query.gateway_id in {e.id for e in self.gateways.registry.entries()}:
                self.gateways.registry.resolve(query.gateway_id, context.environment_id)
            choices = {
                k: a
                for k, a in adapters.items()
                if (query.gateway_id not in adapters or k == query.gateway_id)
                and (query.namespace is None or a.settings.namespace in {None, query.namespace})
            }
            if len(choices) != 1:
                raise ConfigurationError()
            binding, adapter = next(iter(choices.items()))
            discovery = await adapter.discover_installations(
                context, GatewayQuery(namespace=query.namespace, limit=200)
            )
            snapshot = discovery.snapshot
            matched = [
                i
                for i in discovery.installations
                if (query.gateway_id in {None, binding, i.id})
                and (query.resource_id is None or query.resource_id in i.runtime_resources)
                and (
                    query.component_id is None or query.component_id in {c.id for c in i.components}
                )
            ]
            if len(matched) > 1:
                raise ConfigurationError()
            if not matched and (query.gateway_id or query.component_id):
                raise ResourceNotFound()
            installation = matched[0] if matched else None
            if installation:
                allowed = set(installation.runtime_resources)
                # Shared references must not bridge observations from different installations.
                foreign = {
                    r
                    for i in discovery.installations
                    if i.id != installation.id
                    for r in i.runtime_resources
                }
                allowed -= foreign
                components = tuple(
                    ComponentContext(
                        id=c.id,
                        installation_id=installation.id,
                        type=c.type.value,
                        resources=tuple(r for r in c.runtime_resources if r in allowed),
                        provenance=tuple(e.provenance for e in c.evidence),
                        expected=c.expected,
                        external=c.external,
                        presence=c.status.value,
                        dependencies=c.dependencies,
                    )
                    for c in installation.components
                )
                links = tuple(
                    CorrelationLink(
                        id=e.id,
                        source=e.source,
                        target=e.target,
                        relation=e.relationship.value,
                        provenance=e.provenance,
                    )
                    for e in installation.relationships
                    if e.source not in foreign and e.target not in foreign
                )
            else:
                allowed = {n.id for n in snapshot.topology.nodes} - {
                    r for i in discovery.installations for r in i.runtime_resources
                }
        else:
            if query.gateway_id or query.component_id:
                raise ResourceNotFound()
            runtime = self.runtime.adapters.get(context.environment_id)
            if runtime is None:
                raise ResourceNotFound()
            snapshot = await runtime.discover(
                context, RuntimeQuery(namespace=query.namespace, limit=200)
            )
            allowed = {n.id for n in snapshot.topology.nodes}
        if snapshot.environment_id != context.environment_id:
            raise AuthorizationError()
        resources = {n.id: n for n in snapshot.topology.nodes if n.id in allowed}
        if query.namespace and any(
            n.namespace not in {None, query.namespace} for n in resources.values()
        ):
            raise AuthorizationError()
        warnings = [
            CorrelationWarning(code=w.code, item_id=w.resource_id)
            for w in snapshot.warnings
            if w.resource_id is None or w.resource_id in allowed
        ]
        if installation and installation.partial:
            warnings.append(CorrelationWarning(code="partial_semantic_snapshot"))
        for unresolved in snapshot.unresolved:
            sources = [e.source for e in snapshot.evidence if e.resource_id == unresolved.source]
            if unresolved.source in allowed and sources:
                links += (
                    CorrelationLink(
                        id=identity("unresolved", unresolved.model_dump_json()),
                        source=unresolved.source,
                        target=identity("unobserved", unresolved.target.model_dump_json()),
                        relation="unresolved_" + unresolved.resolution,
                        provenance=sources[0],
                        target_kind=unresolved.target.kind,
                    ),
                )
        return CorrelationSnapshot(
            environment_id=snapshot.environment_id,
            observed_at=snapshot.observed_at,
            topology=Topology(
                environment_id=snapshot.environment_id,
                nodes=tuple(resources.values()),
                edges=tuple(
                    e
                    for e in snapshot.topology.edges
                    if e.source in allowed and e.target in allowed
                ),
            ),
            evidence=tuple(
                atom(e, resources[e.resource_id])
                for e in snapshot.evidence
                if e.resource_id in allowed
            ),
            components=components,
            links=links,
            warnings=tuple(warnings),
            installation_id=installation.id if installation else None,
            gateway_type="threescale" if installation else None,
            version=installation.version if installation else None,
            coverage=tuple(
                c
                for c in snapshot.categories
                if c.namespace in {n.namespace for n in resources.values()}
            ),
        )


class ReferenceBridge:
    def __init__(self, service: KnowledgeService, limit: int) -> None:
        self.service, self.limit = service, limit

    def text(self, context: CorrelationContext, snapshot: CorrelationSnapshot) -> str:
        return (
            " ".join(
                filter(
                    None,
                    (
                        context.request.symptom,
                        snapshot.gateway_type,
                        *(c.type for c in snapshot.components),
                        *(n.kind.value for n in snapshot.topology.nodes),
                        *(a.state for a in snapshot.evidence),
                    ),
                )
            )[:4096]
            or "runtime observations"
        )

    def check_index(self, context: ExecutionContext, history: bool) -> None:
        sources = [
            s
            for s in self.service.list_sources(context)
            if (s.source_type == SourceType.HISTORICAL_INCIDENT) == history
        ]
        if not sources or any(
            s.id not in self.service.manifests or s.id in self.service.failures for s in sources
        ):
            raise DataSourceUnavailable()


class KnowledgeBridge(ReferenceBridge):
    async def retrieve(
        self,
        context: CorrelationContext,
        snapshot: CorrelationSnapshot,
        execution: ExecutionContext,
    ) -> tuple[CorrelatedKnowledge, ...]:
        self.check_index(execution, False)
        query = RetrievalQuery(
            text=self.text(context, snapshot),
            limit=self.limit,
            source_types=tuple(
                s
                for s in SourceType
                if s not in {SourceType.HISTORICAL_INCIDENT, SourceType.OFFICIAL_DOCUMENTATION}
            ),
        )
        internal = await self.service.search(query, execution)
        known = snapshot.version not in {None, "UNKNOWN"}
        version = ".".join(snapshot.version.split(".")[:2]) if snapshot.version else None
        filters = (
            KnowledgeMetadata(product="3scale", product_version=version if known else None)
            if snapshot.gateway_type == "threescale"
            else None
        )
        official = await self.service.search(
            query.model_copy(
                update={"source_types": (SourceType.OFFICIAL_DOCUMENTATION,), "filters": filters}
            ),
            execution,
        )
        matches = sorted(
            (*official.results, *internal.results),
            key=lambda r: (
                r.chunk.source_type != SourceType.OFFICIAL_DOCUMENTATION,
                -r.relevance,
                r.chunk.id,
            ),
        )[: self.limit]
        return tuple(
            CorrelatedKnowledge(
                id=r.chunk.id,
                reference=r,
                version_compatible=(r.chunk.metadata.product_version == version) if known else None,
            )
            for r in matches
        )


class HistoryBridge(ReferenceBridge):
    async def retrieve(
        self,
        context: CorrelationContext,
        snapshot: CorrelationSnapshot,
        execution: ExecutionContext,
    ) -> tuple[HistoricalSimilarity, ...]:
        self.check_index(execution, True)
        result = await self.service.search(
            RetrievalQuery(
                text=self.text(context, snapshot),
                limit=self.limit,
                source_types=(SourceType.HISTORICAL_INCIDENT,),
            ),
            execution,
        )
        matches = []
        for reference in result.results:
            chunk = reference.chunk
            incident = next(
                (
                    d.incident
                    for d in self.service.documents.get(chunk.source.source_id, {}).values()
                    if d.id == chunk.document_id
                ),
                None,
            )
            matches.append(
                HistoricalSimilarity(
                    id=chunk.id,
                    reference=reference,
                    incident=incident,
                    similar_symptoms=incident.symptom if incident else chunk.text,
                    similar_components=tuple(
                        sorted(set(incident.components) & {c.type for c in snapshot.components})
                    )
                    if incident
                    else (),
                )
            )
        return tuple(matches)
