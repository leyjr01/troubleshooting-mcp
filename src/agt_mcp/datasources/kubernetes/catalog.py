"""Allowlisted generated SDK operations. No Secret or write operation is registered."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceType:
    kind: str
    api_version: str
    plural: str
    api_class: str
    namespaced: bool = True
    suffix: str = ""

    @property
    def method_suffix(self) -> str:
        return self.suffix or self.plural.removesuffix("s")


TYPES = (
    ResourceType("Pod", "v1", "pods", "CoreV1Api", suffix="pod"),
    ResourceType("Deployment", "apps/v1", "deployments", "AppsV1Api", suffix="deployment"),
    ResourceType("ReplicaSet", "apps/v1", "replicasets", "AppsV1Api", suffix="replica_set"),
    ResourceType("StatefulSet", "apps/v1", "statefulsets", "AppsV1Api", suffix="stateful_set"),
    ResourceType("DaemonSet", "apps/v1", "daemonsets", "AppsV1Api", suffix="daemon_set"),
    ResourceType("Service", "v1", "services", "CoreV1Api", suffix="service"),
    ResourceType(
        "EndpointSlice",
        "discovery.k8s.io/v1",
        "endpointslices",
        "DiscoveryV1Api",
        suffix="endpoint_slice",
    ),
    ResourceType("ConfigMap", "v1", "configmaps", "CoreV1Api", suffix="config_map"),
    ResourceType(
        "PersistentVolumeClaim",
        "v1",
        "persistentvolumeclaims",
        "CoreV1Api",
        suffix="persistent_volume_claim",
    ),
    ResourceType("ServiceAccount", "v1", "serviceaccounts", "CoreV1Api", suffix="service_account"),
    ResourceType("Event", "v1", "events", "CoreV1Api", suffix="event"),
    ResourceType(
        "Ingress", "networking.k8s.io/v1", "ingresses", "NetworkingV1Api", suffix="ingress"
    ),
    ResourceType(
        "NetworkPolicy",
        "networking.k8s.io/v1",
        "networkpolicies",
        "NetworkingV1Api",
        suffix="network_policy",
    ),
    ResourceType("Namespace", "v1", "namespaces", "CoreV1Api", False, "namespace"),
    ResourceType(
        "PersistentVolume", "v1", "persistentvolumes", "CoreV1Api", False, "persistent_volume"
    ),
    ResourceType(
        "CustomResourceDefinition",
        "apiextensions.k8s.io/v1",
        "customresourcedefinitions",
        "ApiextensionsV1Api",
        False,
        "custom_resource_definition",
    ),
)
ROUTE = ResourceType("Route", "route.openshift.io/v1", "routes", "CustomObjectsApi")
DISCOVERY_APIS = (
    "v1",
    "apps/v1",
    "networking.k8s.io/v1",
    "discovery.k8s.io/v1",
    "storage.k8s.io/v1",
    "rbac.authorization.k8s.io/v1",
    "apiextensions.k8s.io/v1",
    "route.openshift.io/v1",
)
