# PROJECT_STATE

## Current baseline
Current Sprint: 8 — Observability Correlation & Evidence Enrichment, completed (PASS).
Commit: HEAD — feat: add observability evidence correlation (Sprint 8).
Base commit: 14cbc5f14c5072300180cfe6a31e6aab737bcd2f (Sprint 7).
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
ObservabilityAdapter: InMemory logs/metrics/traces and Prometheus-compatible HTTP metrics.
Scoped UTC queries → redacted Evidence → existing correlation refresh and evaluator.
Events/ProbeEvidence reuse; descriptive timeline, cached VirtualTrace enrichment, partial sources.
Impact: HIGH; external integrations, secret handling, volume and diagnostic evidence.

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
Observability: inspect_observability, inspect_logs, inspect_metrics, inspect_trace,
build_evidence_timeline. 38 tools; opt-in: src/agt_mcp/core/execution.py.
Diagnosis needs operation diagnose, troubleshooting.read, correlation.read and source ACLs.
diagnose_api accepts mapped runtime resources; unmapped IDs return explicit LIMITED.

## Constraints and security
Read-only sources; no Secret contents, external writes or remediation.
Observability sources disabled by default; exact configured resource/provider bindings.
Signal permissions: observability.logs/metrics/traces/timeline.read, plus runtime/correlation ACLs.
No raw PromQL/URLs in tools; safe configured HTTP GET, pinned DNS and verified TLS.
Observability credentials resolve via CredentialProvider after TLS; probes remain unauthenticated.
Untrusted telemetry redacted before truncation/hashing; no external text executes instructions.
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
Sprint 7 baseline: 823 validated; coverage 97.05%, unchanged branch-inclusive gate >=96%.
Sprint 8 baseline: 29 passed. L1: models 39, service 38, protocol 47, transport 31, MCP 8.
L2: 108 passed; prior valid integration/security results reused.
Final single full run: 995 passed, 0 failed/errors/skipped; all 823 prior tests retained, 172 new.
Coverage 97.30%, branch-inclusive; unchanged >=96% gate. No Python changes after collection.
Ruff lint/format PASS (276 files); strict mypy PASS (129 source files); Bandit/pip check PASS.
Only the Bandit empty-credential initialization warning needed a local pre-regression correction.
Documentation/checkpoint PASS; current-sprint assertion advanced to Sprint 8.
AGENTS.md unchanged; no dependencies, coverage exclusions or new ADR.

## Known limitations and next scope
Offline validation; no live cluster qualification. Metadata-based version detection.
Bounded non-atomic snapshots; no Admin API mapping; unmapped APIs explicitly LIMITED.
DNS/TCP/TLS/HTTP(S) from MCP host only; first approved address; system TLS trust.
No Redis/DB protocol probes, authenticated probes or automatic root-cause confirmation.
Probes: no proxy/credential headers, Secret decoding, response bodies or automatic redirects.
Observability: bounded response bodies and configured HTTPS credentials; no proxies/redirects.
Metric mapping/units are operator-defined; logs/traces in-memory only; no live provider validation.
Custom CA reference supported; verified SSLContext is the mTLS extension point.
Observability defaults: 1h window, 100 new items, 12 resources, 8 log lines, 256 KiB, 3s/source.
Existing total Evidence/depth/request-byte limits still apply; no metric-only root-cause claim.
OS DNS worker may finish after cancellation; late results never create connections.
Local Git only; no remote fetch. Explicit programmatic refresh; CLI index starts empty.
Lexical embeddings, ephemeral indexes/caches, pattern-based redaction.
No mandatory Sprint 8 item pending.
Next recommended scope: qualify operator mappings and one real log/trace adapter when authorized.

## Relevant ADRs and documents
0003 models; 0004 config/secrets; 0007 datasource; 0009 RAG; 0010 security;
0011 FastMCP; 0013 runtime; 0014 3scale; 0015 knowledge; 0016 trust boundary;
0017 correlation; 0018 hypothesis/troubleshooting; 0019 trace/safe probes, APPROVED.
Contracts: docs/architecture/troubleshooting-engine.md and hypothesis-model.md.
Safety/plans: docs/security/troubleshooting-safety.md and docs/architecture/troubleshooting-plan.md.
Trace/probes: docs/architecture/virtual-trace-probes.md; docs/security/probe-safety.md.
Observability: docs/architecture/observability-correlation.md; docs/security/observability-data-access.md.
Validation: docs/development/sprint-8-validation.md (Sprint 7 report retained).

## SPRINT CHECKPOINT
Sprint: 8
Commit: HEAD (single containing commit; resolve using command above).
Base commit: 14cbc5f14c5072300180cfe6a31e6aab737bcd2f
Expected commit subject: feat: add observability evidence correlation (Sprint 8)
Status: PASS
Impact: HIGH
Capabilities: logs, metrics, traces, Events, timeline, VirtualTrace and ProbeEvidence enrichment.
Adapters: InMemory and Prometheus-compatible read-only HTTP; five opt-in MCP tools.
Architecture: existing correlation engine and evaluator reused; no duplicate engine or collector.
New ADR: NONE; existing approved decisions preserved.
Security: scoped configuration/permissions, redaction, SSRF/TLS boundary, no raw queries/writes.
Tests: 995 passed, 0 failed/errors/skipped; 172 new, all 823 previous retained.
Validation: L2 108 PASS; single full regression PASS; lint/format/mypy/security/dependencies PASS.
Coverage: 97.30%, branch-inclusive; no Python changes after collection.
Coverage gate: >=96%, branch-inclusive; no new exclusions or dependencies.
Limits: offline qualification, fixture logs/traces, operator metric mappings, existing engine bounds.
Next: qualify one real log/trace adapter and environment mappings when authorized.
