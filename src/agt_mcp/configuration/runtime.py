"""Explicit environment-to-cluster bindings and bounded read-only discovery."""

from typing import Literal, Self

from pydantic import Field, model_validator

from agt_mcp.core.models import Environment, Identifier, Model
from agt_mcp.core.runtime import RuntimeName


class RuntimeAuthentication(Model):
    mode: Literal["kubeconfig", "in-cluster"] = "kubeconfig"
    kubeconfig: str = "~/.kube/config"
    context: Identifier | None = None
    cluster: Identifier | None = None


class NamespaceScope(Model):
    include: tuple[RuntimeName, ...] = ()
    exclude: tuple[RuntimeName, ...] = ()


class RuntimeLimits(Model):
    max_namespaces: int = Field(default=5, ge=1, le=20)
    max_resources_per_type: int = Field(default=100, ge=1, le=1000)
    max_events: int = Field(default=50, ge=1, le=200)
    max_relationships: int = Field(default=1000, ge=1, le=10000)
    max_topology_nodes: int = Field(default=500, ge=1, le=5000)
    max_topology_depth: int = Field(default=3, ge=1, le=3)
    max_configmap_bytes: int = Field(default=16384, ge=1, le=65536)
    max_response_bytes: int = Field(default=1048576, ge=1024, le=4194304)
    page_size: int = Field(default=50, ge=1, le=200)


class SecretPolicy(Model):
    mode: Literal["referenced-metadata-only"] = "referenced-metadata-only"


class CustomResourceSpec(Model):
    group: RuntimeName
    version: RuntimeName
    plural: RuntimeName
    kind: Identifier
    namespaced: bool = True

    @model_validator(mode="after")
    def safe_group(self) -> Self:
        if (
            self.kind.lower() in {"secret", "secretlist"}
            or "." not in self.group
            or self.plural
            in {
                "secrets",
                "tokenreviews",
                "subjectaccessreviews",
            }
        ):
            raise ValueError("invalid custom resource binding")
        return self


class DiscoveryConfig(Model):
    namespaces: NamespaceScope = NamespaceScope()
    cluster_scoped: bool = False
    secrets: SecretPolicy = SecretPolicy()
    custom_resources: tuple[CustomResourceSpec, ...] = ()
    limits: RuntimeLimits = RuntimeLimits()


class RuntimeConfig(Model):
    provider: Literal["kubernetes", "openshift"]
    authentication: RuntimeAuthentication = RuntimeAuthentication()
    discovery: DiscoveryConfig = DiscoveryConfig()
    timeout_seconds: float = Field(default=20, gt=0, le=60)


class RuntimeEnvironment(Environment):
    enabled: bool = True
    runtime: RuntimeConfig | None = None
