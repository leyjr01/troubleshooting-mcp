"""Knowledge application service: explicit refresh and read-only indexed search."""

import asyncio
from datetime import UTC, datetime

from agt_mcp.configuration.knowledge import KnowledgeLimits
from agt_mcp.core.errors import AuthorizationError, ConfigurationError, ResourceNotFound
from agt_mcp.core.operations import OperationContext
from agt_mcp.knowledge.models import (
    DocumentState,
    IngestionResult,
    KnowledgeDocument,
    KnowledgeHealth,
    KnowledgeIndexManifest,
    KnowledgeSource,
)
from agt_mcp.knowledge.pipeline import Chunker, DocumentNormalizer, checksum
from agt_mcp.knowledge.sources import KnowledgeSourceAdapter
from agt_mcp.rag.contracts import (
    EmbeddingProvider,
    KnowledgeChunk,
    KnowledgeResult,
    MutableVectorIndex,
    RetrievalQuery,
    RetrievalResult,
)
from agt_mcp.rag.local import LocalRetriever


class KnowledgeService:
    def __init__(
        self,
        sources: dict[str, KnowledgeSourceAdapter],
        limits: KnowledgeLimits,
        normalizer: DocumentNormalizer,
        chunker: Chunker,
        embedding: EmbeddingProvider,
        store: MutableVectorIndex,
        embedding_name: str = "deterministic-lexical-256-v1",
    ) -> None:
        self.sources, self.limits = dict(sources), limits
        self.normalizer, self.chunker = normalizer, chunker
        self.embedding, self.store = embedding, store
        self.embedding_name = embedding_name
        self.retriever = LocalRetriever(embedding, store)
        self.manifests: dict[str, KnowledgeIndexManifest] = {}
        self.documents: dict[str, dict[str, KnowledgeDocument]] = {}
        self.failures: set[str] = set()
        self._lock = asyncio.Lock()

    def source(self, identifier: str, context: OperationContext) -> KnowledgeSourceAdapter:
        source = self.sources.get(identifier)
        if source is None:
            raise ResourceNotFound()
        source.check_scope(context)
        return source

    def list_sources(self, context: OperationContext) -> tuple[KnowledgeSource, ...]:
        return tuple(
            s.source_metadata()
            for _, s in sorted(self.sources.items())
            if s.config.metadata.environment in {"global", context.environment_id}
        )

    async def refresh(
        self, identifier: str, context: OperationContext, *, rebuild: bool = False
    ) -> IngestionResult:
        source = self.source(identifier, context)
        async with asyncio.timeout(context.timeout_seconds), self._lock:
            try:
                snapshot = await source.snapshot(context)
                documents = {
                    raw.path: self.normalizer.normalize(raw, source.config)
                    for raw in snapshot.documents
                }
                if len(documents) != len(snapshot.documents):
                    raise ConfigurationError()
                previous = self.manifests.get(identifier)
                pipeline = checksum(
                    self.limits.model_dump_json()
                    + source.config.model_dump_json()
                    + self.embedding_name
                    + "normalizer-1/chunker-1/redaction-1"
                )
                before = previous.documents if previous else {}
                old_records = self.store.source_records(identifier)
                records: dict[str, tuple[KnowledgeChunk, tuple[float, ...]]] = {}
                states: dict[str, DocumentState] = {}
                new = changed = unchanged = 0
                for path, document in sorted(documents.items()):
                    prior = before.get(path)
                    same = (
                        not rebuild
                        and previous is not None
                        and previous.pipeline_version == pipeline
                        and prior is not None
                        and prior.checksum == document.source.content_sha256
                        and all(cid in old_records for cid in prior.chunk_ids)
                    )
                    chunks = self.chunker.chunk(document, snapshot.revision)
                    if same:
                        unchanged += 1
                        records.update({c.id: (c, old_records[c.id][1]) for c in chunks})
                    else:
                        new += prior is None
                        changed += prior is not None
                        vectors = await self.embedding.embed(tuple(c.text for c in chunks), context)
                        if len(vectors) != len(chunks):
                            raise ConfigurationError()
                        records.update({c.id: (c, v) for c, v in zip(chunks, vectors, strict=True)})
                    states[path] = DocumentState(
                        checksum=document.source.content_sha256,
                        chunk_ids=tuple(c.id for c in chunks),
                    )
                    if len(records) > self.limits.max_total_chunks_per_ingestion:
                        raise ConfigurationError()
                    await asyncio.sleep(0)
                manifest = KnowledgeIndexManifest(
                    source_id=identifier,
                    source_revision=snapshot.revision,
                    branch=source.config.branch if source.config.type == "git" else None,
                    documents=states,
                    embedding_provider=self.embedding_name,
                    pipeline_version=pipeline,
                    created_at=datetime.now(UTC),
                )
                # No awaits between replacement and manifest publication: atomic per event loop.
                self.store.replace_source(identifier, records)
                self.manifests[identifier] = manifest
                self.documents[identifier] = documents
                self.failures.discard(identifier)
                return IngestionResult(
                    source_id=identifier,
                    new=new,
                    changed=changed,
                    unchanged=unchanged,
                    deleted=len(before.keys() - states.keys()),
                    chunks=len(records),
                )
            except Exception:
                self.failures.add(identifier)
                raise

    async def health(self, identifier: str, context: OperationContext) -> KnowledgeHealth:
        source = self.source(identifier, context)
        manifest = self.manifests.get(identifier)
        try:
            async with asyncio.timeout(context.timeout_seconds):
                revision = await source.revision(context)
        except Exception:
            return KnowledgeHealth(source_id=identifier, status="UNAVAILABLE")
        return KnowledgeHealth(
            source_id=identifier,
            status="DEGRADED"
            if identifier in self.failures
            else "NOT_INDEXED"
            if manifest is None
            else "STALE"
            if manifest.source_revision != revision
            else "HEALTHY",
            source_revision=revision,
            indexed_revision=manifest.source_revision if manifest else None,
        )

    def document_metadata(
        self, source_id: str, path: str, context: OperationContext
    ) -> KnowledgeDocument:
        self.source(source_id, context)
        document = self.documents.get(source_id, {}).get(path)
        if document is None:
            raise ResourceNotFound()
        if document.source.environment_id not in {"global", context.environment_id}:
            raise AuthorizationError()
        return document.model_copy(update={"text": "", "incident": None})

    async def search(self, query: RetrievalQuery, context: OperationContext) -> RetrievalResult:
        if query.filters and query.filters.environment not in {"global", context.environment_id}:
            raise AuthorizationError()
        for identifier in query.repository_ids:
            self.source(identifier, context)
        allowed = tuple(s.id for s in self.list_sources(context))
        if not allowed:
            return RetrievalResult(results=())
        query = query.model_copy(
            update={
                "repository_ids": query.repository_ids or allowed,
                "limit": min(query.limit, self.limits.max_top_k, context.max_items),
            }
        )
        async with asyncio.timeout(context.timeout_seconds):
            matches = await self.retriever.results(query, context)
        accepted: list[KnowledgeResult] = []
        for match in matches:
            candidate = RetrievalResult(results=tuple([*accepted, match]))
            if len(candidate.model_dump_json().encode()) > min(
                self.limits.max_result_bytes, context.max_payload_bytes
            ):
                return RetrievalResult(results=tuple(accepted), truncated=True)
            accepted.append(match)
        return RetrievalResult(results=tuple(accepted))
