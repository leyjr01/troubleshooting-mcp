"""Federated retrieval contracts; no ingestion, embedding or vector implementation."""

from collections.abc import Mapping
from typing import Literal, Protocol

from pydantic import Field, field_validator

from agt_mcp.core.models import Identifier, Model, Provenance, Text
from agt_mcp.core.operations import OperationContext
from agt_mcp.knowledge.models import KnowledgeMetadata, KnowledgeProvenance, SourceType


class KnowledgeChunk(Model):
    id: Identifier
    environment_id: Identifier
    text: Text
    source: KnowledgeProvenance | Provenance
    access_labels: tuple[Identifier, ...]
    revision: Identifier
    title: Text = "document"
    source_type: SourceType = SourceType.INTERNAL_KNOWLEDGE
    metadata: KnowledgeMetadata = KnowledgeMetadata()
    document_id: Identifier | None = None
    trust: Literal["untrusted_data"] = "untrusted_data"


class RetrievalQuery(Model):
    text: Text
    repository_ids: tuple[Identifier, ...] = ()
    limit: int = Field(default=10, ge=1, le=100)
    source_types: tuple[SourceType, ...] = ()
    filters: KnowledgeMetadata | None = None

    @field_validator("repository_ids", mode="before")
    @classmethod
    def json_repositories(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value

    @field_validator("source_types", mode="before")
    @classmethod
    def json_categories(cls, value: object) -> object:
        return tuple(SourceType(v) for v in value) if isinstance(value, (list, tuple)) else value


class KnowledgeResult(Model):
    chunk: KnowledgeChunk
    relevance: float = Field(ge=-1, le=1, allow_inf_nan=False)
    score_kind: Literal["retrieval_similarity"] = "retrieval_similarity"
    match_kind: str = "knowledge_reference"


class RetrievalResult(Model):
    results: tuple[KnowledgeResult, ...]
    truncated: bool = False


class EmbeddingProvider(Protocol):
    async def embed(
        self, texts: tuple[str, ...], context: OperationContext
    ) -> tuple[tuple[float, ...], ...]: ...


class VectorStoreAdapter(Protocol):
    async def search(
        self, vector: tuple[float, ...], query: RetrievalQuery, context: OperationContext
    ) -> tuple[KnowledgeChunk, ...]: ...


class Retriever(Protocol):
    async def retrieve(
        self, query: RetrievalQuery, context: OperationContext
    ) -> tuple[KnowledgeChunk, ...]: ...


class MutableVectorIndex(VectorStoreAdapter, Protocol):
    def source_records(
        self, source_id: str
    ) -> dict[str, tuple[KnowledgeChunk, tuple[float, ...]]]: ...

    def replace_source(
        self, source_id: str, records: Mapping[str, tuple[KnowledgeChunk, tuple[float, ...]]]
    ) -> None: ...
