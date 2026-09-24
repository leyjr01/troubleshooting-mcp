# Evidence correlation

Implemented in Sprint 5; [ADR-0017](../adr/0017-evidence-correlation-engine.md).

The MCP boundary creates an authorized ExecutionContext. CorrelationService checks
source permissions before calling EvidenceCorrelationEngine. Its injected provider
returns one canonical snapshot with topology, observation timestamps and optional
semantic component/reference context. Gateway-specific composition stays in services.
The engine bounds and sanitizes context, applies deterministic rules, enriches with
indexed references, validates lineage and returns a CorrelationResult.

## Contracts and separation

- EvidenceSet: subject, environment, requested window, resources/components, runtime
  Evidence and original provenance; knowledge/history are separate IDs.
- CorrelationCandidate: relation type, mechanism, reasons, support, contradictions,
  topology/document/history references, distances and qualitative Confidence.
- CorrelationResult: engine version, correlated_at, COMPLETE/PARTIAL, sets, candidates,
  timeline, separate reference objects, topology and warning codes.
- CorrelationContext: sanitized query, environment, subject, explicit time window.
- CorrelatedKnowledge: attributed untrusted KnowledgeResult and version compatibility.
- HistoricalSimilarity: prior Incident identity, symptoms, prior cause/remediation,
  matched components; historical similarity, runtime_support=false.
- TimelineItem: nullable event timestamp, resource/component, event type, observation,
  relevance and original provenance. Unknown timestamps sort last; never invent event time.

IncidentBundle.correlations defaults to an empty tuple. Each result carries its own
validated evidence closure; bundle environment must match. Findings and current incident
root_cause_finding_id remain unchanged by correlation.

## MCP contracts

Enable correlate_evidence, get_correlation_timeline and explain_correlation explicitly
in mcp.server.enabled_tools. Allow application operation correlate and permission
correlation.read. Creation additionally requires resource.read, event.read, topology.read;
semantic installations require gateway.discover, gateway.components.read and
gateway.topology.read. Default knowledge/history enrichment requires
knowledge.search.internal, knowledge.search.official and knowledge.issues.read.
Set include_knowledge/include_history=false to omit these sources and permissions.

correlate_evidence takes query plus optional environment_id/correlation_id. At least one
resource_id, component_id or gateway_id is required. A namespace narrows the authorized
scope; symptom is sanitized inert text. time_window accepts timezone-aware start/end.
topology_depth defaults to 2. Creation returns the complete structured result.

get_correlation_timeline takes result_id and returns its timeline.
explain_correlation takes result_id plus optional candidate_id and returns candidates
with rules, reasons, support, contradictions, original provenance and engine metadata.
Both also accept environment_id/correlation_id. They do not recollect evidence.
An expired, missing or differently scoped ID returns resource_not_found. Revoked
permissions return authorization. Oversized outputs return sanitization, never partial JSON.

## Bounds and lifecycle

Configuration key correlation uses CorrelationConfig. Defaults: 900-second lookback,
86400-second maximum window, 30-second future skew, 90-second temporal proximity,
10 observations, 12 resources, 12 candidates, depth 2 (hard maximum 3), two references
per enrichment category, three seconds per enrichment request, 16 cached results,
300-second cache TTL. Hard limits reject invalid configuration. Response bytes are
also bounded by application.max_payload_bytes.

The default window ends after collection; an explicit historical window stays fixed.
Stale/missing/future evidence remains in the bounded timeline with warnings and no
runtime support. A current topology snapshot outside an explicit historical window
does not assert historical dependencies. Truncation is deterministic and warns;
contradicted candidates have priority, then relation categories are interleaved.

Cache keys include principal and environment. Reads recheck original source permissions.
No export, persistence, refresh tool or scheduler is introduced. Restart and worker
boundaries invalidate result IDs. Index refresh remains the explicit Sprint 4 operation.

## Failure and version handling

Optional enrichment timeout/unavailability produces PARTIAL and retains runtime results.
Authorization/scope violations, missing subjects and invalid input remain fatal.
Unknown timestamps and bounded/truncated graphs also produce warnings. Source exception
details never reach clients. Cancellation is not converted into a successful result.

The bridge prefers official documentation for detected 3scale major.minor (2.16.x maps
to 2.16). Unknown versions broaden product-scoped retrieval and mark returned official
references with version_compatibility_unconfirmed. No compatibility is inferred from
retrieval score. Histories preserve distinct previous causes even for the same symptom.

See [rules](correlation-rules.md) and [trust boundary](../security/correlation-trust-boundary.md).
