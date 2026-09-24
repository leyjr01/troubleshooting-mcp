# Hypothesis and troubleshooting engine

FastMCP → TroubleshootingService → TroubleshootingEngine → existing correlation →
catalog/generation → evaluation → candidate extraction → inspection plan.

The engine imports no vendor implementation, FastMCP, Kubernetes SDK, Git or vector
vendor. Application composition registers generic, Kubernetes and 3scale providers.
No LLM is required. The correlation engine collects one canonical snapshot; explanation
and plan tools reuse a bounded cached diagnostic result without additional collection.

## Inputs, outputs and limits

TroubleshootingResult contains context, full bounded CorrelationResult, hypothesis
instances/evaluations, root cause candidates, plan, warnings, missing capabilities,
provenance and status. IncidentBundle.troubleshooting is optional and environment
validated; the existing fields remain compatible.

Configuration key troubleshooting defaults to max_hypotheses=16, max_candidates=8,
max_plan_steps=12, max_evidence_per_hypothesis=10 and max_components=12. Cache bounds
are 16 results and 300 seconds. Hard limits reject invalid configuration. Correlation
continues enforcing its own window/events/resources/depth/reference bounds; application
max_payload_bytes bounds the complete response. Truncation warns and cannot turn
discarded support into certainty. The requested resource/component takes priority.

Only correlation timeline entries marked relevant support evaluation. Historical,
missing and future observations cannot silently become current proof. Collection
coverage is scoped by namespace and resource kind; forbidden/truncated/incomplete
inventory cannot prove an absence. Metadata/state signals are typed allowlists, never
derived from commands or assertions inside free text.

3scale profiles exclude disabled/optional components from failure generation. External
Redis/database references do not imply live failure. Version-specific definitions
use known major.minor compatibility; unknown versions warn and remain inconclusive.
Known incompatible versions omit the specialized definition, preserving generic rules.
No missing Redis Pod hypothesis is generated for expected external Redis.

## MCP contracts

Opt in to diagnose_component, diagnose_gateway, diagnose_api, explain_hypothesis and
get_troubleshooting_plan. Enable application operation diagnose and permission
troubleshooting.read. Creation also needs correlation.read and the source permissions
documented in [correlation](evidence-correlation.md). Knowledge/history can be omitted
with include_knowledge=false/include_history=false. Caller arguments cannot grant access.

The three diagnose tools accept a typed CorrelationQuery plus optional environment_id
and correlation_id. diagnose_component requires component_id; diagnose_gateway requires
gateway_id; diagnose_api requires resource_id. The query carries optional sanitized
symptom, namespace, explicit time_window, topology_depth and enrichment flags.

diagnose_api works for an existing canonical runtime resource. It does not discover
3scale Admin API Products/APIs. An unassociated identity returns status LIMITED,
API_MAPPING_NOT_AVAILABLE, empty hypotheses/candidates and an unexecuted empty plan.
It does not invent a mapping or promote a nonexistent subject.

explain_hypothesis accepts hypothesis_id and optional result_id. It returns the catalog
definition and evaluated instance, including generation reasons, support, contradiction,
missing requirements, confidence explanation and provenance. get_troubleshooting_plan
requires result_id and returns the plan and missing capabilities. Both accept optional
environment_id/correlation_id and never execute steps.

The cache key includes environment and principal; reads repeat the original source
permission checks. Missing/expired/foreign IDs return resource_not_found; revoked
permissions return authorization. Result IDs are process-local and not durable or
shareable across workers/restarts. Oversized responses fail safely without caching.

Definitions/rules determine stable hypothesis IDs, status, confidence and ordering for
the same correlation context. Original retrieval timestamps/checksums are preserved;
correlated_at and engine_version remain explicit. No confirmed incident root cause is
assigned. See [hypothesis model](hypothesis-model.md), [plans](troubleshooting-plan.md)
and [safety](../security/troubleshooting-safety.md).
