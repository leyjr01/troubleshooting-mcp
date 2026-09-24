"""Gateway-neutral correlation of bounded canonical snapshots and optional references."""

import asyncio
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from pydantic import JsonValue

from agt_mcp.configuration.correlation import CorrelationConfig
from agt_mcp.core.errors import (
    AuthorizationError,
    ConfigurationError,
    ResourceNotFound,
    SanitizationError,
)
from agt_mcp.core.execution import ExecutionContext
from agt_mcp.core.models import Confidence, ConfidenceLevel, Provenance
from agt_mcp.correlation.models import (
    CorrelatedKnowledge,
    CorrelationCandidate,
    CorrelationContext,
    CorrelationLink,
    CorrelationQuery,
    CorrelationResult,
    CorrelationSnapshot,
    CorrelationWarning,
    EvidenceAtom,
    EvidenceSet,
    HistoricalSimilarity,
    ObservedState,
    RelationType,
    TimelineItem,
    TimeWindow,
)
from agt_mcp.correlation.ports import (
    Clock,
    EvidenceTopologyProvider,
    HistoricalIncidentProvider,
    KnowledgeCorrelationProvider,
)
from agt_mcp.correlation.rules import RULES, CorrelationRule, RuleContext, candidate, identity
from agt_mcp.knowledge.security import KnowledgeRedactor
from agt_mcp.topology.models import Topology


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


class EvidenceCorrelationEngine:
    def __init__(
        self,
        provider: EvidenceTopologyProvider,
        knowledge: KnowledgeCorrelationProvider,
        history: HistoricalIncidentProvider,
        config: CorrelationConfig,
        clock: Clock | None = None,
        rules: tuple[CorrelationRule, ...] = RULES,
    ) -> None:
        self.provider, self.knowledge, self.history = provider, knowledge, history
        self.config, self.clock, self.rules = config, clock or SystemClock(), rules
        self.redactor = KnowledgeRedactor()

    def check_provenance(self, source: Provenance) -> None:
        reference = source.source_reference
        # Canonical provenance contains content hashes and long public documentation paths.
        # Keep them intact, while rejecting explicit credential patterns and URL credentials.
        if self.redactor.redact(reference, opaque_values=False) != reference:
            raise SanitizationError()

    def clean_confidence(self, confidence: Confidence) -> Confidence:
        return confidence.model_copy(
            update={
                key: self.redactor.redact(value)
                for key, value in confidence.model_dump().items()
                if isinstance(value, str) and key != "level"
            }
        )

    def check_reference_fields(self, value: JsonValue) -> None:
        if isinstance(value, str):
            if self.redactor.redact(value, opaque_values=False) != value:
                raise SanitizationError()
        elif isinstance(value, dict):
            for item in value.values():
                self.check_reference_fields(item)
        elif isinstance(value, list):
            for item in value:
                self.check_reference_fields(item)

    def context(self, query: CorrelationQuery, execution: ExecutionContext) -> CorrelationContext:
        now = self.clock.now()
        window = query.time_window or TimeWindow(
            start=now - timedelta(seconds=self.config.default_lookback_seconds), end=now
        )
        if (
            (window.end - window.start).total_seconds() > self.config.max_lookback_seconds
            or window.start < now - timedelta(seconds=self.config.max_lookback_seconds)
            or window.end > now + timedelta(seconds=self.config.future_skew_seconds)
            or query.topology_depth > self.config.max_topology_depth
        ):
            raise ConfigurationError()
        clean = query.model_copy(
            update={"symptom": self.redactor.redact(query.symptom) if query.symptom else None}
        )
        return CorrelationContext(
            environment_id=execution.environment_id,
            subject=query.resource_id or query.component_id or query.gateway_id or "unknown",
            request=clean,
            time_window=window,
            correlated_at=now,
        )

    def scope(self, snapshot: CorrelationSnapshot, context: CorrelationContext) -> dict[str, int]:
        env = context.environment_id
        if snapshot.environment_id != env or snapshot.topology.environment_id != env:
            raise AuthorizationError()
        for node in snapshot.topology.nodes:
            if node.environment_id != env:
                raise AuthorizationError()
            if context.request.namespace and node.namespace not in {
                None,
                context.request.namespace,
            }:
                raise AuthorizationError()
        if any(c.installation_id != snapshot.installation_id for c in snapshot.components):
            raise AuthorizationError()
        for atom in snapshot.evidence:
            if atom.evidence.environment_id != env or atom.evidence.source.environment_id != env:
                raise AuthorizationError()
            self.check_provenance(atom.evidence.source)
        for source in [
            *(e.source_of_information for e in snapshot.topology.edges),
            *(e.provenance for e in snapshot.links),
            *(p for c in snapshot.components for p in c.provenance),
        ]:
            if source.environment_id != env:
                raise AuthorizationError()
            self.check_provenance(source)
        nodes = {n.id for n in snapshot.topology.nodes}
        query = context.request
        if query.component_id:
            components = [c for c in snapshot.components if c.id == query.component_id]
            if not components:
                raise ResourceNotFound()
            roots = set(components[0].resources) & nodes
        elif query.resource_id:
            roots = {query.resource_id} & nodes
        else:
            roots = nodes
        if query.resource_id and query.resource_id not in roots:
            raise ResourceNotFound()
        if not roots and not query.component_id:
            raise ResourceNotFound()
        distances = dict.fromkeys(sorted(roots)[: self.config.max_resources], 0)
        for depth in range(1, query.topology_depth + 1):
            adjacent = {
                v
                for e in snapshot.topology.edges
                for u, v in ((e.source, e.target), (e.target, e.source))
                if u in distances and v not in distances
            }
            for key in sorted(adjacent)[: max(0, self.config.max_resources - len(distances))]:
                distances[key] = depth
        return distances

    def evidence(
        self,
        snapshot: CorrelationSnapshot,
        context: CorrelationContext,
        distances: dict[str, int],
        warnings: list[CorrelationWarning],
    ) -> tuple[tuple[EvidenceAtom, ...], tuple[EvidenceAtom, ...]]:
        unique: dict[str, EvidenceAtom] = {}
        ids: dict[str, str] = {}
        for atom in sorted(snapshot.evidence, key=lambda a: a.evidence.id):
            item = atom.evidence
            if item.resource_id not in distances:
                continue
            key = identity(
                "fact",
                item.resource_id,
                item.source.model_dump_json(),
                item.observation,
                str(atom.occurred_at),
                atom.kind,
                atom.state,
            )
            if item.id in ids and ids[item.id] != key:
                raise ConfigurationError()
            ids[item.id] = key
            clean = item.model_copy(
                update={
                    "observation": self.redactor.redact(item.observation),
                    "raw_reference": item.source.source_reference,
                    "metadata": {},
                    "confidence": self.clean_confidence(item.confidence),
                }
            )
            unique.setdefault(key, atom.model_copy(update={"evidence": clean}))
        ordered = sorted(
            unique.values(),
            key=lambda a: (
                a.occurred_at is None,
                a.occurred_at or context.correlated_at,
                a.evidence.id,
            ),
        )
        if len(ordered) > self.config.max_events:
            warnings.append(CorrelationWarning(code="evidence_truncated"))
            ordered.sort(
                key=lambda a: (
                    not (
                        a.occurred_at is not None
                        and context.time_window.start <= a.occurred_at <= context.time_window.end
                    ),
                    distances[a.evidence.resource_id],
                    a.evidence.id,
                )
            )
        ordered = sorted(
            ordered[: self.config.max_events],
            key=lambda a: (
                a.occurred_at is None,
                a.occurred_at or context.correlated_at,
                a.evidence.id,
            ),
        )
        fresh = []
        for atom in ordered:
            stamp = atom.occurred_at
            code = (
                "missing_timestamp"
                if stamp is None
                else "future_timestamp"
                if stamp
                > context.correlated_at + timedelta(seconds=self.config.future_skew_seconds)
                else "stale_evidence"
                if stamp < context.time_window.start or stamp > context.time_window.end
                else None
            )
            if code:
                warnings.append(CorrelationWarning(code=code, item_id=atom.evidence.id))
            else:
                fresh.append(atom)
        return tuple(ordered), tuple(fresh)

    async def correlate(
        self, query: CorrelationQuery, execution: ExecutionContext
    ) -> CorrelationResult:
        context = self.context(query, execution)
        snapshot = await self.provider.collect(context.request, execution)
        # Default windows end after collection so observation timestamps are not future events.
        context = self.context(context.request, execution)
        distances = self.scope(snapshot, context)
        warnings = list(snapshot.warnings)
        if len(distances) >= self.config.max_resources:
            warnings.append(CorrelationWarning(code="topology_limit_reached"))
        all_atoms, fresh = self.evidence(snapshot, context, distances, warnings)
        topology = Topology(
            environment_id=context.environment_id,
            nodes=tuple(
                n.model_copy(
                    update={
                        "labels": {},
                        "annotations": {},
                        "details": {},
                        "metadata": {},
                        "name": n.id,
                        "status": "observed",
                    }
                )
                for n in sorted(snapshot.topology.nodes, key=lambda n: n.id)
                if n.id in distances
            ),
            edges=tuple(
                e.model_copy(
                    update={"metadata": {}, "confidence": self.clean_confidence(e.confidence)}
                )
                for e in sorted(snapshot.topology.edges, key=lambda e: e.id)
                if e.source in distances and e.target in distances
            ),
        )
        links = tuple(
            CorrelationLink(
                id=e.id,
                source=e.source,
                target=e.target,
                relation=e.relationship.value,
                provenance=e.source_of_information,
            )
            for e in topology.edges
        )
        semantic = tuple(
            e
            for e in sorted(snapshot.links, key=lambda e: e.id)
            if e.source in distances or e.target in distances
        )
        components = tuple(
            c
            for c in sorted(snapshot.components, key=lambda c: c.id)
            if set(c.resources) & distances.keys() or c.id == context.request.component_id
        )
        snapshot_current = (
            context.time_window.start <= snapshot.observed_at <= context.time_window.end
        )
        if not snapshot_current:
            warnings.append(CorrelationWarning(code="snapshot_outside_window"))
        data = RuleContext(
            context,
            fresh,
            distances,
            components,
            (*links, *semantic) if snapshot_current else (),
            self.config.temporal_proximity_seconds,
        )
        candidates = [c for rule in self.rules for c in rule(data)]
        enrichment_snapshot = snapshot.model_copy(
            update={
                "topology": topology,
                "evidence": all_atoms,
                "components": components,
                "links": semantic,
            }
        )
        knowledge: tuple[CorrelatedKnowledge, ...] = ()
        history: tuple[HistoricalSimilarity, ...] = ()
        if context.request.include_knowledge:
            if snapshot.gateway_type and snapshot.version in {None, "UNKNOWN"}:
                warnings.append(CorrelationWarning(code="version_compatibility_unconfirmed"))
            try:
                async with asyncio.timeout(self.config.enrichment_timeout_seconds):
                    knowledge = await self.knowledge.retrieve(
                        context, enrichment_snapshot, execution
                    )
            except AuthorizationError:
                raise
            except Exception:
                warnings.append(CorrelationWarning(code="knowledge_unavailable"))
        if context.request.include_history:
            try:
                async with asyncio.timeout(self.config.enrichment_timeout_seconds):
                    history = await self.history.retrieve(context, enrichment_snapshot, execution)
            except AuthorizationError:
                raise
            except Exception:
                warnings.append(CorrelationWarning(code="history_unavailable"))
        knowledge = tuple(sorted(knowledge, key=lambda k: k.id))[
            : self.config.max_knowledge_results
        ]
        history = tuple(sorted(history, key=lambda h: h.id))[: self.config.max_knowledge_results]
        references: tuple[CorrelatedKnowledge | HistoricalSimilarity, ...] = (*knowledge, *history)
        for item in references:
            self.check_reference_fields(item.model_dump(mode="json"))
            chunk = item.reference.chunk
            if (
                chunk.environment_id not in {context.environment_id, "global"}
                or chunk.source.environment_id != chunk.environment_id
            ):
                raise AuthorizationError()
            if self.redactor.redact(chunk.text) != chunk.text:
                raise SanitizationError()
            self.check_provenance(chunk.source)
            historical = isinstance(item, HistoricalSimilarity)
            if (
                isinstance(item, HistoricalSimilarity)
                and item.incident
                and (
                    item.incident.environment_id not in {context.environment_id, "global"}
                    or item.incident.source.environment_id != item.incident.environment_id
                )
            ):
                raise AuthorizationError()
            if isinstance(item, HistoricalSimilarity) and item.incident:
                for value in (
                    item.incident.symptom,
                    item.incident.historical_root_cause,
                    item.incident.historical_remediation,
                    item.similar_symptoms,
                ):
                    if value and self.redactor.redact(value) != value:
                        raise SanitizationError()
            c = candidate(
                data,
                RelationType.HISTORICAL_SIMILARITY if historical else RelationType.KNOWLEDGE,
                "historical-reference" if historical else "knowledge-reference",
                reason="reference only; not runtime supporting evidence",
            )
            candidates.append(
                c.model_copy(
                    update={
                        "id": identity("candidate", c.id, item.id),
                        "source_items": (item.id,),
                        "historical_refs": (item.id,) if historical else (),
                        "knowledge_refs": () if historical else (item.id,),
                        "provenance": (chunk.source,),
                        "confidence": c.confidence.model_copy(
                            update={"level": ConfidenceLevel.LOW}
                        ),
                    }
                )
            )
            if (
                isinstance(item, CorrelatedKnowledge)
                and item.version_compatible is not True
                and chunk.source_type.value == "OFFICIAL_DOCUMENTATION"
            ):
                warnings.append(
                    CorrelationWarning(code="version_compatibility_unconfirmed", item_id=item.id)
                )
        # Reserve contradicted candidates first, then interleave relation types.
        groups: dict[str, list[CorrelationCandidate]] = defaultdict(list)
        for c in sorted({c.id: c for c in candidates}.values(), key=lambda c: c.id):
            groups["0" if c.contradicting_evidence else c.relation_type].append(c)
        candidates = list(groups.pop("0", []))
        while any(groups.values()):
            for key in sorted(groups):
                if groups[key]:
                    candidates.append(groups[key].pop(0))
        if len(candidates) > self.config.max_candidates:
            warnings.append(CorrelationWarning(code="candidates_truncated"))
        candidates = candidates[: self.config.max_candidates]
        provenance = tuple(
            {e.evidence.source.model_dump_json(): e.evidence.source for e in all_atoms}.values()
        )
        evidence_set = EvidenceSet(
            id=identity("set", context.subject, *sorted(a.evidence.id for a in all_atoms)),
            subject=context.subject,
            environment_id=context.environment_id,
            time_window=context.time_window,
            evidence=tuple(a.evidence for a in all_atoms),
            resources=tuple(sorted(distances)),
            components=tuple(sorted(c.id for c in components)),
            provenance=provenance,
            knowledge_refs=tuple(k.id for k in knowledge),
            historical_refs=tuple(h.id for h in history),
        )
        timeline = tuple(
            TimelineItem(
                evidence_id=a.evidence.id,
                timestamp=a.occurred_at,
                resource_id=a.evidence.resource_id,
                components=tuple(
                    sorted(c.id for c in components if a.evidence.resource_id in c.resources)
                ),
                event_type=a.kind,
                observation=a.evidence.observation,
                provenance=a.evidence.source,
                relevant=a in fresh,
            )
            for a in all_atoms
        )
        result = CorrelationResult(
            id="pending",
            context=context,
            status="PARTIAL" if warnings else "COMPLETE",
            evidence_sets=(evidence_set,),
            candidates=tuple(candidates),
            timeline=timeline,
            knowledge=knowledge,
            historical_matches=history,
            topology_context=topology,
            semantic_links=semantic,
            warnings=tuple(
                CorrelationWarning(code=c, item_id=i)
                for c, i in sorted(
                    {(w.code, w.item_id) for w in warnings}, key=lambda w: (w[0], w[1] or "")
                )
            ),
            provenance=provenance,
            observed_states=tuple(
                ObservedState(
                    evidence_id=a.evidence.id, state=a.state, origin=a.origin, signals=a.signals
                )
                for a in all_atoms
            ),
            component_context=tuple(
                c.model_copy(update={"resources": tuple(r for r in c.resources if r in distances)})
                for c in components
            ),
            installation_id=snapshot.installation_id,
            gateway_type=snapshot.gateway_type,
            version=snapshot.version,
            coverage=snapshot.coverage,
        )
        return result.model_copy(update={"id": identity("correlation", result.model_dump_json())})
