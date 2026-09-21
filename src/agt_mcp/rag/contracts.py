"""Federated retrieval contracts; no ingestion, embedding or vector implementation."""

from typing import Protocol

from pydantic import Field

from agt_mcp.core.models import Identifier, Model, Provenance, Text
from agt_mcp.core.operations import OperationContext


class KnowledgeChunk(Model):
    id: Identifier
    environment_id: Identifier
    text: Text
    source: Provenance
    access_labels: tuple[Identifier, ...]
    revision: Identifier


class RetrievalQuery(Model):
    text: Text
    repository_ids: tuple[Identifier, ...]
    limit: int = Field(default=10, ge=1, le=100)


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
