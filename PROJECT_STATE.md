# PROJECT_STATE

## Post-v1.0 working checkpoint — multi-namespace 3scale discovery
Status: implementation complete; focused execution pending restoration of the local Python 3.12
interpreter referenced by `.venv`. Ruff lint/format and `git diff --check` pass.
ThreeScaleGatewayAdapter now requests the runtime's complete authorized namespace scope while
retaining the configured/requested APIManager namespace as the installation's primary namespace.
The classifier associates cross-namespace APIcast workloads only when a single APIManager makes
the label-based association unambiguous; concrete ownership remains authoritative and competing
APIManagers remain isolated. Single-namespace behavior and the singular Installation.namespace
contract are preserved. Focused adapter/classifier regression tests cover both association and
ambiguity boundaries. ADR-0014 records the revised namespace boundary.

## Current baseline
Current Sprint: 11 — Final Hardening, Release Readiness & v1.0.0 Preparation.
Status: PASS. v1.0.0: READY WITH LIMITATIONS; all critical technical gates passed.
Commit: HEAD — chore: prepare v1.0.0 release readiness (Sprint 11).
Base commit: 0f7ad273ae95924b803e98090cdd05624931d0ca (Sprint 10 PASS).
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
Approved Sprint 10 baseline: 1124 PASS, 97.76%, 35/35 scenarios and 6/6 golden.
Sprint 11 minimal baseline: 67 PASS; focused release/HTTP/deployment/docs: 43 PASS.
Focused collection emitted Windows WMI diagnostic but completed with exit zero.
Wheel/sdist build and isolated install/system_health 1.0.0 PASS.
L2 release checkpoint: 590 PASS, 543 deselected, 132.21s; 35 scenarios and 6 golden PASS.
Lint/format PASS (314 files), mypy PASS (134 source files), Bandit/pip check PASS.
Single final full regression: 1133 PASS, 0 failures/errors/skips, 267.47s.
All 1124 baseline tests retained; 9 added. Branch-inclusive coverage 97.81%, >=97% PASS.
No runtime source changes after the full regression; final packaging refresh is documentation-only.
Runtime version uses installed package metadata; pyproject is the single version authority.
OCI version supplied at build is verified against installed metadata; no runtime Git.
Audit includes configured principal and hashed resource/query reference, never raw input.
Release marker reuses configuration/security/architecture/MCP/deployment/scenario suites.
Global 38-tool read-only and all-role get/list/no-Secret/no-wildcard gates implemented.
No new diagnostic algorithm, adapter, probe, RAG capability or remediation.
AGENTS.md and approved ADRs unchanged; no new ADR. Runtime dependency versions unchanged.
Only existing pinned setuptools/wheel build tools installed for artifact generation.
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
Post-1.0: live OpenShift/3scale qualification, SSO/OIDC, HA, additional gateways/providers,
incident DB, production RAG hardening and separately authorized controlled remediation.
Current dependency CVEs not assessed by Bandit/pip check; license metadata inventory supplied.
Public redistribution license is unspecified; no publication or tag performed.

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
Release: docs/release/v1.0.0.md, compatibility.md, tool-catalog.md, contracts.md,
security-review.md, commands.md and sprint-11-validation.md; CHANGELOG.md.
Operations: docs/operations/runbook.md; installation: docs/installation/README.md.

## SPRINT CHECKPOINT
Sprint: 11
Commit: HEAD (single containing commit; resolve using command above).
Base commit: 0f7ad273ae95924b803e98090cdd05624931d0ca
Expected commit subject: chore: prepare v1.0.0 release readiness (Sprint 11)
Status: PASS. v1.0.0: READY WITH LIMITATIONS.
Release: 1.0.0 technical preparation complete; no publication or tag.
Impact: HIGH
Delivered: metadata version authority, OCI labels, audit attribution/reference hashes,
release catalog, compatibility/security/operations docs, packaging and clean-install scripts.
Architecture: existing 38 tools and diagnostic pipeline preserved; no new feature.
Security: read-only tools/RBAC; no Secret API grants, wildcard or source-write operations.
New ADR: NONE. AGENTS.md and prior approved decisions unchanged.
Tests: baseline 67 PASS; focused 43 PASS; L2 590 PASS; single full regression 1133 PASS.
Scenarios: 35/35 PASS, golden 6/6 PASS, six expected inconclusive; no false positives/negatives.
Packaging: wheel/sdist and isolated installation/system_health PASS.
Quality: lint/format/mypy/Bandit/pip PASS; coverage 97.81%, >=97% required.
Real Lab: Kubernetes/OpenShift/3scale/container NOT EXECUTED; no infrastructure available.
Limits: no live qualification, production SSO/HA/remediation or current CVE certification.
Next: no mandatory Sprint 11 item pending; follow documented post-1.0 qualification backlog.
