# PROJECT_STATE

## Current baseline
Current Sprint: 6 — Hypothesis & Troubleshooting Engine, completed (PASS).
Commit: HEAD — feat: add hypothesis troubleshooting engine (Sprint 6).
Base commit: a3e0c6d7ccaf8fa7d4ecc15a5a1c3235da4528ef (Sprint 5).
Exactly one sprint commit follows this base.
Resolve with git log -1 --format="%H %s" -- PROJECT_STATE.md.
Containing commit reference avoids a self-referential hash.

## Architecture and capabilities
FastMCP → services → adapters → canonical models. Runtime, knowledge, history and
inference remain separate. Core imports no vendor implementation.
Kubernetes/OpenShift read-only discovery; 3scale/APIcast semantic topology, 2.16 profile.
Local committed Git, curated documents and incident sources; sanitized lexical retrieval.
Indexes/manifests are derived, rebuildable and process-local; Git remains authoritative.
Correlation supplies one bounded snapshot, timeline, provenance and scoped references.
Troubleshooting: injected catalog → generation → evaluation → candidates → safe plan.
15 generic/Kubernetes/3scale definitions; typed runtime states, coverage and expectations.
Explicit support/contradiction/missing evidence; LOW/MEDIUM/HIGH confidence with rationale.
Only SUPPORTED hypotheses promote to candidates for observed conditions.
Optional IncidentBundle.correlations/troubleshooting preserve existing fields.
No confirmed incident cause, LLM requirement or plan execution.

## Current MCP tools
System/inventory: system_health, list_capabilities, list_environments, list_gateways,
list_datasources, inspect_datasource, discover_gateway.
Runtime: discover_environment, inspect_resource, inspect_events,
find_related_resources, get_resource_topology.
Semantic: get_gateway_topology, inspect_gateway_component, get_gateway_dependencies.
Knowledge: search_internal_knowledge, search_official_documentation, find_known_issue,
list_knowledge_sources, get_knowledge_source_health.
Correlation: correlate_evidence, get_correlation_timeline, explain_correlation.
Troubleshooting: diagnose_component, diagnose_gateway, diagnose_api,
explain_hypothesis, get_troubleshooting_plan.
28 tools; opt-in registration/permissions: src/agt_mcp/core/execution.py.
Diagnosis needs operation diagnose, troubleshooting.read, correlation.read and source ACLs.
diagnose_api accepts mapped runtime resources; unmapped IDs return explicit LIMITED.

## Constraints and security
Read-only sources; no Secret contents, external writes, probes or remediation.
Core has no FastMCP/Kubernetes/Git/vector implementations; semantic layer has no SDK.
Correlation/troubleshooting cores have no 3scale implementation imports.
Environment/installation isolation; scoped principal caches with permission rechecks.
All external knowledge is untrusted; sanitize before indexing, filter before ranking.
History/similarity never establish present causes or become runtime supporting evidence.
Missing/stale/future observations and partial inventory cannot silently prove absence.
Contradictions survive limits; duplicate facts cannot raise confidence.
Structural HIGH is limited to independently observed facts, per ADR-0018.
External Redis/DB without probes remain inconclusive; optional Zync causes no false failure.
User-reported symptoms stay separate from evidence-backed observed symptoms.
Plans never execute; future passive probes are unavailable placeholders.
Defaults: 16 hypotheses, 8 candidates, 12 steps, 10 evidence/hypothesis, 12 components.
Cache: 16 results, 300-second TTL; correlation bounds and response-byte bounds also apply.

## Current test status
648 passed, 0 failed/skipped; branch-inclusive coverage 96.65% (gate >=95.5%).
All 556 previous tests preserved; 92 new (40 hypothesis, 37 service/security, 15 MCP).
MCP integration: 64 passed. Dedicated security: 112 passed; categories overlap.
Ruff lint/format (226 files), strict mypy (104 files), Bandit, pip check: PASS.
Documentation links, ADR structure and checkpoint: PASS. AGENTS.md unchanged.

## Known limitations and next scope
Offline validation; no live cluster qualification. Metadata-based version detection.
Bounded non-atomic snapshots; no Admin API mapping; unmapped APIs explicitly LIMITED.
No DNS/TCP/TLS/HTTP/Redis/DB probes or automatic root-cause confirmation.
Local Git only; no remote fetch. Explicit programmatic refresh; CLI index starts empty.
Lexical embeddings, ephemeral indexes/caches, pattern-based redaction.
No mandatory Sprint 6 items pending.
Next: Sprint 7 — Virtual Trace & Active/Passive Probe Foundation.

## Relevant ADRs and documents
0003 models; 0004 config/secrets; 0007 datasource; 0009 RAG; 0010 security;
0011 FastMCP; 0013 runtime; 0014 3scale; 0015 knowledge; 0016 trust boundary;
0017 correlation; 0018 hypothesis/troubleshooting architecture, APPROVED.
Contracts: docs/architecture/troubleshooting-engine.md and hypothesis-model.md.
Safety/plans: docs/security/troubleshooting-safety.md and docs/architecture/troubleshooting-plan.md.
Validation: docs/development/sprint-6-validation.md.

## SPRINT CHECKPOINT
Sprint: 6
Commit: HEAD (single containing commit; resolve using command above).
Base commit: a3e0c6d7ccaf8fa7d4ecc15a5a1c3235da4528ef
Expected commit subject: feat: add hypothesis troubleshooting engine (Sprint 6)
Status: PASS
Capabilities: 15 definitions, deterministic evaluation/candidates, five MCP tools.
Architecture: one correlation snapshot, injected providers, additive IncidentBundle field.
New ADR: 0018, APPROVED; structural HIGH scoped to observed conditions only.
Security: scoped ACL/cache, inert text; no secrets/probes/writes/plan execution.
Tests: 648 passed, 0 failed/skipped; 92 added; all 556 previous preserved.
Coverage: 96.65%, branch-inclusive; gate >=95.5%; no added exclusions.
Quality: lint, formatting, mypy, Bandit, dependencies, documentation PASS.
Limits: bounded non-atomic snapshots, lexical retrieval, ephemeral cache, unmapped APIs LIMITED.
Next: Sprint 7 — Virtual Trace & Active/Passive Probe Foundation.
