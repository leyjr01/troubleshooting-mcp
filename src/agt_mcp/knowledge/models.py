"""Canonical knowledge references, deliberately separate from runtime Evidence."""

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator

from agt_mcp.core.models import Identifier, Incident, Model, Provenance, Text


class SourceType(StrEnum):
    INTERNAL_KNOWLEDGE = "INTERNAL_KNOWLEDGE"
    OFFICIAL_DOCUMENTATION = "OFFICIAL_DOCUMENTATION"
    HISTORICAL_INCIDENT = "HISTORICAL_INCIDENT"
    RUNBOOK = "RUNBOOK"
    ARCHITECTURE = "ARCHITECTURE"
    KNOWN_ERROR = "KNOWN_ERROR"
    CMDB = "CMDB"
    OTHER_EXTERNAL_SOURCE = "OTHER_EXTERNAL_SOURCE"


class KnowledgeMetadata(Model):
    environment: Identifier = "global"
    system: Identifier | None = None
    application: Identifier | None = None
    gateway_type: Identifier | None = None
    product: Text | None = None
    product_version: Identifier | None = None
    document_type: Identifier | None = None
    tags: tuple[Identifier, ...] = ()

    @field_validator("tags", mode="before")
    @classmethod
    def json_tags(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value


class KnowledgeProvenance(Provenance):
    source_type: SourceType
    repository: Text | None = None
    path: Text
    document_id: Identifier
    section: Text = "document"
    version: Identifier | None = None
    commit: Identifier | None = None
    branch: Text | None = None
    ingested_at: AwareDatetime
    metadata: KnowledgeMetadata


class KnowledgeDocument(Model):
    id: Identifier
    title: Text
    text: str = Field(max_length=1048576)
    format: Literal[".md", ".txt", ".yaml", ".yml", ".json"]
    source: KnowledgeProvenance
    incident: Incident | None = None
    trust: Literal["untrusted_data"] = "untrusted_data"


class KnowledgeSource(Model):
    id: Identifier
    source_type: SourceType
    environment: Identifier
    capabilities: tuple[Identifier, ...]
    usage: tuple[Identifier, ...] = ("rag",)


class DocumentState(Model):
    checksum: str
    chunk_ids: tuple[Identifier, ...]


class KnowledgeIndexManifest(Model):
    source_id: Identifier
    source_revision: Text
    branch: Text | None = None
    documents: dict[str, DocumentState]
    embedding_provider: Identifier
    pipeline_version: Text
    knowledge_index_schema_version: Literal["1.0.0"] = "1.0.0"
    created_at: AwareDatetime


class IngestionResult(Model):
    source_id: Identifier
    new: int
    changed: int
    unchanged: int
    deleted: int
    chunks: int


class KnowledgeHealth(Model):
    source_id: Identifier
    status: Literal["HEALTHY", "DEGRADED", "STALE", "UNAVAILABLE", "NOT_INDEXED"]
    indexed_revision: Text | None = None
    source_revision: Text | None = None


class SourceDocument(Model):
    """Internal adapter transfer object; never an MCP response or index record."""

    path: str
    content: bytes = Field(repr=False)
    revision: str
    retrieved_at: AwareDatetime
    incident: Incident | None = None


class SourceSnapshot(Model):
    revision: str
    documents: tuple[SourceDocument, ...]


class SourceChanges(Model):
    new: tuple[str, ...]
    changed: tuple[str, ...]
    unchanged: tuple[str, ...]
    deleted: tuple[str, ...]
