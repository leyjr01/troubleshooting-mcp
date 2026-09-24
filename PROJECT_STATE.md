# PROJECT_STATE

## Current baseline
Current Sprint: 7 — Virtual Trace & Safe Probe Foundation, completed (PASS).
Commit: HEAD — feat: add virtual trace and safe probes (Sprint 7).
Base commit: 70e1b3d83b61b1a9e17e54f18ee2778463aad6bf (Sprint 6).
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
17 generic/Kubernetes/3scale/network definitions; typed states, coverage and expectations.
Explicit support/contradiction/missing evidence; LOW/MEDIUM/HIGH confidence with rationale.
Only SUPPORTED hypotheses promote to candidates for observed conditions.
Optional IncidentBundle.correlations/troubleshooting preserve existing fields.
No confirmed incident cause or LLM requirement; troubleshooting plans remain non-executable.
VirtualTraceBuilder preserves structural relationships, unresolved references and provenance.
ProbePlanner → ProbePolicy → injected executor → Evidence → same evaluator re-evaluation.
DNS/TCP/TLS/HTTP(S) implementation is outside the trace/probe/troubleshooting cores.

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
Trace/probes: trace_resource, trace_gateway_component, plan_probes,
execute_probe_plan, explain_trace.
33 tools; opt-in registration/permissions: src/agt_mcp/core/execution.py.
Diagnosis needs operation diagnose, troubleshooting.read, correlation.read and source ACLs.
diagnose_api accepts mapped runtime resources; unmapped IDs return explicit LIMITED.

## Constraints and security
Read-only sources; no Secret contents, external writes or remediation.
Probes default disabled/plan_only; execution requires probe.execute.active_readonly.
Approved configured endpoints + scoped resource membership + per-environment host/CIDR policy.
Validated DNS addresses pinned to sockets; bounded redirects revalidated; no credentials.
Network observations are externally observable; structural trace never proves connectivity.
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
Troubleshooting plans never execute. Probe plans need separate authorization and policy.
TCP/TLS evidence cannot fulfill missing Redis/database protocol evidence.
Defaults: 16 hypotheses, 8 candidates, 12 steps, 10 evidence/hypothesis, 12 components.
Cache: 16 results, 300-second TTL; correlation bounds and response-byte bounds also apply.

## Current test status
823 tests validated, 0 outstanding failures/skips; all 648 previous tests retained.
175 new: 136 probe/security, 28 trace units, 9 MCP integration, 2 documentation.
Full run once: 822 passed plus one checkpoint-field failure, corrected and revalidated.
Coverage 97.05%, branch-inclusive; gate >=96%; affected-file measurement refreshed.
Ruff lint/format (255 files), mypy (119 files), Bandit, dependencies: PASS.
Documentation/checkpoint: PASS. AGENTS.md unchanged. MCP integration: 73 passed total.

## Known limitations and next scope
Offline validation; no live cluster qualification. Metadata-based version detection.
Bounded non-atomic snapshots; no Admin API mapping; unmapped APIs explicitly LIMITED.
DNS/TCP/TLS/HTTP(S) from MCP host only; first approved address; system TLS trust.
No Redis/DB protocol probes, authenticated probes or automatic root-cause confirmation.
No proxy/credential headers, Secret decoding, response bodies or automatic redirects.
OS DNS worker may finish after cancellation; late results never create connections.
Local Git only; no remote fetch. Explicit programmatic refresh; CLI index starts empty.
Lexical embeddings, ephemeral indexes/caches, pattern-based redaction.
No mandatory Sprint 7 item pending.
Next recommended scope: authorized Redis/DB protocol probes and richer target mapping.

## Relevant ADRs and documents
0003 models; 0004 config/secrets; 0007 datasource; 0009 RAG; 0010 security;
0011 FastMCP; 0013 runtime; 0014 3scale; 0015 knowledge; 0016 trust boundary;
0017 correlation; 0018 hypothesis/troubleshooting; 0019 trace/safe probes, APPROVED.
Contracts: docs/architecture/troubleshooting-engine.md and hypothesis-model.md.
Safety/plans: docs/security/troubleshooting-safety.md and docs/architecture/troubleshooting-plan.md.
Trace/probes: docs/architecture/virtual-trace-probes.md; docs/security/probe-safety.md.
Validation: docs/development/sprint-7-validation.md.

## SPRINT CHECKPOINT
Sprint: 7
Commit: HEAD (single containing commit; resolve using command above).
Base commit: 70e1b3d83b61b1a9e17e54f18ee2778463aad6bf
Expected commit subject: feat: add virtual trace and safe probes (Sprint 7)
Status: PASS
Capabilities: virtual trace, safe DNS/TCP/TLS/HTTP(S), probe Evidence, five MCP tools.
Architecture: canonical bounded trace, approved endpoint policy, existing evaluator re-use.
New ADR: 0019, APPROVED; active read-only network observation is separately authorized.
Security: default disabled/plan_only; SSRF/redirect policy; no secrets/credentials/writes.
Tests: 823 validated, 0 outstanding failures/skips; 175 new, all 648 previous retained.
Validation: one full run; only affected checkpoint/coverage gates repeated.
Coverage: 97.05%, branch-inclusive; quality and documentation gates PASS.
Coverage gate: >=96%, branch-inclusive; no new exclusions or dependencies.
Limits: MCP-host vantage point, approved endpoints only, ephemeral cache, system trust.
Next: authorized protocol probes and richer target mapping; no automatic remediation.
