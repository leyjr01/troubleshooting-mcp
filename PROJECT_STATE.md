# PROJECT_STATE

## Current baseline
Current Sprint: 5 — Evidence Correlation Engine, completed (PASS).
Commit: HEAD — feat: add evidence correlation engine (Sprint 5).
Base commit: ec6211e (Sprint 4); exactly one sprint commit follows this base.
Resolve with git log -1 --format="%H %s" -- PROJECT_STATE.md.
The checkpoint uses its containing commit reference to avoid a self-referential hash.

## Architecture status
FastMCP → application services → adapters → canonical models.
Runtime evidence, semantic topology, knowledge references and inference stay separate.
Knowledge: source snapshot → normalization/redaction → chunking → embedding → index → retrieval.
Git is authoritative; index/manifest are derived, mutable, process-local and rebuildable.
Correlation: canonical snapshot → bounded deterministic rules → optional scoped references.
Gateway-specific composition stays outside the engine; no causal findings are generated.

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
- EvidenceCorrelationEngine with injectable ports, clock, bounds and rule registry.
- Ten relation types, explicit time windows, timeline and support/contradiction lineage.
- Version-aware knowledge/history references; optional IncidentBundle.correlations.
- Bounded principal/environment cache with TTL and permission rechecks.

## Current MCP tools
System/inventory: system_health, list_capabilities, list_environments, list_gateways,
list_datasources, inspect_datasource, discover_gateway.
Runtime: discover_environment, inspect_resource, inspect_events,
find_related_resources, get_resource_topology.
Semantic: get_gateway_topology, inspect_gateway_component, get_gateway_dependencies.
Knowledge: search_internal_knowledge, search_official_documentation, find_known_issue,
list_knowledge_sources, get_knowledge_source_health.
Correlation: correlate_evidence, get_correlation_timeline, explain_correlation.
Twenty-three tools; opt-in registration and permissions: src/agt_mcp/core/execution.py.

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
- Correlation core has no gateway implementation imports; all external text stays inert.
- Missing/stale/future timestamps warn; optional enrichment failures return PARTIAL.
- Contradictions survive candidate limits; mirrored facts cannot raise confidence.

## Current test status
556 passed, 0 failed, 0 skipped; branch-inclusive coverage 96.34% (gate >=95%).
All 448 previous tests preserved; 108 correlation tests added (96 unit, 12 integration).
MCP integration: 49 passed. Dedicated security modules: 88 passed; categories overlap.
Ruff lint/format, mypy (92 files), Bandit, pip check and documentation: PASS.

## Known limitations
Offline validation; no live cluster qualification. Version detection uses metadata.
External endpoints unresolved; runtime snapshots bounded and non-atomic.
- Git CLI required; clone/fetch/remote credential resolution not implemented.
- Explicit programmatic refresh in the serving Runtime; default CLI index starts empty.
- Index/manifest in memory; rebuild after restart. No scheduler/public refresh tool.
- Embeddings are lexical hash vectors, not a production semantic model or vendor choice.
- Curated snapshots are bounded, not atomic against concurrent local file edits.
- Redaction is pattern-based; reviewed/minimized inputs remain necessary.
- Correlation IDs expire; bounded process-local cache does not cross worker/restart boundaries.
- No causal diagnosis or connectivity probes; runtime source alone cannot establish HIGH.

## Pending next-step items
No mandatory Sprint 5 item pending.
Next recommended scope: Sprint 6 — Hypothesis & Troubleshooting Engine.
Production persistence, remote sources and trained embeddings remain future scope.

## Relevant ADR index
0003 canonical models; 0004 configuration/secrets; 0007 datasource contracts;
0009 RAG separation; 0010 read-only security; 0011 FastMCP;
0013 runtime boundary; 0014 3scale semantic discovery;
0015 Knowledge and RAG Architecture; 0016 Knowledge Security and Trust Boundary;
0017 Evidence Correlation Engine, APPROVED.
Details: docs/architecture/evidence-correlation.md and docs/architecture/correlation-rules.md.
Validation: docs/development/sprint-5-validation.md.

## SPRINT CHECKPOINT
Sprint: 5
Commit: HEAD (the single commit containing this checkpoint; resolve using the command above).
Base commit: ec6211e
Expected commit subject: feat: add evidence correlation engine (Sprint 5)
Status: PASS
Capabilities added: ten correlation types, timeline, contradictions, three MCP tools.
Architecture changes: injected canonical providers/rules/clock; IncidentBundle correlations.
New ADR: 0017, APPROVED.
Security: scoped cache/permissions; installation isolation; inert documents; no secret access.
Tests: 556 passed, 0 failed/skipped; 108 new; all quality gates PASS.
Coverage: 96.34%, branch-inclusive; gate >=95%; no added exclusions.
Known limitations: bounded non-atomic snapshots; lexical references; ephemeral scoped cache.
Next: Sprint 6 — Hypothesis & Troubleshooting Engine; no automatic remediation.
