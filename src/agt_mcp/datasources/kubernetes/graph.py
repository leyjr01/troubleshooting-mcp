"""Derive declared runtime relationships while raw API objects remain adapter-local."""

import json
from datetime import datetime
from typing import Any

from agt_mcp.configuration.runtime import RuntimeLimits
from agt_mcp.core.models import Evidence, Resource, ResourceKind, ResourceReference
from agt_mcp.core.runtime import CategoryResult, DiscoveryWarning, UnresolvedRelationship
from agt_mcp.datasources.kubernetes.mapping import (
    KNOWN_REASONS,
    confidence,
    digest,
    identity,
    normalize,
    observation,
    provenance,
    safe_name,
    timestamp,
)
from agt_mcp.topology.models import Dependency, Relationship, Topology


def matches(selector: dict[str, Any], labels: dict[str, Any]) -> bool:
    if any(labels.get(key) != value for key, value in selector.get("matchLabels", {}).items()):
        return False
    for expression in selector.get("matchExpressions", []):
        key, operation, values = (
            expression.get("key"),
            expression.get("operator"),
            expression.get("values", []),
        )
        if operation == "In" and (key not in labels or labels[key] not in values):
            return False
        if operation == "NotIn" and key in labels and labels[key] in values:
            return False
        if operation == "Exists" and key not in labels:
            return False
        if operation == "DoesNotExist" and key in labels:
            return False
        if operation not in {"In", "NotIn", "Exists", "DoesNotExist"}:
            return False
    return True


class GraphBuilder:
    def __init__(
        self,
        environment: str,
        cluster: str,
        observed: datetime,
        limits: RuntimeLimits,
        categories: list[CategoryResult],
    ) -> None:
        self.environment, self.cluster, self.observed, self.limits = (
            environment,
            cluster,
            observed,
            limits,
        )
        self.categories = categories
        self.nodes: dict[str, Resource] = {}
        self.raw: dict[str, dict[str, Any]] = {}
        self.edges: dict[str, Dependency] = {}
        self.warnings: list[DiscoveryWarning] = []
        self.unresolved: list[UnresolvedRelationship] = []
        self.evidence: dict[str, Evidence] = {}

    def warn(self, code: Any, source: Resource | None = None) -> None:
        warning = DiscoveryWarning(
            code=code,
            resource_id=source.id if source else None,
            namespace=source.namespace if source else None,
            kind=source.reference.kind if source and source.reference else None,
        )
        if warning not in self.warnings and len(self.warnings) < self.limits.max_relationships:
            self.warnings.append(warning)

    def add(self, raw: dict[str, Any]) -> None:
        if raw.get("kind") == "ConfigMap":
            content = {k: raw[k] for k in ("data", "binaryData") if k in raw}
            if len(json.dumps(content).encode()) > self.limits.max_configmap_bytes:
                self.warn("truncated_discovery")
            # Discard content before retaining the adapter's relationship snapshot.
            raw = {k: v for k, v in raw.items() if k not in {"data", "binaryData"}}
        try:
            node = normalize(raw, self.environment, self.cluster)
        except (ValueError, KeyError, TypeError, AttributeError):
            self.warn("invalid_resource")
            return
        if len(self.nodes) >= self.limits.max_topology_nodes and node.id not in self.nodes:
            self.warn("truncated_discovery")
            return
        self.nodes[node.id], self.raw[node.id] = node, raw

    def edge(
        self, source: Resource, target: Resource, relation: Relationship, mechanism: str
    ) -> None:
        key = "edge:" + digest((source.id, target.id, relation.value))[:40]
        if len(self.edges) >= self.limits.max_relationships and key not in self.edges:
            self.warn("truncated_discovery", source)
            return
        self.edges[key] = Dependency(
            id=key,
            source=source.id,
            target=target.id,
            relationship=relation,
            source_of_information=provenance(
                self.environment, self.observed, source.id, (key, mechanism)
            ),
            confidence=confidence(mechanism, mechanism != "label-selector"),
            metadata={"mechanism": mechanism},
        )

    def find(
        self,
        kind: str,
        name: str,
        namespace: str | None,
        uid: str | None = None,
        api_version: str | None = None,
    ) -> list[Resource]:
        return [
            r
            for r in self.nodes.values()
            if r.reference
            and r.reference.kind == kind
            and r.name == name
            and r.namespace == namespace
            and (uid is None or r.reference.uid == uid)
            and (api_version is None or r.reference.api_version == api_version)
        ]

    def refer(
        self,
        source: Resource,
        kind: str,
        name: object,
        relation: Relationship,
        mechanism: str,
        namespace: str | None = None,
        uid: str | None = None,
        api_version: str = "v1",
    ) -> Resource | None:
        try:
            target = ResourceReference(
                environment_id=self.environment,
                cluster=self.cluster,
                namespace=namespace,
                kind=safe_name(kind),
                name=safe_name(name),
                uid=uid,
                api_version=api_version,
            )
        except ValueError:
            self.warn("invalid_resource", source)
            return None
        if kind == "Secret":
            key = identity(target)
            if key not in self.nodes:
                if len(self.nodes) >= self.limits.max_topology_nodes:
                    self.warn("truncated_discovery", source)
                    return None
                self.nodes[key] = Resource(
                    id=key,
                    environment_id=self.environment,
                    namespace=namespace,
                    name=target.name,
                    kind=ResourceKind.SECRET_REFERENCE,
                    provider="kubernetes",
                    reference=target,
                    status="reference-only",
                    details={
                        "type_if_available": None,
                        "keys_if_safely_available": [],
                        "content_read": False,
                        "referenced_by": source.id,
                        "usage_type": mechanism,
                    },
                    metadata={"trust": "untrusted-external-data"},
                )
            self.edge(source, self.nodes[key], relation, mechanism)
            return self.nodes[key]
        candidates = self.find(kind, target.name, namespace, uid, api_version)
        if len(candidates) == 1:
            self.edge(source, candidates[0], relation, mechanism)
            return candidates[0]
        category = next(
            (c for c in self.categories if c.namespace == namespace and c.kind == kind), None
        )
        resolution = "ambiguous" if len(candidates) > 1 else "not_observed"
        if len(candidates) > 1:
            self.warn("ambiguous_selector", source)
        elif category and category.status == "completed":
            resolution = "not_found"
        elif category and category.status == "forbidden":
            resolution = "forbidden"
        if len(self.unresolved) < self.limits.max_relationships:
            self.unresolved.append(
                UnresolvedRelationship(
                    source=source.id,
                    target=target,
                    relationship=relation,
                    resolution=resolution,
                    mechanism=mechanism,
                )
            )
        else:
            self.warn("truncated_discovery", source)
        self.warn("missing_target", source)
        return None

    def build(self) -> Topology:
        for identifier, raw in list(self.raw.items()):
            source = self.nodes[identifier]
            try:
                self.relationships(source, raw)
                self.observations(source, raw)
            except (ValueError, TypeError, KeyError, AttributeError):
                self.warn("invalid_resource", source)
        return Topology(
            environment_id=self.environment,
            nodes=tuple(sorted(self.nodes.values(), key=lambda n: n.id)),
            edges=tuple(sorted(self.edges.values(), key=lambda e: e.id)),
        )

    def relationships(self, source: Resource, raw: dict[str, Any]) -> None:
        namespace, spec = source.namespace, raw.get("spec", {})
        for owner in raw["metadata"].get("ownerReferences", [])[:32]:
            if not owner.get("uid"):
                self.warn("invalid_resource", source)
                continue
            owners = (
                self.find(
                    owner.get("kind"),
                    owner.get("name"),
                    namespace,
                    owner.get("uid"),
                    owner.get("apiVersion"),
                )
                if owner.get("uid")
                else []
            )
            if len(owners) == 1:
                self.edge(owners[0], source, Relationship.OWNS, "owner-reference")
            else:
                # Reverse explicit reference retains the missing owner without fabricating a node.
                self.refer(
                    source,
                    owner.get("kind"),
                    owner.get("name"),
                    Relationship.MANAGED_BY,
                    "owner-reference",
                    namespace,
                    owner.get("uid"),
                    owner.get("apiVersion", "v1"),
                )
        if raw["kind"] in {"Service", "NetworkPolicy"}:
            selector = (
                {"matchLabels": spec.get("selector", {})}
                if raw["kind"] == "Service"
                else spec.get("podSelector", {})
            )
            if raw["kind"] != "Service" or spec.get("selector"):
                for target_id, candidate in self.raw.items():
                    if (
                        candidate["kind"] == "Pod"
                        and candidate["metadata"].get("namespace") == namespace
                        and matches(selector, candidate["metadata"].get("labels", {}))
                    ):
                        self.edge(
                            source, self.nodes[target_id], Relationship.SELECTS, "label-selector"
                        )
        if raw["kind"] == "Pod":
            self.pod_references(source, spec)
        elif raw["kind"] in {"Deployment", "StatefulSet", "DaemonSet", "ReplicaSet"}:
            self.pod_references(source, spec.get("template", {}).get("spec", {}))
        if raw["kind"] == "PersistentVolumeClaim" and spec.get("volumeName"):
            self.refer(
                source, "PersistentVolume", spec["volumeName"], Relationship.BOUND_TO, "pvc-spec"
            )
        if raw["kind"] == "Route":
            for target in [spec.get("to", {}), *spec.get("alternateBackends", [])[:32]]:
                if target.get("kind", "Service") == "Service":
                    self.refer(
                        source,
                        "Service",
                        target.get("name"),
                        Relationship.ROUTES_TO,
                        "route-spec",
                        namespace,
                    )
        if raw["kind"] == "Ingress":
            backends = [spec.get("defaultBackend", {})]
            backends.extend(
                path.get("backend", {})
                for rule in spec.get("rules", [])[:32]
                for path in rule.get("http", {}).get("paths", [])[:32]
            )
            for backend in backends:
                if backend.get("service", {}).get("name"):
                    self.refer(
                        source,
                        "Service",
                        backend["service"]["name"],
                        Relationship.ROUTES_TO,
                        "ingress-spec",
                        namespace,
                    )
            for tls in spec.get("tls", [])[:32]:
                if tls.get("secretName"):
                    self.refer(
                        source,
                        "Secret",
                        tls["secretName"],
                        Relationship.REFERENCES_SECRET,
                        "ingress-tls",
                        namespace,
                    )
        if raw["kind"] == "EndpointSlice":
            self.endpoints(source, raw)
        if raw["kind"] == "Service":
            complete = any(
                c.kind == "EndpointSlice" and c.namespace == namespace and c.status == "completed"
                for c in self.categories
            )
            slices = [
                s
                for s in self.raw.values()
                if s["kind"] == "EndpointSlice"
                and s["metadata"].get("namespace") == namespace
                and s["metadata"].get("labels", {}).get("kubernetes.io/service-name") == source.name
            ]
            if complete and not any(
                e.get("conditions", {}).get("ready") is not False
                for s in slices
                for e in s.get("endpoints", [])
            ):
                self.warn("no_endpoints", source)
                self.record(
                    observation(source, self.observed, "Service has no ready runtime endpoints")
                )

    def pod_references(self, source: Resource, spec: dict[str, Any]) -> None:
        namespace = source.namespace
        for container in [
            *spec.get("containers", []),
            *spec.get("initContainers", []),
            *spec.get("ephemeralContainers", []),
        ][:64]:
            for env in container.get("env", [])[:128]:
                value = env.get("valueFrom", {})
                for key, kind, relation in (
                    ("secretKeyRef", "Secret", Relationship.REFERENCES_SECRET),
                    ("configMapKeyRef", "ConfigMap", Relationship.REFERENCES_CONFIGMAP),
                ):
                    if value.get(key, {}).get("name"):
                        self.refer(source, kind, value[key]["name"], relation, key, namespace)
            for env in container.get("envFrom", [])[:128]:
                for key, kind, relation in (
                    ("secretRef", "Secret", Relationship.REFERENCES_SECRET),
                    ("configMapRef", "ConfigMap", Relationship.REFERENCES_CONFIGMAP),
                ):
                    if env.get(key, {}).get("name"):
                        self.refer(source, kind, env[key]["name"], relation, key, namespace)
        for volume in spec.get("volumes", [])[:128]:
            for item in [volume, *volume.get("projected", {}).get("sources", [])[:32]]:
                for key, name_key, kind, relation in (
                    ("secret", "secretName", "Secret", Relationship.REFERENCES_SECRET),
                    ("configMap", "name", "ConfigMap", Relationship.REFERENCES_CONFIGMAP),
                    (
                        "persistentVolumeClaim",
                        "claimName",
                        "PersistentVolumeClaim",
                        Relationship.MOUNTS,
                    ),
                ):
                    name = item.get(key, {}).get(name_key) or item.get(key, {}).get("name")
                    if name:
                        self.refer(source, kind, name, relation, "volume-reference", namespace)
        for pull in spec.get("imagePullSecrets", [])[:32]:
            self.refer(
                source,
                "Secret",
                pull.get("name"),
                Relationship.REFERENCES_SECRET,
                "image-pull-secret",
                namespace,
            )
        self.refer(
            source,
            "ServiceAccount",
            spec.get("serviceAccountName", "default"),
            Relationship.USES_SERVICE_ACCOUNT,
            "pod-spec",
            namespace,
        )

    def endpoints(self, source: Resource, raw: dict[str, Any]) -> None:
        service_name = raw["metadata"].get("labels", {}).get("kubernetes.io/service-name")
        services = self.find("Service", service_name, source.namespace) if service_name else []
        if len(services) == 1:
            self.edge(services[0], source, Relationship.HAS_ENDPOINTSLICE, "service-label")
        for index, endpoint in enumerate(raw.get("endpoints", [])[:100]):
            target = endpoint.get("targetRef", {})
            if target.get("kind") == "Pod" and target.get("name"):
                node = self.refer(
                    source,
                    "Pod",
                    target["name"],
                    Relationship.TARGETS,
                    "endpoint-target-reference",
                    target.get("namespace") or source.namespace,
                    target.get("uid"),
                )
            else:
                if len(self.nodes) >= self.limits.max_topology_nodes:
                    self.warn("truncated_discovery", source)
                    continue
                key = "endpoint:" + digest((source.id, index))[:40]
                node = Resource(
                    id=key,
                    environment_id=self.environment,
                    namespace=source.namespace,
                    name=f"endpoint-{index}",
                    kind=ResourceKind.ENDPOINT,
                    provider="kubernetes",
                    status="ready"
                    if endpoint.get("conditions", {}).get("ready") is not False
                    else "not-ready",
                    metadata={"identity_scope": source.id},
                )
                self.nodes[key] = node
                self.edge(source, node, Relationship.TARGETS, "endpoint-address")
            if (
                node
                and len(services) == 1
                and endpoint.get("conditions", {}).get("ready") is not False
            ):
                self.edge(services[0], node, Relationship.HAS_ENDPOINT, "ready-endpoint")

    def record(self, evidence: Evidence) -> None:
        if len(self.evidence) < self.limits.max_events:
            self.evidence[evidence.id] = evidence
        else:
            self.warn("truncated_discovery")

    def observations(self, source: Resource, raw: dict[str, Any]) -> None:
        if raw["kind"] == "Event":
            ref = raw.get("involvedObject", {})
            targets = self.find(
                ref.get("kind"),
                ref.get("name"),
                ref.get("namespace"),
                ref.get("uid"),
            )
            if len(targets) == 1:
                reason = raw.get("reason") if raw.get("reason") in KNOWN_REASONS else "Unclassified"
                observed = timestamp(
                    raw.get("eventTime")
                    or raw.get("lastTimestamp")
                    or raw["metadata"].get("creationTimestamp"),
                    self.observed,
                )
                evidence = observation(
                    targets[0],
                    self.observed,
                    f"Kubernetes Event: {reason}; free text withheld",
                    observed,
                )
                self.record(
                    evidence.model_copy(
                        update={
                            "id": "evidence:" + digest((source.id, observed))[:40],
                            "source": provenance(
                                self.environment, self.observed, source.id, evidence.observation
                            ),
                            "raw_reference": source.id,
                        }
                    )
                )
        elif raw["kind"] in {
            "Pod",
            "Deployment",
            "PersistentVolumeClaim",
            "EndpointSlice",
            "Route",
        }:
            safe = {"status": source.status, "details": source.details}
            text = json_text(safe)
            self.record(observation(source, self.observed, text))


def json_text(value: object) -> str:
    import json

    return json.dumps(value, sort_keys=True)[:16000]
