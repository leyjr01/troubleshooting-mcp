"""Validated configuration contracts. Secret values are not configuration fields."""

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from agt_mcp.configuration.correlation import CorrelationConfig
from agt_mcp.configuration.gateway import GatewayDiscoveryConfig
from agt_mcp.configuration.knowledge import KnowledgeLimits, KnowledgeSourceConfig
from agt_mcp.configuration.runtime import RuntimeEnvironment
from agt_mcp.configuration.server import MCPConfig
from agt_mcp.core.models import Identifier, Model
from agt_mcp.core.operations import Operation
from agt_mcp.credentials.providers import CredentialReference

Host = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9.:-]*$")]


class TLSConfig(Model):
    enabled: Literal[True] = True
    verify: Literal[True] = True


class ConnectionConfig(Model):
    host: Host
    port: int = Field(ge=1, le=65535)
    database: Identifier | None = None


class DataSourceConfig(Model):
    id: Identifier
    environment_id: Identifier
    type: Literal[
        "git", "database", "vector", "search", "metrics", "logs", "rest", "kubernetes", "memory"
    ]
    provider: Identifier
    enabled: bool = False
    connection: ConnectionConfig
    credentials: CredentialReference | None = None
    tls: TLSConfig = TLSConfig()
    usage: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def same_environment(self) -> Self:
        if self.credentials and self.credentials.environment_id != self.environment_id:
            raise ValueError("credential scope mismatch")
        return self


class GatewayConfig(Model):
    id: Identifier
    environment_id: Identifier
    adapter: Identifier
    enabled: bool = False
    datasource_id: Identifier | None = None
    discovery: GatewayDiscoveryConfig = GatewayDiscoveryConfig()


class RAGConfig(Model):
    enabled: Literal[False] = False
    repository_ids: tuple[Identifier, ...] = ()
    max_results: int = Field(default=10, ge=1, le=100)


class DiagnosticsConfig(Model):
    enabled: Literal[False] = False
    max_evidence: int = Field(default=100, ge=1, le=1000)


class ApplicationConfig(Model):
    environment: Identifier = "demo"
    read_only: Literal[True] = True
    timeout_seconds: float = Field(default=10, gt=0, le=300)
    max_payload_bytes: int = Field(default=65536, ge=1, le=1048576)
    allowed_operations: tuple[Operation, ...] = tuple(Operation)


class Configuration(Model):
    schema_version: Literal["1.0.0"] = "1.0.0"
    application: ApplicationConfig = ApplicationConfig()
    datasources: tuple[DataSourceConfig, ...] = ()
    gateways: tuple[GatewayConfig, ...] = ()
    rag: RAGConfig = RAGConfig()
    diagnostics: DiagnosticsConfig = DiagnosticsConfig()
    mcp: MCPConfig = MCPConfig()
    environments: tuple[RuntimeEnvironment, ...] = ()
    knowledge_sources: tuple[KnowledgeSourceConfig, ...] = ()
    knowledge_limits: KnowledgeLimits = KnowledgeLimits()
    correlation: CorrelationConfig = CorrelationConfig()

    @model_validator(mode="after")
    def references(self) -> Self:
        if len({s.id for s in self.knowledge_sources}) != len(self.knowledge_sources):
            raise ValueError("duplicate knowledge source")
        if any(
            s.metadata.environment not in {"global", *(e.id for e in self.environments)}
            for s in self.knowledge_sources
        ):
            raise ValueError("unknown knowledge environment")
        if len({environment.id for environment in self.environments}) != len(self.environments):
            raise ValueError("duplicate environment")
        sources = {source.id: source for source in self.datasources}
        if len(sources) != len(self.datasources):
            raise ValueError("duplicate datasource")
        if len({gateway.id for gateway in self.gateways}) != len(self.gateways):
            raise ValueError("duplicate gateway")
        for gateway in self.gateways:
            if gateway.adapter == "threescale" and gateway.datasource_id is None:
                environment = next(
                    (e for e in self.environments if e.id == gateway.environment_id), None
                )
                if (
                    gateway.datasource_id is not None
                    or environment is None
                    or environment.runtime is None
                ):
                    raise ValueError("3scale requires an explicit runtime environment")
                if gateway.enabled and not environment.enabled:
                    raise ValueError("enabled gateway requires enabled environment")
                if not any(
                    c.kind == "APIManager"
                    and c.group == "apps.3scale.net"
                    and c.version == "v1alpha1"
                    and c.plural == "apimanagers"
                    and c.namespaced
                    for c in environment.runtime.discovery.custom_resources
                ):
                    raise ValueError("3scale requires the APIManager allowlist")
                continue
            source = sources.get(gateway.datasource_id or "")
            if source is None or source.environment_id != gateway.environment_id:
                raise ValueError("invalid gateway datasource scope")
            if gateway.enabled and not source.enabled:
                raise ValueError("enabled gateway requires enabled datasource")
        return self
