# Knowledge and RAG foundation

FastMCP → KnowledgeService → source snapshot → normalization/sanitization →
structure-aware chunker → EmbeddingProvider → MutableVectorIndex → Retriever.
Canonical knowledge results retain source category, effective environment, document,
section, revision, sanitized checksum and retrieval/ingestion timestamps.

Decisions: [ADR-0015](../adr/0015-knowledge-and-rag-architecture.md) and
[ADR-0016](../adr/0016-knowledge-security-trust-boundary.md).
Git remains authoritative; vectors, manifests and normalized document metadata are
rebuildable derived data. No query or refresh changes source files.

## Implemented MCP contracts

| Tool | Input | Permission |
| --- | --- | --- |
| search_internal_knowledge | query: RetrievalQuery | knowledge.search.internal |
| search_official_documentation | query: RetrievalQuery | knowledge.search.official |
| find_known_issue | query: RetrievalQuery | knowledge.issues.read |
| list_knowledge_sources | optional environment_id | knowledge.sources.read |
| get_knowledge_source_health | source_id, optional environment_id | knowledge.sources.read |

All accept optional environment_id and correlation_id. RetrievalQuery contains text,
repository_ids (source IDs), limit (top-k), source_types and optional filters:
environment, system, application, gateway_type, product, product_version,
document_type and tags. JSON arrays are supported under strict MCP validation.
Tool category restrictions cannot be widened by source_types. A product/version
filter is recommended for official documentation. Results preserve source type;
known issues have match_kind historical match / known error / runbook semantics.
Historical matches use the literal `similar prior incident`.

```json
{"query":{"text":"external Redis","limit":5,"filters":{"product":"3scale","product_version":"2.16"}}}
```

Search returns bounded chunks, relevance with score_kind=retrieval_similarity and
full knowledge provenance. It never returns a whole source document by default.
Ranking uses deterministic lexical hash embeddings, not a trained semantic model.
At most one chunk per document and one identical excerpt is returned, with stable
tie-breaking. Up to 100 candidates are considered; diversity can reduce result count.
Future hybrid retrieval/reranking replaces the retriever without changing sources.

## Separation and future correlation

KnowledgeReference is not Runtime Evidence. Incident historical_root_cause is a
recorded historical claim and never creates a root_cause_finding_id. Sprint 5 may
correlate runtime evidence, knowledge references and historical incidents through
an explicit Evidence Correlation Engine. No causal conclusion is generated here.

Refresh is an internal service operation; the public MCP interface is read-only.
Sources are scoped before ranking. Core and semantic gateway layers gain no Git,
HTTP, vector vendor, FastMCP or Kubernetes implementation imports.
