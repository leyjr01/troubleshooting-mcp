# PROJECT_STATE

## Current baseline
Current Sprint: 4 — Knowledge and RAG foundation, completed.
Commit: HEAD — feat: add knowledge and RAG foundation (Sprint 4).
Base commit: ca83d25 (Sprint 3); exactly one sprint commit follows this base.
Resolve with git log -1 --format="%H %s" -- PROJECT_STATE.md.
The checkpoint uses its containing commit reference to avoid a self-referential hash.

## Architecture status
FastMCP → application services → adapters → canonical models.
Runtime evidence, semantic topology, knowledge references and inference stay separate.
Knowledge: source snapshot → normalization/redaction → chunking → embedding → index → retrieval.
Git is authoritative; index/manifest are derived, mutable, process-local and rebuildable.

## Implemented capabilities and adapters
- FastMCP STDIO and local HTTP, authorization, audit and bounded responses.
- Kubernetes/OpenShift RuntimeAdapter, Route/EndpointSlice and safe custom resources.
- ThreeScaleGatewayAdapter, APIManager roots, 2.16 profile and semantic topology.
- Memory gateway/data source, credential provider contracts, mapping/RAG contracts.
- GitKnowledgeSource: committed local blobs, configured branch/subpath/include prefixes.
- CuratedLocalSource: versioned official documents; attribution URLs only, no HTTP fetch.
- LocalIncidentSource: JSON rows, canonical Incident mapping and schema inspection.
- Deterministic lexical EmbeddingProvider, InMemoryVectorStore and LocalRetriever.
- Incremental new/changed/unchanged/deleted ingestion; atomic source replacement.
- Manifest schema 1.0.0: source revision, branch, checksums, chunks and pipeline identity.

## Current MCP tools
System/inventory: system_health, list_capabilities, list_environments, list_gateways,
list_datasources, inspect_datasource, discover_gateway.
Runtime: discover_environment, inspect_resource, inspect_events,
find_related_resources, get_resource_topology.
Semantic: get_gateway_topology, inspect_gateway_component, get_gateway_dependencies.
Knowledge: search_internal_knowledge, search_official_documentation, find_known_issue,
list_knowledge_sources, get_knowledge_source_health.
Twenty tools; opt-in registration and permissions: src/agt_mcp/core/execution.py.

## Important constraints and security invariants
- Read-only sources; no Kubernetes Secret contents or Secret list permission.
- Core has no FastMCP/Kubernetes imports; semantic layer has no Kubernetes imports.
- Environment isolation, evidence/provenance and deterministic ordering.
- No causal diagnosis, remediation, live DB/Redis probes or Admin API access.
- Core has no Git or vector vendor implementation imports.
- All knowledge is untrusted_data; document instructions never execute.
- Sanitize before embedding/indexing; document checksums cover sanitized content + metadata.
- Filter environment/source/category before ranking and recheck at retrieval boundary.
- Global is explicit; scoped source front matter cannot broaden environment access.
- Similarity is not diagnostic confidence; historical causes are not current findings.

## Current test status
448 passed, 0 failed, 0 skipped; branch-inclusive coverage 95.87% (gate >=94%).
All 339 previous tests preserved; 109 added.
Knowledge unit tests: 97; MCP integration: 37 including 12 knowledge tests.
Security category: 103 (overlaps other totals); checkpoint/examples: 2 passed.
Ruff lint/format, mypy (83 files), Bandit, pip check and documentation: PASS.

## Known limitations
Offline validation; no live cluster qualification. Version detection uses metadata.
External endpoints unresolved; runtime snapshots bounded and non-atomic.
- Git CLI required; clone/fetch/remote credential resolution not implemented.
- Explicit programmatic refresh in the serving Runtime; default CLI index starts empty.
- Index/manifest in memory; rebuild after restart. No scheduler/public refresh tool.
- Embeddings are lexical hash vectors, not a production semantic model or vendor choice.
- Curated snapshots are bounded, not atomic against concurrent local file edits.
- Redaction is pattern-based; reviewed/minimized inputs remain necessary.

## Pending next-step items
No mandatory Sprint 4 item pending.
Next recommended scope: Sprint 5 — Evidence Correlation Engine with explicit evidence links.
Production persistence, remote sources and trained embeddings remain future scope.

## Relevant ADR index
0003 canonical models; 0004 configuration/secrets; 0007 datasource contracts;
0009 RAG separation; 0010 read-only security; 0011 FastMCP;
0013 runtime boundary; 0014 3scale semantic discovery;
0015 Knowledge and RAG Architecture; 0016 Knowledge Security and Trust Boundary.
Details: docs/architecture/knowledge-rag.md and docs/development/knowledge-ingestion.md.

## SPRINT CHECKPOINT
Sprint: 4
Commit: HEAD (the single commit containing this checkpoint; resolve using the command above).
Base commit: ca83d25
Expected commit subject: feat: add knowledge and RAG foundation (Sprint 4)
Status: PASS
Capabilities added: Git/local official/incident sources; ingestion; retrieval; five MCP tools.
Architecture changes: KnowledgeSourceAdapter and MutableVectorIndex; reuse existing RAG ports.
New ADRs: 0015 and 0016, APPROVED.
Security changes: pre-index redaction, inert documents, scoped/category-filtered retrieval.
Tests: 448 passed; coverage 95.87%; all quality gates PASS.
Known limitations: local sources, explicit refresh, in-memory index, lexical embeddings.
Next: Sprint 5 — Evidence Correlation Engine; no automatic remediation.
