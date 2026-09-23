# ADR-0015 — Knowledge and RAG Architecture

## Status
APPROVED — Sprint 4, 2026-09-23.

## Context
Runtime facts, product classification and historical knowledge answer different
questions. Existing DataSourceAdapter.query returns runtime Evidence; using it for
documents would incorrectly promote retrieved text into operational observations.

## Decision
Keep Git as the internal source of truth and the vector index as derived data.
Introduce KnowledgeSourceAdapter for document snapshots, reads, changes, source
metadata and health. Preserve the generic DataSourceAdapter schema contract and
provide a local incident schema inspection implementation using SchemaDescription.
Keep knowledge-specific canonical models outside the generic core. Reuse Incident,
adding optional historical_root_cause/historical_remediation text without creating
Finding or Recommendation entities. Existing Incident fields remain compatible.

Reuse EmbeddingProvider, VectorStoreAdapter and Retriever. Extend the vector port
with MutableVectorIndex for atomic source replacement. Keep normalization,
chunking, embedding and storage injectable. Ship deterministic lexical embeddings
and an in-memory backend as offline validation implementations, not a production
vector database choice. Scores mean retrieval similarity, never diagnostic confidence.

Pin local Git reads to branch commit objects. Never checkout, clone, fetch or push.
Remote repository URLs are optional attribution/configuration metadata only.
Official documentation is curated local content with allowlisted attribution URLs.
Incident sources read local JSON rows through a declarative column mapping.
No SQL, HTTP fetch, model service or database connection is introduced.

Checksums cover normalized sanitized content plus effective metadata, not raw
secret values. IDs derive from source/path/section/sanitized content. Refresh skips
embedding unchanged documents, replaces changed chunks, removes deleted documents
and updates commit provenance. A versioned manifest records revision, checksums,
chunk IDs, embedding identity and pipeline settings. Index/manifest publication is
atomic per source within one service instance. Refresh is programmatic, outside
the public MCP tool set. Search only reads the current index.

## Consequences
Sources/categories and environment scopes remain explicit at every retrieval.
Indexes and manifests are process-local and reconstructible. A restart requires
explicit ingestion before search returns matches. Legacy rag.enabled remains a
disabled blueprint; knowledge_sources[].enabled is the implemented opt-in.
Failed refresh preserves the previous complete source index and reports degraded
health. There is no scheduler, live crawl or causal correlation engine.

## Alternatives Considered
Overloading Evidence would erase the fact/reference distinction. Selecting a hosted
embedding/vector vendor adds unnecessary credentials and external dependencies.
Automatic refresh during search would couple query latency and trust to source I/O.
Hybrid retrieval and production ranking remain replaceable future implementations.
