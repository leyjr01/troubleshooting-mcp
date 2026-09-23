"""Explicit safe projections. Raw specs, Secret data and free text never escape."""

import hashlib
import json
import re
from datetime import UTC, datetime
from typing import Any

from pydantic import JsonValue

from agt_mcp.core.models import (
    Confidence,
    ConfidenceLevel,
    Evidence,
    InformationType,
    Provenance,
    Resource,
    ResourceKind,
    ResourceReference,
)
from agt_mcp.datasources.kubernetes.semantic_projection import safe_hints

KNOWN_REASONS = {
    "CrashLoopBackOff",
    "ImagePullBackOff",
    "ErrImagePull",
    "ContainerCreating",
    "PodInitializing",
    "Completed",
    "Error",
    "OOMKilled",
    "Unhealthy",
    "FailedScheduling",
    "FailedMount",
    "BackOff",
    "Pulled",
    "Started",
    "Created",
    "Scheduled",
    "Killing",
}
KINDS = {kind.value: kind for kind in ResourceKind}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def safe_name(value: object) -> str:
    text = str(value or "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", text):
        raise ValueError("invalid resource identity")
    return text


def reference(raw: dict[str, Any], environment: str, cluster: str) -> ResourceReference:
    metadata = raw["metadata"]
    return ResourceReference(
        environment_id=environment,
        cluster=cluster,
        api_version=safe_name(raw["apiVersion"]),
        kind=safe_name(raw["kind"]),
        name=safe_name(metadata["name"]),
        namespace=safe_name(metadata["namespace"]) if metadata.get("namespace") else None,
        uid=safe_name(metadata["uid"]) if metadata.get("uid") else None,
    )


def identity(ref: ResourceReference) -> str:
    return "runtime:" + digest(ref.model_dump())[:40]


def confidence(mechanism: str, high: bool = False) -> Confidence:
    return Confidence(
        level=ConfidenceLevel.HIGH if high else ConfidenceLevel.MEDIUM,
        rationale=f"API observation via {mechanism}; not a diagnosis",
        source_reliability="Authenticated API, authoritative for declared configuration",
        temporal_relevance="Bounded discovery snapshot; not atomic across resource versions",
        topological_relevance="Direct scoped reference or selector evaluation",
        historical_similarity="Not used",
    )


def provenance(environment: str, observed: datetime, resource_id: str, data: object) -> Provenance:
    return Provenance(
        source_id="kubernetes-api",
        environment_id=environment,
        retrieved_at=observed,
        source_reference=resource_id,
        content_sha256=digest(data),
    )


def timestamp(value: object, fallback: datetime) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return result.astimezone(UTC) if result.tzinfo else fallback
    except ValueError:
        return fallback


def number(value: object) -> int:
    return value if type(value) is int and 0 <= value <= 1000000000 else 0


def scalar(value: object, maximum: int = 256) -> str:
    """Only structural names/hosts/paths/quantities; no unrestricted free text."""
    text = str(value or "")
    return (
        text
        if len(text) <= maximum and re.fullmatch(r"[A-Za-z0-9._:/%*+-]*", text)
        else "[REDACTED]"
    )


def condition(value: object) -> bool | None:
    return value if type(value) is bool else None


def selector_structure(value: object) -> JsonValue:
    """Preserve selector shape with opaque hashed label identities, not label values."""
    if not isinstance(value, dict):
        return {}
    return {
        "matchLabels": {
            digest(k)[:12]: digest(v)[:12]
            for k, v in list(value.get("matchLabels", {}).items())[:32]
        },
        "matchExpressions": [
            {
                "key": digest(e.get("key"))[:12],
                "operator": e.get("operator")
                if e.get("operator") in {"In", "NotIn", "Exists", "DoesNotExist"}
                else "unknown",
                "values": [digest(v)[:12] for v in e.get("values", [])[:32]],
            }
            for e in value.get("matchExpressions", [])[:32]
        ],
    }


def normalize(raw: dict[str, Any], environment: str, cluster: str) -> Resource:
    ref = reference(raw, environment, cluster)
    kind = KINDS.get(ref.kind.lower(), ResourceKind.CUSTOM_RESOURCE)
    spec, state = raw.get("spec", {}), raw.get("status", {})
    details: dict[str, JsonValue] = {}
    status = "observed"
    if ref.kind == "Pod":
        phase = state.get("phase", "Unknown")
        status = (
            phase
            if phase in {"Pending", "Running", "Succeeded", "Failed", "Unknown"}
            else "Unknown"
        )
        if raw["metadata"].get("deletionTimestamp"):
            status = "Terminating"
        details["containers"] = [
            {
                "name": scalar(c.get("name")),
                "restarts": number(c.get("restartCount")),
                "ready": c.get("ready") is True,
                "waiting_reason": c.get("state", {}).get("waiting", {}).get("reason")
                if c.get("state", {}).get("waiting", {}).get("reason") in KNOWN_REASONS
                else None,
            }
            for c in state.get("containerStatuses", [])[:32]
        ]
    elif ref.kind in {"Deployment", "ReplicaSet", "StatefulSet", "DaemonSet"}:
        details = {
            key: number(state.get(key))
            for key in (
                "replicas",
                "readyReplicas",
                "availableReplicas",
                "unavailableReplicas",
                "desiredNumberScheduled",
                "numberReady",
            )
        }
    elif ref.kind == "PersistentVolumeClaim":
        status = (
            state.get("phase") if state.get("phase") in {"Pending", "Bound", "Lost"} else "Unknown"
        )
        details = {
            "storageClass": scalar(spec.get("storageClassName")),
            "accessModes": [
                v
                for v in spec.get("accessModes", [])
                if v in {"ReadWriteOnce", "ReadOnlyMany", "ReadWriteMany", "ReadWriteOncePod"}
            ],
            "requestedCapacity": scalar(
                spec.get("resources", {}).get("requests", {}).get("storage")
            ),
            "boundVolume": scalar(spec.get("volumeName")),
        }
    elif ref.kind == "EndpointSlice":
        details = {
            "addressType": scalar(raw.get("addressType")),
            "ports": [
                {
                    "name": scalar(p.get("name")),
                    "port": number(p.get("port")),
                    "protocol": p.get("protocol")
                    if p.get("protocol") in {"TCP", "UDP", "SCTP"}
                    else "TCP",
                }
                for p in raw.get("ports", [])[:32]
            ],
            "endpoints": [
                {
                    "addresses": [scalar(a) for a in e.get("addresses", [])[:16]],
                    "ready": condition(e.get("conditions", {}).get("ready")),
                    "serving": condition(e.get("conditions", {}).get("serving")),
                    "terminating": condition(e.get("conditions", {}).get("terminating")),
                    "hostname": scalar(e.get("hostname")),
                    "nodeName": scalar(e.get("nodeName")),
                    "zone": scalar(e.get("zone")),
                    "targetRef": {
                        k: scalar(e.get("targetRef", {}).get(k))
                        for k in ("kind", "namespace", "name", "uid")
                    },
                }
                for e in raw.get("endpoints", [])[:100]
            ],
        }
    elif ref.kind == "Route":
        admitted = [
            condition.get("status") == "True"
            for ingress in state.get("ingress", [])
            for condition in ingress.get("conditions", [])
            if condition.get("type") == "Admitted"
        ]
        details = {
            "host": scalar(spec.get("host")),
            "path": scalar(spec.get("path")),
            "serviceTarget": scalar(spec.get("to", {}).get("name")),
            "portTarget": scalar(spec.get("port", {}).get("targetPort")),
            "tlsTermination": scalar(spec.get("tls", {}).get("termination")),
            "wildcardPolicy": scalar(spec.get("wildcardPolicy")),
            "admitted": any(admitted) if admitted else None,
        }
    elif ref.kind == "Ingress":
        details = {
            "rules": [
                {
                    "host": scalar(rule.get("host")),
                    "paths": [
                        {
                            "path": scalar(path.get("path")),
                            "service": scalar(
                                path.get("backend", {}).get("service", {}).get("name")
                            ),
                            "port": scalar(
                                path.get("backend", {})
                                .get("service", {})
                                .get("port", {})
                                .get("name")
                                or path.get("backend", {})
                                .get("service", {})
                                .get("port", {})
                                .get("number")
                            ),
                        }
                        for path in rule.get("http", {}).get("paths", [])[:32]
                    ],
                }
                for rule in spec.get("rules", [])[:32]
            ],
            "tlsSecretReferences": [
                scalar(item.get("secretName")) for item in spec.get("tls", [])[:32]
            ],
        }
    elif ref.kind == "NetworkPolicy":
        details = {
            "policyTypes": [p for p in spec.get("policyTypes", []) if p in {"Ingress", "Egress"}],
            "podSelector": selector_structure(spec.get("podSelector")),
        }
        for direction in ("ingress", "egress"):
            peer_key = "from" if direction == "ingress" else "to"
            details[direction] = [
                {
                    "peers": [
                        {
                            "podSelector": selector_structure(peer.get("podSelector")),
                            "namespaceSelector": selector_structure(peer.get("namespaceSelector")),
                            "ipBlock": {
                                "cidr": scalar(peer.get("ipBlock", {}).get("cidr")),
                                "except": [
                                    scalar(v)
                                    for v in peer.get("ipBlock", {}).get("except", [])[:32]
                                ],
                            },
                        }
                        for peer in rule.get(peer_key, [])[:32]
                    ],
                    "ports": [
                        {"port": scalar(p.get("port")), "protocol": scalar(p.get("protocol"))}
                        for p in rule.get("ports", [])[:32]
                    ],
                }
                for rule in spec.get(direction, [])[:32]
            ]
    elif ref.kind == "CustomResourceDefinition":
        details = {
            "group": scalar(spec.get("group")),
            "kind": scalar(spec.get("names", {}).get("kind")),
            "plural": scalar(spec.get("names", {}).get("plural")),
            "scope": scalar(spec.get("scope")),
            "servedVersions": [
                scalar(v.get("name"))
                for v in spec.get("versions", [])[:32]
                if v.get("served") is True
            ],
        }
    hints = safe_hints(raw)
    if hints:
        details["discovery_hints"] = hints
    # ConfigMap data/binaryData, Event messages, annotations and arbitrary CR specs are absent.
    return Resource(
        id=identity(ref),
        environment_id=environment,
        namespace=ref.namespace,
        kind=kind,
        name=ref.name,
        provider="kubernetes",
        reference=ref,
        status=status,
        details=details,
        metadata={"trust": "untrusted-external-data", "projection": "runtime-safe-v1"},
    )


def observation(
    resource: Resource, observed: datetime, text: str, timestamp_value: datetime | None = None
) -> Evidence:
    data = {"resource": resource.id, "observation": text}
    return Evidence(
        id="evidence:" + digest(data)[:40],
        environment_id=resource.environment_id,
        timestamp=timestamp_value or observed,
        source=provenance(resource.environment_id, observed, resource.id, data),
        type=InformationType.OBSERVATION,
        resource_id=resource.id,
        observation=text,
        raw_reference=resource.id,
        confidence=confidence("runtime-observation"),
        metadata={"trust": "untrusted-external-data", "projection": "runtime-safe-v1"},
    )
