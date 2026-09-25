# PROJECT_STATE

## Current baseline
Current Sprint: 10 — Real Environment Integration & Deployment Readiness.
Status: PASS for deployment readiness; live qualification NOT EXECUTED.
Commit: HEAD — feat: add Kubernetes OpenShift deployment readiness (Sprint 10).
Base commit: c80518197268c3b99d49f8fc516a0af03f560f10 (Sprint 9.1 PASS).
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
Impact: HIGH; authenticated HTTP deployment, container and Kubernetes/OpenShift manifests.
Loopback default preserved; external HTTP requires configured bearer token and exact hosts.
TokenVerifier uses CredentialProvider (environment or allowlisted mounted file), same ACLs.
No identity federation; static token maps to the existing configured local-client principal.
Non-root image, arbitrary UID design, read-only root filesystem, bounded writable /tmp.
Namespace/ServiceAccount/read-only Role/Binding/ConfigMap/Deployment/Service and optional Route.
Minimal /livez and /readyz reuse lifecycle state; unavailable sources do not kill readiness.
Opt-in real_lab profile reuses existing SDK, runtime, trace and diagnosis; default CI ignores it.

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
Read-only discovered sources; no Secret API reads, external writes or remediation.
Server authentication may read its explicitly configured mounted credential; never exported.
RBAC grants only get/list on named resource kinds; no Secret grants or wildcards.
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
Approved baseline: 1092 PASS, 97.38% coverage; 35/35 scenarios, 6/6 golden.
Small initial baseline: 62 PASS (configuration/runtime).
L1 deployment: 27 unit cases and authenticated HTTP case passed across focused runs.
L2 checkpoint: 117 PASS, zero failures/errors/skips, including all 6 golden cases.
L2 covers HTTP authentication/ACLs/health/shutdown, unavailable Kubernetes, runner,
transport compatibility, SSRF/probe security, architecture, SDK auth and documentation.
Opt-in real_lab: 2 SKIPPED (no Docker or configured cluster); no real execution claimed.
Single final full regression: 1124 PASS, 0 failures/errors/skips, 115.93 seconds.
All 1092 baseline tests retained; 32 added. Strict scenarios: 35/35 PASS, golden 6/6 PASS.
Coverage: 97.76%, branch-inclusive; >=97% gate PASS.
Lint/format PASS (301 files), strict mypy PASS (134 source files), Bandit/pip check PASS.
Bandit B104 exceptions only for explicit authenticated bind and its comparison, per ADR-0020.
Post-regression edits: documentation and those comments/formatting only; behavior unchanged.
Coverage gate >=97%, branch-inclusive; project minimum >=96% unchanged, no exclusions added.
AGENTS.md unchanged; existing runtime dependencies unchanged; Linux build constraints added.

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
Real-lab profile implemented, explicitly enabled with --real-lab; no default CI network.
Docker/kind/k3d/kubectl/oc unavailable; no configured real Kubernetes/OpenShift/3scale.
Container build/smoke, Linux dependency resolution, SCC admission, Route TLS and actual
SIGTERM shutdown NOT EXECUTED; static contracts and local HTTP lifecycle are validated.
Operator must supply approved Python 3.12 Linux image digest, token and cluster-specific
hosts/namespaces/network policy; examples are not production identity/HA/SSO support.
Sprint 11 baseline: containing Sprint 10 PASS commit; resolve using command above.

## Relevant ADRs and documents
0003 models; 0004 config/secrets; 0007 datasource; 0009 RAG; 0010 security;
0011 FastMCP; 0013 runtime; 0014 3scale; 0015 knowledge; 0016 trust boundary;
0017 correlation; 0018 hypothesis/troubleshooting; 0019 trace/safe probes, APPROVED.
0020 authenticated container deployment; previous approved ADRs unchanged.
Contracts: docs/architecture/troubleshooting-engine.md and hypothesis-model.md.
Safety/plans: docs/security/troubleshooting-safety.md and docs/architecture/troubleshooting-plan.md.
Trace/probes: docs/architecture/virtual-trace-probes.md; docs/security/probe-safety.md.
Observability: docs/architecture/observability-correlation.md; docs/security/observability-data-access.md.
Validation: docs/development/sprint-9-validation.md; earlier sprint reports retained.
Sprint 10: docs/development/sprint-10-validation.md; docs/development/real-lab.md.
Deployment: docs/deployment/kubernetes.md, openshift.md and operations.md.
Harness: docs/development/diagnostic-scenario-harness.md.

## SPRINT CHECKPOINT
Sprint: 10
Commit: HEAD (single containing commit; resolve using command above).
Base commit: c80518197268c3b99d49f8fc516a0af03f560f10
Expected commit subject: feat: add Kubernetes OpenShift deployment readiness (Sprint 10)
Status: PASS for deployment readiness; real infrastructure NOT EXECUTED.
Impact: HIGH
Delivered: authenticated HTTP, container definition, Kubernetes/OpenShift manifests/runbooks,
health/lifecycle endpoints, credential mount support and opt-in real-lab smoke profiles.
Architecture: existing SDK/runtime/services/evaluator reused; 38 tools unchanged.
New ADR: 0020 authenticated container deployment; previous approved decisions preserved.
Security: get/list RBAC, no Secret API access, scoped ACLs, safe logs, SSRF boundaries.
Probes: disabled by default; explicit configuration and authorization still required.
Tests: L1 deployment PASS; L2 117 PASS; single full regression 1124 PASS, zero failures/skips.
Scenarios: 35/35 PASS; golden 6/6 PASS; no false positives/negatives or recommendation failures.
Quality: lint/format/mypy/Bandit/pip check PASS; coverage 97.76%, required >=97%.
Real Lab: Kubernetes/OpenShift/3scale/container NOT EXECUTED; opt-in 2 SKIPPED.
Limits: live image/SCC/TLS/SIGTERM not qualified; no production SSO, HA or remediation.
Next: Sprint 11 baseline is this single containing commit; no mandatory Sprint 10 item pending.
