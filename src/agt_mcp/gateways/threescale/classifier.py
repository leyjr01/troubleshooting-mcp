"""Evidence-backed semantic classification of one bounded canonical snapshot."""

import hashlib
import json
from typing import Any

from agt_mcp.core.models import Confidence, ConfidenceLevel, Provenance, Resource
from agt_mcp.core.runtime import RuntimeSnapshot
from agt_mcp.gateways.threescale.models import (
    Component,
    DetectionEvidence,
    ExternalDependency,
    Installation,
    Presence,
    SemanticEdge,
    SemanticWarning,
)
from agt_mcp.gateways.threescale.models import (
    ComponentType as C,
)
from agt_mcp.gateways.threescale.models import (
    SemanticRelation as R,
)
from agt_mcp.gateways.threescale.profiles import (
    CORE_COMPONENTS,
    PATTERNS,
    SECRET_BINDINGS,
    ZYNC_COMPONENTS,
    profile_for,
)
from agt_mcp.topology.models import Relationship


def stable_id(prefix: str, *values: object) -> str:
    return (
        prefix
        + ":"
        + hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()[:40]
    )


def confidence(level: ConfidenceLevel, signal: str) -> Confidence:
    return Confidence(
        level=level,
        rationale=f"Classification via {signal}; no causal diagnosis",
        source_reliability="Declared runtime structure; metadata alone can be spoofed",
        temporal_relevance="Single bounded runtime snapshot",
        topological_relevance="Environment and installation scoped",
        historical_similarity="Not used",
    )


def hints(resource: Resource) -> dict[str, Any]:
    value = resource.details.get("discovery_hints", {})
    return value if isinstance(value, dict) else {}


class ThreeScaleComponentClassifier:
    def __init__(
        self,
        snapshot: RuntimeSnapshot,
        *,
        version_profile: str = "auto",
        max_edges: int = 1000,
        max_components: int = 200,
    ) -> None:
        self.snapshot = snapshot
        self.profile_override = version_profile
        self.max_edges, self.max_components = max_edges, max_components
        self.nodes = {n.id: n for n in snapshot.topology.nodes}
        self.edges = tuple(sorted(snapshot.topology.edges, key=lambda e: e.id))
        self.ownership: dict[str, set[str]] = {}
        for edge in self.edges:
            if edge.relationship == Relationship.OWNS:
                self.ownership.setdefault(edge.source, set()).add(edge.target)

    def evidence(
        self, resource: Resource, signal: str, level: ConfidenceLevel
    ) -> DetectionEvidence:
        identifier = stable_id("detection", resource.id, signal)
        provenance = Provenance(
            source_id="runtime-semantic-projection",
            environment_id=self.snapshot.environment_id,
            retrieved_at=self.snapshot.observed_at,
            source_reference=resource.id,
            content_sha256=hashlib.sha256(f"{resource.id}:{signal}".encode()).hexdigest(),
        )
        return DetectionEvidence(
            id=identifier,
            resource_id=resource.id,
            signal=signal,
            observation=f"Observed classification signal: {signal}",
            provenance=provenance,
            confidence=confidence(level, signal),
        )

    def descendants(self, root: str) -> set[str]:
        found = {root}
        pending = [root]
        while pending:
            fresh = self.ownership.get(pending.pop(), set()) - found
            found.update(fresh)
            pending.extend(sorted(fresh))
        return found

    def classify(self) -> tuple[Installation, ...]:
        roots = [
            n
            for n in self.nodes.values()
            if n.reference
            and n.reference.kind == "APIManager"
            and n.reference.api_version == "apps.3scale.net/v1alpha1"
        ]
        result = [self.installation(root, roots) for root in sorted(roots, key=lambda n: n.id)]
        # Without an APIManager, keep only corroborated namespace-level candidates.
        occupied = {r.namespace for r in roots}
        for namespace in sorted(self.snapshot.namespaces):
            if namespace in occupied:
                continue
            candidates = [
                n
                for n in self.nodes.values()
                if n.namespace == namespace
                and hints(n).get("product_label")
                and hints(n).get("component_labels")
                and n.reference
                and n.reference.kind in {"Deployment", "StatefulSet", "DaemonSet"}
            ]
            if candidates:
                result.append(
                    self.installation(sorted(candidates, key=lambda n: n.id)[0], [], candidate=True)
                )
        return tuple(sorted(result, key=lambda i: i.id))

    def installation(
        self, root: Resource, roots: list[Resource], candidate: bool = False
    ) -> Installation:
        installation_id = stable_id(
            "threescale",
            self.snapshot.environment_id,
            root.namespace,
            root.id if not candidate else "unverified",
        )
        same_namespace = [r for r in roots if r.namespace == root.namespace]
        owned = self.descendants(root.id) if not candidate else set()
        foreign = set().union(*(self.descendants(r.id) for r in same_namespace if r.id != root.id))
        scoped = {
            k: n
            for k, n in self.nodes.items()
            if n.namespace == root.namespace and k not in foreign
        }
        warnings: list[SemanticWarning] = []
        ev_root = self.evidence(
            root,
            "metadata-candidate" if candidate else "apimanager-declaration",
            ConfidenceLevel.MEDIUM if candidate else ConfidenceLevel.HIGH,
        )
        if candidate or len(same_namespace) > 1:
            warnings.append(SemanticWarning(code="ambiguous_classification", resource_id=root.id))
        version = hints(root).get("version_label", "UNKNOWN")
        version_signal = "version-label"
        version_source = root
        if version == "UNKNOWN":
            versions = {hints(scoped[n]).get("version_label") for n in owned if n in scoped}
            versions.discard(None)
            if len(versions) == 1:
                version = versions.pop()
                version_signal = "owned-resource-version-label"
                version_source = next(
                    scoped[n]
                    for n in sorted(owned)
                    if n in scoped and hints(scoped[n]).get("version_label") == version
                )
        profile = profile_for(version if self.profile_override == "auto" else self.profile_override)
        if version == "UNKNOWN":
            warnings.append(SemanticWarning(code="version_unknown", resource_id=root.id))
        elif profile_for(version) is None:
            warnings.append(
                SemanticWarning(code="unsupported_version_profile", resource_id=root.id)
            )
        evidence = [ev_root]
        if version != "UNKNOWN":
            evidence.append(self.evidence(version_source, version_signal, ConfidenceLevel.MEDIUM))
        seeds: dict[C, set[str]] = {}
        detections: dict[C, list[DetectionEvidence]] = {}
        if not candidate:
            seeds[C.APIMANAGER] = {root.id}
            detections[C.APIMANAGER] = [ev_root]
        for node in sorted(scoped.values(), key=lambda n: n.id):
            if not node.reference or node.reference.kind not in {
                "Deployment",
                "StatefulSet",
                "DaemonSet",
            }:
                continue
            hint = hints(node)
            roles = {PATTERNS[v] for v in hint.get("component_labels", []) if v in PATTERNS}
            belongs = node.id in owned
            label_candidate = hint.get("product_label") and len(same_namespace) <= 1
            if not belongs and not label_candidate:
                continue
            if not roles and belongs and node.name in PATTERNS:
                roles = {PATTERNS[node.name]}
                signal = "owner-reference-and-documented-name"
            else:
                signal = (
                    "owner-reference-and-component-label"
                    if belongs
                    else "product-and-component-label"
                )
            if len(roles) != 1:
                if not belongs and not roles:
                    continue
                kind = C.UNKNOWN
                warnings.append(
                    SemanticWarning(code="ambiguous_classification", resource_id=node.id)
                )
            else:
                kind = next(iter(roles))
            level = (
                ConfidenceLevel.HIGH
                if belongs and hint.get("component_labels") and kind != C.UNKNOWN
                else ConfidenceLevel.MEDIUM
            )
            seeds.setdefault(kind, set()).add(node.id)
            detections.setdefault(kind, []).append(self.evidence(node, signal, level))

        all_seeds = set().union(*seeds.values()) if seeds else set()
        memberships: dict[C, set[str]] = {}
        for kind, initial in seeds.items():
            selected = set(initial)
            if kind != C.APIMANAGER:
                for _ in range(len(scoped)):
                    expanded = set(selected)
                    for edge in self.edges:
                        if edge.source not in scoped or edge.target not in scoped:
                            continue
                        if edge.source in selected and edge.relationship in {
                            Relationship.OWNS,
                            Relationship.REFERENCES_SECRET,
                            Relationship.REFERENCES_CONFIGMAP,
                            Relationship.MOUNTS,
                            Relationship.HAS_ENDPOINTSLICE,
                        }:
                            expanded.add(edge.target)
                        if (
                            edge.target in selected
                            and edge.relationship
                            in {
                                Relationship.SELECTS,
                                Relationship.TARGETS,
                                Relationship.ROUTES_TO,
                                Relationship.HAS_ENDPOINTSLICE,
                                Relationship.HAS_ENDPOINT,
                            }
                            and scoped[edge.source].reference
                            and (source_ref := scoped[edge.source].reference) is not None
                            and source_ref.kind in {"Service", "Route", "Ingress", "EndpointSlice"}
                        ):
                            expanded.add(edge.source)
                    expanded -= all_seeds - initial
                    expanded.discard(root.id)
                    if expanded <= selected:
                        break
                    selected.update(expanded)
            memberships[kind] = selected

        namespace_categories = [
            c for c in self.snapshot.categories if c.namespace == root.namespace
        ]
        partial = any(c.status != "completed" for c in namespace_categories)
        namespace_warnings = [
            w for w in self.snapshot.warnings if w.namespace in {None, root.namespace}
        ]
        if partial or namespace_warnings:
            warnings.append(SemanticWarning(code="partial_topology"))
        if any(c.status == "forbidden" for c in namespace_categories):
            warnings.append(SemanticWarning(code="runtime_resource_forbidden"))
        complete_workloads = any(
            c.kind == "Deployment" and c.status == "completed" for c in namespace_categories
        )
        configuration = hints(root) if not candidate else {}
        zync_enabled = configuration.get("zync_enabled")
        external_config = configuration.get("external_components", {})
        components: list[Component] = []
        dependencies: list[ExternalDependency] = []
        edges: dict[str, SemanticEdge] = {}

        def add_edge(
            source: str, target: str, relation: R, mechanism: str, ev: DetectionEvidence
        ) -> None:
            key = stable_id("semantic-edge", source, target, relation)
            if len(edges) >= self.max_edges:
                warnings.append(SemanticWarning(code="partial_topology"))
                return
            edges[key] = SemanticEdge(
                id=key,
                source=source,
                target=target,
                relationship=relation,
                mechanism=mechanism,
                provenance=ev.provenance,
                confidence=ev.confidence,
            )

        kinds = set(seeds)
        if not candidate:
            kinds.update(CORE_COMPONENTS)
            kinds.update(ZYNC_COMPONENTS)
            kinds.update(SECRET_BINDINGS)
            kinds.add(C.SYSTEM_MEMCACHE)
        for kind in sorted(kinds):
            ids = memberships.get(kind, set())
            cid = stable_id("component", installation_id, kind)
            expected = bool(profile and kind in profile.expected_components)
            if kind in ZYNC_COMPONENTS:
                expected = zync_enabled is True
            status = Presence.PRESENT if ids else Presence.UNKNOWN
            external = False
            signals = list(detections.get(kind, []))
            binding = SECRET_BINDINGS.get(kind)
            declaration = None
            if binding:
                declaration = external_config.get(binding[0], {}).get(binding[1])
                external = declaration is True or bool(
                    profile
                    and kind in profile.externally_managed_components
                    and declaration is not False
                )
            if kind in ZYNC_COMPONENTS and zync_enabled is False and not ids:
                status = Presence.DISABLED
                expected = False
                external = False
            elif external:
                status = Presence.EXTERNAL
                expected = True
            elif not ids and (profile or zync_enabled is not None):
                status = (
                    Presence.ABSENT_EXPECTED
                    if expected and complete_workloads and not partial
                    else Presence.UNKNOWN
                    if expected
                    else Presence.ABSENT_OPTIONAL
                )
            if not signals:
                expected_evidence = self.evidence(
                    root,
                    "apimanager-declaration"
                    if declaration is not None
                    or (kind in ZYNC_COMPONENTS and zync_enabled is not None)
                    else "version-profile-rule"
                    if profile
                    else "expectation-unknown",
                    ConfidenceLevel.HIGH if declaration is not None else ConfidenceLevel.MEDIUM,
                )
                source_reference = root.id
                source_id = "runtime-semantic-projection"
                if binding and declaration is not None:
                    source_reference += f"#spec.externalComponents.{binding[0]}.{binding[1]}"
                elif kind in ZYNC_COMPONENTS and zync_enabled is not None:
                    source_reference += "#spec.zync.enabled"
                elif profile:
                    source_id = "threescale-version-profile"
                    source_reference = f"{profile.sources[0]}#profile-{profile.version}"
                expected_evidence = expected_evidence.model_copy(
                    update={
                        "provenance": expected_evidence.provenance.model_copy(
                            update={
                                "source_id": source_id,
                                "source_reference": source_reference,
                                "content_sha256": hashlib.sha256(
                                    f"{source_reference}:{kind}:{declaration}:{zync_enabled}".encode()
                                ).hexdigest(),
                            }
                        )
                    }
                )
                signals.append(expected_evidence)
            if status == Presence.ABSENT_EXPECTED:
                warnings.append(
                    SemanticWarning(code="expected_component_not_observed", resource_id=cid)
                )
            if (external and ids) or (ids and kind in ZYNC_COMPONENTS and zync_enabled is False):
                warnings.append(SemanticWarning(code="configuration_conflict", resource_id=cid))
            if (
                binding
                and declaration is False
                and profile
                and kind in profile.externally_managed_components
            ):
                warnings.append(SemanticWarning(code="configuration_conflict", resource_id=cid))
            degraded = any(
                scoped[n].details.get("unavailableReplicas", 0) not in {0, None}
                or scoped[n].status in {"Pending", "Failed", "Terminating"}
                for n in ids
            )
            rank = {ConfidenceLevel.LOW: 0, ConfidenceLevel.MEDIUM: 1, ConfidenceLevel.HIGH: 2}
            signals.sort(key=lambda e: (rank[e.confidence.level], e.id))
            components.append(
                Component(
                    id=cid,
                    type=kind,
                    role=kind.value.split("_")[0].lower(),
                    runtime_resources=tuple(sorted(ids)),
                    status=status,
                    runtime_status="DEGRADED" if degraded else "OBSERVED" if ids else "UNKNOWN",
                    expected=expected if profile or zync_enabled is not None else None,
                    external=external,
                    evidence=tuple(signals),
                    confidence=signals[0].confidence,
                )
            )
            add_edge(cid, installation_id, R.COMPONENT_OF, "installation-scope", signals[0])
            if (
                not candidate
                and any(n in owned for n in seeds.get(kind, set()))
                and kind != C.APIMANAGER
            ):
                add_edge(root.id, cid, R.MANAGES, "owner-reference", signals[0])
            for rid in sorted(ids):
                support = next(
                    (
                        e
                        for e in self.edges
                        if e.source in ids and e.target in ids and rid in {e.source, e.target}
                    ),
                    None,
                )
                bridge_evidence = signals[0]
                mechanism = "runtime-resource-bridge"
                if support and rid not in seeds.get(kind, set()):
                    mechanism = support.metadata.get("mechanism", "runtime-relationship")
                    bridge_evidence = signals[0].model_copy(
                        update={
                            "provenance": support.source_of_information,
                            "confidence": support.confidence
                            if support.confidence.level != ConfidenceLevel.HIGH
                            else signals[0].confidence,
                        }
                    )
                add_edge(cid, rid, R.EXPOSES, mechanism, bridge_evidence)
            if external and binding:
                secret_ids = {
                    rid
                    for members in memberships.values()
                    for rid in members
                    if scoped[rid].kind.value == "secret_reference"
                    and scoped[rid].name == binding[2]
                }
                dependencies.append(
                    ExternalDependency(
                        id=cid,
                        type=kind,
                        secret_references=tuple(sorted(secret_ids)),
                        evidence=tuple(signals),
                    )
                )
                warnings.append(
                    SemanticWarning(code="external_dependency_unresolved", resource_id=cid)
                )
                for rid in sorted(secret_ids):
                    add_edge(
                        rid,
                        cid,
                        R.DESCRIBES_CONNECTION_TO,
                        "documented-secret-reference",
                        signals[0],
                    )

        for component in components:
            dependency_ids: set[str] = set()
            for runtime_edge in self.edges:
                if (
                    runtime_edge.source not in component.runtime_resources
                    or runtime_edge.target not in scoped
                ):
                    continue
                if runtime_edge.relationship in {
                    Relationship.REFERENCES_SECRET,
                    Relationship.REFERENCES_CONFIGMAP,
                }:
                    add_edge(
                        component.id,
                        runtime_edge.target,
                        R.CONFIGURED_BY,
                        "runtime-reference",
                        component.evidence[0],
                    )
                    for dependency in dependencies:
                        if runtime_edge.target in dependency.secret_references:
                            relation = (
                                R.USES_QUEUE
                                if dependency.type == C.BACKEND_REDIS_QUEUES
                                else R.USES_STORAGE
                            )
                            add_edge(
                                component.id,
                                dependency.id,
                                relation,
                                "documented-secret-reference",
                                dependency.evidence[0],
                            )
                            dependency_ids.add(dependency.id)
                elif runtime_edge.relationship == Relationship.MOUNTS:
                    add_edge(
                        component.id,
                        runtime_edge.target,
                        R.USES_STORAGE,
                        "volume-reference",
                        component.evidence[0],
                    )
            if dependency_ids:
                components[components.index(component)] = component.model_copy(
                    update={"dependencies": tuple(sorted(dependency_ids))}
                )
        if len(components) > self.max_components:
            warnings.append(SemanticWarning(code="partial_topology"))
            components = components[: self.max_components]
        resource_ids = set().union(*(set(c.runtime_resources) for c in components))
        valid = resource_ids | {c.id for c in components} | {installation_id}
        edges = {k: e for k, e in edges.items() if e.source in valid and e.target in valid}
        dependencies = [d for d in dependencies if d.id in valid]
        operator_seen = any(
            hints(n).get("operator_label") for n in scoped.values() if n.id in owned
        )
        operator_state = (
            "observed" if operator_seen else "access_unavailable" if partial else "not_observed"
        )
        warnings = list({(w.code, w.resource_id): w for w in warnings}.values())
        return Installation(
            id=installation_id,
            environment_id=self.snapshot.environment_id,
            namespace=root.namespace or "default",
            version=version,
            version_profile=profile.version if profile else "UNKNOWN",
            configuration_summary={
                "external_components": external_config,
                "zync_enabled": zync_enabled,
            },
            operator_managed=not candidate and len(owned) > 1,
            operator_observation=operator_state,
            apimanager=None if candidate else root.id,
            observed_at=self.snapshot.observed_at,
            components=tuple(sorted(components, key=lambda c: c.id)),
            dependencies=tuple(sorted(dependencies, key=lambda d: d.id)),
            relationships=tuple(sorted(edges.values(), key=lambda e: e.id)),
            runtime_resources=tuple(sorted(resource_ids)),
            runtime_evidence=tuple(
                e for e in self.snapshot.evidence if e.resource_id in resource_ids
            ),
            evidence=tuple(evidence),
            warnings=tuple(sorted(warnings, key=lambda w: (w.code, w.resource_id or ""))),
            partial=partial
            or any(w.code in {"partial_topology", "ambiguous_classification"} for w in warnings),
        )
