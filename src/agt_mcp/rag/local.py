"""Deterministic lexical embeddings and replaceable, scoped in-memory vector index."""

import hashlib
import math
import re
from collections.abc import Mapping

from agt_mcp.core.errors import ConfigurationError
from agt_mcp.core.operations import OperationContext
from agt_mcp.rag.contracts import (
    EmbeddingProvider,
    KnowledgeChunk,
    KnowledgeResult,
    RetrievalQuery,
    VectorStoreAdapter,
)


class DeterministicFakeEmbeddingProvider:
    """Test/offline lexical similarity, not production semantic understanding."""

    name = "deterministic-lexical-256-v1"

    async def embed(
        self, texts: tuple[str, ...], context: OperationContext
    ) -> tuple[tuple[float, ...], ...]:
        vectors = []
        for text in texts:
            vector = [0.0] * 256
            for token in re.findall(r"\w+", text.casefold()):
                index = int.from_bytes(hashlib.sha256(token.encode()).digest()[:4], "big") % 256
                vector[index] += 1
            length = math.sqrt(sum(value * value for value in vector)) or 1.0
            vectors.append(tuple(value / length for value in vector))
        return tuple(vectors)


def visible(chunk: KnowledgeChunk, query: RetrievalQuery, context: OperationContext) -> bool:
    if chunk.environment_id not in {"global", context.environment_id}:
        return False
    if chunk.access_labels and not set(chunk.access_labels) & {"global", context.environment_id}:
        return False
    if query.repository_ids and chunk.source.source_id not in query.repository_ids:
        return False
    if query.source_types and chunk.source_type not in query.source_types:
        return False
    if query.filters:
        for key, value in query.filters.model_dump(exclude_unset=True).items():
            observed = getattr(chunk.metadata, key)
            if key == "tags":
                if not set(value) <= set(observed):
                    return False
            elif value is not None and value != observed:
                return False
    return True


class InMemoryVectorStore:
    def __init__(self) -> None:
        self.records: dict[str, tuple[KnowledgeChunk, tuple[float, ...]]] = {}

    def source_records(self, source_id: str) -> dict[str, tuple[KnowledgeChunk, tuple[float, ...]]]:
        return {k: r for k, r in self.records.items() if r[0].source.source_id == source_id}

    def replace_source(
        self, source_id: str, records: Mapping[str, tuple[KnowledgeChunk, tuple[float, ...]]]
    ) -> None:
        if any(c.source.source_id != source_id or k != c.id for k, (c, _) in records.items()):
            raise ConfigurationError()
        dimensions = {len(v) for _, v in records.values()}
        if len(dimensions) > 1 or any(
            not v or not all(math.isfinite(x) for x in v) for _, v in records.values()
        ):
            raise ConfigurationError()
        retained = {k: r for k, r in self.records.items() if r[0].source.source_id != source_id}
        self.records = {**retained, **records}

    async def search(
        self, vector: tuple[float, ...], query: RetrievalQuery, context: OperationContext
    ) -> tuple[KnowledgeChunk, ...]:
        return tuple(chunk for _, chunk in self.ranked(vector, query, context)[: query.limit])

    def ranked(
        self, vector: tuple[float, ...], query: RetrievalQuery, context: OperationContext
    ) -> list[tuple[float, KnowledgeChunk]]:
        ranked = []
        for chunk, embedding in self.records.values():
            if not visible(chunk, query, context):
                continue
            if len(vector) != len(embedding):
                raise ConfigurationError()
            denominator = math.sqrt(sum(x * x for x in vector) * sum(x * x for x in embedding))
            score = (
                sum(a * b for a, b in zip(vector, embedding, strict=True)) / denominator
                if denominator
                else 0.0
            )
            if score > 0:
                ranked.append((min(1.0, max(-1.0, score)), chunk))
        return sorted(ranked, key=lambda item: (-item[0], item[1].id))


class LocalRetriever:
    def __init__(self, embedding: EmbeddingProvider, store: VectorStoreAdapter) -> None:
        self.embedding, self.store = embedding, store

    async def retrieve(
        self, query: RetrievalQuery, context: OperationContext
    ) -> tuple[KnowledgeChunk, ...]:
        vector = (await self.embedding.embed((query.text,), context))[0]
        chunks = await self.store.search(vector, query, context)
        # Defense in depth for replacement stores: recheck canonical ACL/filter fields.
        return tuple(c for c in chunks if visible(c, query, context))[: query.limit]

    async def results(
        self, query: RetrievalQuery, context: OperationContext
    ) -> tuple[KnowledgeResult, ...]:
        chunks = await self.retrieve(query.model_copy(update={"limit": 100}), context)
        vectors = await self.embedding.embed((query.text, *(c.text for c in chunks)), context)
        results = []
        seen_documents: set[str] = set()
        seen_text: set[str] = set()
        for chunk, vector in zip(chunks, vectors[1:], strict=True):
            if chunk.document_id in seen_documents or chunk.text in seen_text:
                continue
            seen_documents.add(chunk.document_id or chunk.id)
            seen_text.add(chunk.text)
            denominator = math.sqrt(sum(x * x for x in vector) * sum(x * x for x in vectors[0]))
            score = (
                sum(a * b for a, b in zip(vector, vectors[0], strict=True)) / denominator
                if denominator
                else 0.0
            )
            results.append(
                KnowledgeResult(
                    chunk=chunk,
                    relevance=min(1.0, max(-1.0, score)),
                    match_kind={
                        "HISTORICAL_INCIDENT": "similar prior incident",
                        "KNOWN_ERROR": "known error",
                        "RUNBOOK": "runbook",
                    }.get(chunk.source_type.value, "knowledge_reference"),
                )
            )
        return tuple(results[: query.limit])
