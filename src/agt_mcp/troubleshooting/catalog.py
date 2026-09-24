"""Declarative catalogs select trusted rule identifiers, never executable document text."""

from typing import Protocol

from agt_mcp.core.errors import ConfigurationError
from agt_mcp.core.models import ResourceKind
from agt_mcp.troubleshooting.models import (
    EvidenceRequirement,
    HypothesisDefinition,
    RuleKind,
    SafetyClass,
)


class HypothesisProvider(Protocol):
    def definitions(self) -> tuple[HypothesisDefinition, ...]: ...


def requirement(
    identifier: str, description: str, capability: str = "resource.read", probe: bool = False
) -> EvidenceRequirement:
    return EvidenceRequirement(
        id=identifier,
        description=description,
        required_capability=capability,
        safety_class=SafetyClass.PASSIVE_PROBE if probe else SafetyClass.READ_ONLY_INSPECTION,
    )


REQUIREMENTS = {
    RuleKind.AVAILABILITY: (requirement("runtime_state", "Inspect current runtime availability"),),
    RuleKind.ENDPOINT: (
        requirement("service_topology", "Inspect Service endpoint topology", "topology.read"),
        requirement("endpoint_readiness", "Inspect every related EndpointSlice readiness"),
    ),
    RuleKind.ROUTING: (
        requirement(
            "target_resolution",
            "Inspect declared routing target and scoped inventory",
            "topology.read",
        ),
    ),
    RuleKind.CRASH_LOOP: (
        requirement("container_lifecycle", "Inspect current container waiting state"),
    ),
    RuleKind.PVC: (
        requirement("volume_binding", "Inspect the PersistentVolumeClaim binding state"),
    ),
    RuleKind.REFERENCE: (
        requirement(
            "dependency_reference", "Inspect unresolved configuration references", "topology.read"
        ),
    ),
    RuleKind.EXTERNAL: (
        requirement(
            "dependency_connectivity",
            "Obtain application-level connectivity evidence",
            "DEPENDENCY_CONNECTIVITY_NOT_AVAILABLE",
            True,
        ),
    ),
}


def definition(
    identifier: str,
    description: str,
    rule: RuleKind,
    kinds: tuple[ResourceKind, ...] = (),
    components: tuple[str, ...] = (),
    gateway: str | None = None,
    versions: tuple[str, ...] = (),
    capability: str | None = None,
) -> HypothesisDefinition:
    required = REQUIREMENTS[rule]
    if capability:
        required = (required[0].model_copy(update={"required_capability": capability}),)
    return HypothesisDefinition(
        id=identifier,
        name=identifier,
        description=description,
        rule=rule,
        scope="component" if components and not kinds else "resource",
        applicable_resource_types=kinds,
        applicable_component_types=components,
        gateway_constraints=(gateway,) if gateway else (),
        version_constraints=versions,
        required_evidence=required,
        optional_evidence=(
            requirement("recent_events", "Review relevant recent events", "event.read").model_copy(
                update={"optional": True, "purpose": "strengthen"}
            ),
        ),
        priority=20 if gateway else 50,
    )


class GenericHypothesisProvider:
    def definitions(self) -> tuple[HypothesisDefinition, ...]:
        return (
            definition(
                "RESOURCE_UNAVAILABLE",
                "Resource runtime availability is impaired",
                RuleKind.AVAILABILITY,
                (
                    ResourceKind.GATEWAY,
                    ResourceKind.API,
                    ResourceKind.BACKEND,
                    ResourceKind.EXTERNAL_SERVICE,
                ),
            ),
            definition(
                "CONFIGURATION_REFERENCE_UNRESOLVED",
                "Declared configuration dependency is unresolved",
                RuleKind.REFERENCE,
                (ResourceKind.POD, ResourceKind.DEPLOYMENT),
            ),
        )


class KubernetesHypothesisProvider:
    def definitions(self) -> tuple[HypothesisDefinition, ...]:
        return (
            definition(
                "SERVICE_NO_READY_ENDPOINT",
                "Service has no usable runtime endpoint",
                RuleKind.ENDPOINT,
                (ResourceKind.SERVICE,),
            ),
            definition(
                "WORKLOAD_UNAVAILABLE",
                "Workload runtime availability is impaired",
                RuleKind.AVAILABILITY,
                (ResourceKind.DEPLOYMENT, ResourceKind.STATEFULSET, ResourceKind.DAEMONSET),
            ),
            definition(
                "POD_CRASH_LOOP",
                "Container lifecycle is repeatedly failing; process cause is unknown",
                RuleKind.CRASH_LOOP,
                (ResourceKind.POD,),
            ),
            definition(
                "PVC_NOT_BOUND",
                "PersistentVolumeClaim is not bound",
                RuleKind.PVC,
                (ResourceKind.PVC,),
            ),
            definition(
                "ROUTE_TARGET_MISSING",
                "Declared Route target is unresolved in observed inventory",
                RuleKind.ROUTING,
                (ResourceKind.ROUTE,),
            ),
            definition(
                "INGRESS_TARGET_MISSING",
                "Declared Ingress target is unresolved in observed inventory",
                RuleKind.ROUTING,
                (ResourceKind.INGRESS,),
            ),
        )


class HypothesisCatalog:
    def __init__(self, providers: tuple[HypothesisProvider, ...]) -> None:
        items = [d for p in providers for d in p.definitions()]
        if len({d.id for d in items}) != len(items):
            raise ConfigurationError()
        self.definitions = tuple(sorted(items, key=lambda d: (d.priority, d.id)))
        self.by_id = {d.id: d for d in self.definitions}
