# PROJECT_STATE

## Current baseline
Current Sprint: 9.1 — Diagnostic Candidate Promotion & Recommendation Fixes.
Corrective status: PASS. Sprint 9 final status: PASS after Sprint 9.1.
Commit: HEAD — fix: close Sprint 9 diagnostic validation gaps.
Base commit: 24a6a931bed6898931fc2d64de329213aeefdf87 (Sprint 9 PARTIAL).
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
20 generic/Kubernetes/3scale/network definitions; typed states, coverage and expectations.
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
FailureScenario/ExpectedDiagnosis → ScenarioRunner → semantic assertions and structured report.
Runner reuses Runtime.execute and existing diagnosis/trace/probe/observability services.
Fixed fixtures, controlled clocks, fake sources/executor; six real in-process MCP cases.
Existing probe refresh now maps DNS, HTTP response/timeout and TLS certificate facts.
Scoped explicit not_found references can support a missing configuration candidate.
Existing evaluator/promotion/confidence pipeline and planner remain authoritative.
Impact: MEDIUM; concentrated diagnostic fixes, no new external integration or architecture.

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
Historical Sprint 9 full run: 1023 PASS, 35 test-option failures; focused repair 36 PASS.
Historical consolidated regression: 1058 PASS, coverage 97.36%; diagnostic acceptance PARTIAL.
Sprint 9.1 baseline union of seven failing cases and golden subset: 7 FAIL, 2 PASS.
L1 corrected seven cases: 7 PASS, unchanged semantic expectations.
L1 evaluator/probe/negative/recommendation tests: 93 PASS (33 new focused tests).
L2 strict scenario/harness/MCP checkpoint: 64 PASS, including 35/35 scenarios and 6/6 golden.
Expected inconclusive: 6; false positives: 0; false negatives: 0; recommendation failures: 0.
Golden now unconditionally requires PASS; aggregate report requires zero failed scenarios.
All seven known-gap allowances removed; original required/forbidden conclusions preserved.
Single final full regression: 1092 PASS, 0 failures/errors/skips, 259.70 seconds.
All 1058 baseline tests retained; 34 added (33 focused controls and one affected MCP case).
Strict diagnostic acceptance enabled in the complete run; no second full regression.
Coverage: 97.38%, branch-inclusive; corrective >=97% gate PASS, no exclusions added.
Lint/format PASS (289 files), strict mypy PASS (133 source files), Bandit/pip check PASS.
Documentation/checkpoint rechecked after final numbers; no source changes after full run.
Coverage target >=97% for this correction; existing project minimum >=96% unchanged.
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
Seven Sprint 9 gaps corrected: DNS, HTTP 500, timeout, ConfigMap, SecretReference,
contradictory TLS-log/HTTP evidence and target TLS validation recommendation.
TLS expiry and chain share the stable hypothesis ID but have distinct reason codes,
candidate descriptions and inspection requirements when direct certificate facts exist.
Unknown/unzoned expiry cannot prove expiration; unknown chain facts stay generic.
Missing references require current explicit not_found and workload evidence;
forbidden/not_observed remain blocked. No Secret contents are read or exposed.
HTTP timeout identifies an observed request timeout, not the underlying latency cause.
No global probe-over-log priority; relevant semantic counterevidence is preserved.
Redis/DB target-specific TCP candidates do not establish protocol failure (approved rule).
Only fixture mode implemented; real-lab is a documented future extension.
Sprint 10 baseline: this containing corrective commit; resolve using the Git command above.
No mandatory Sprint 9/9.1 item remains pending.

## Relevant ADRs and documents
0003 models; 0004 config/secrets; 0007 datasource; 0009 RAG; 0010 security;
0011 FastMCP; 0013 runtime; 0014 3scale; 0015 knowledge; 0016 trust boundary;
0017 correlation; 0018 hypothesis/troubleshooting; 0019 trace/safe probes, APPROVED.
Contracts: docs/architecture/troubleshooting-engine.md and hypothesis-model.md.
Safety/plans: docs/security/troubleshooting-safety.md and docs/architecture/troubleshooting-plan.md.
Trace/probes: docs/architecture/virtual-trace-probes.md; docs/security/probe-safety.md.
Observability: docs/architecture/observability-correlation.md; docs/security/observability-data-access.md.
Validation: docs/development/sprint-9-validation.md; earlier sprint reports retained.
Harness: docs/development/diagnostic-scenario-harness.md.

## SPRINT CHECKPOINT
Sprint: 9.1
Commit: HEAD (single containing commit; resolve using command above).
Base commit: 24a6a931bed6898931fc2d64de329213aeefdf87
Expected commit subject: fix: close Sprint 9 diagnostic validation gaps
Status: PASS. Sprint 9 final status: PASS.
Impact: MEDIUM
Fixes: DNS/HTTP/timeout and missing configuration promotion; TLS-specific recommendations.
Scenarios: 35 total, 35 PASS, 0 FAIL; golden 6 total, 6 PASS, 0 FAIL.
Inconclusive expected: 6; false positives: 0; false negatives: 0; recommendation failures: 0.
Architecture: existing application and evaluator reused; no duplicate engine or new adapter.
New ADR: NONE; existing approved decisions preserved.
Security: fake sources, no real network, redaction, provenance, SSRF and authorization checks.
Tests: L1 93 PASS; strict L2 64 PASS; single full regression 1092 PASS, 0 failures/errors/skips.
Quality: lint/format/mypy/Bandit/dependencies and documentation PASS.
Coverage: 97.38%, branch-inclusive; corrective >=97% gate PASS, project minimum >=96%.
Limits: offline fixtures, observed conditions only, no Redis/DB protocol proof or remediation.
Next: Sprint 10 baseline is this verified containing commit. No corrective items pending.
