"""Read-only operation vocabulary shared by ports and authorization."""

from enum import StrEnum

from pydantic import Field

from agt_mcp.core.models import Identifier, Model, Text


class Operation(StrEnum):
    KNOWLEDGE_SEARCH = "knowledge_search"
    KNOWLEDGE_SOURCES = "knowledge_sources"
    COMPONENTS = "gateway_components"
    GATEWAY_TOPOLOGY = "gateway_topology"
    HEALTH = "health"
    QUERY = "query"
    DISCOVER_SCHEMA = "discover_schema"
    DISCOVER_GATEWAY = "discover_gateway"
    PRODUCTS = "products"
    BACKENDS = "backends"
    ROUTES = "routes"
    POLICIES = "policies"
    DEPENDENCIES = "dependencies"
    LOGS = "logs"
    TRACE_REQUEST = "trace_request"


class OperationContext(Model):
    environment_id: Identifier
    principal_id: Identifier
    request_id: Identifier
    correlation_id: Identifier
    timeout_seconds: float = Field(gt=0, le=300)
    max_items: int = Field(default=100, ge=1, le=1000)
    max_payload_bytes: int = Field(default=65536, ge=1, le=1048576)


class Health(Model):
    status: str
    detail_code: Identifier


class Query(Model):
    """Logical collection and bound scalar filters, never SQL or shell text."""

    collection: Identifier
    filters: dict[str, str | int | bool] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=1000)
    cursor: str | None = None


class Column(Model):
    name: Identifier
    data_type: Text
    nullable: bool


class SchemaTable(Model):
    schema_name: Identifier
    name: Identifier
    columns: tuple[Column, ...]
    relationships: tuple[Text, ...] = ()
    indexes: tuple[Text, ...] = ()


class SchemaDescription(Model):
    tables: tuple[SchemaTable, ...]
    truncated: bool = False
