# Observability correlation — Sprint 8

`ObservabilityCorrelationService` adds descriptive telemetry to the existing
Evidence Correlation Engine and invokes the same `TroubleshootingEngine.evaluate`.
It does not create another evaluator, infer causes from metrics or execute plans.
No LLM, new dependency, background collector or new ADR is required. This implements
the existing configuration, datasource, correlation and probe boundaries in
ADRs 0004, 0007, 0017 and 0019; approved decisions remain unchanged.

```text
Resource / component / cached VirtualTrace
  -> explicit environment + UTC time window + bounded resource scope
  -> ObservabilityAdapter (health, capabilities, query)
  -> normalized/redacted Evidence with provenance
  -> existing correlation refresh (runtime + Events + ProbeEvidence + telemetry)
  -> existing hypothesis evaluator + descriptive timeline
```

## Contracts and adapters

`ObservabilityQuery` carries environment, explicit aware start/end timestamps,
resource/component references, optional cached virtual trace ID, distributed trace
ID, correlation ID, typed filters, signal types and limit. An unscoped request is
invalid. A trace ID without resources resolves only through configured bindings.
Resource references must belong to the canonical topology around the requested
subject. Components resolve to their canonical resources. Cached traces reuse
resolved resource hops, preserve their ProbeEvidence and recheck principal,
environment, original permissions and TTL before contacting a source.

`ObservabilityAdapter` is a provider-neutral async protocol: `capabilities()` reports
LOG/METRIC/TRACE support, `health()` checks availability and `query()` returns a
bounded `AdapterBatch`. InMemory implements all three signal types using fixtures.
Prometheus implements metrics over GET HTTP with health, instant and range queries.
Events continue through the existing runtime collector; no second collector exists.
Logs/traces have no real Loki, Elasticsearch, Tempo or Jaeger integration in Sprint 8.

`LogObservation`, `MetricObservation` and `TraceObservation` retain canonical resource
identity, source, aware timestamp and typed fields. Normalization redacts before
truncation and hashing. Telemetry IDs are hashed for deduplication; source ID,
resource, timestamp and sanitized content distinguish observations. Identical items
from the same source collapse; independent sources remain distinct corroboration.
Provider text and attributes retain an explicit `UNTRUSTED_DATA` marker in Evidence.

Correlation keys are resource UID, namespace, pod, service, gateway component,
hostname, trace ID, request ID and correlation ID. Resource bindings come from
operator configuration; conflicting supplied keys are rejected. Adapter-provided
identifiers retain source provenance and use exact typed matching, never free text.
Trace, request and correlation IDs occupy different namespaces. Suspicious opaque
identifier values are represented by stable hashes in Evidence. Existing engine
rules own time proximity and topology/resource/component association; telemetry
text cannot add typed failure states or masquerade as runtime status.

Each Evidence source reference records adapter, datasource, canonical query hash,
window and resource; `retrieved_at` and a sanitized-content checksum are included.
Runtime and probe timestamps are not relabeled fresh. Timeline entries use existing
Evidence references, category and provenance, sorted by timestamp/resource/ID.
Only temporally relevant entries enter the descriptive timeline; stale runtime
evidence may remain in the diagnosis with the existing engine's warnings.

## MCP interface and authorization

| Tool | Purpose | Entry permission |
| --- | --- | --- |
| inspect_observability | Retrieve selected signal types and reevaluate | observability.timeline.read |
| inspect_logs | Bounded resource logs | observability.logs.read |
| inspect_metrics | Internal metric intent query | observability.metrics.read |
| inspect_trace | Distributed trace ID lookup in scoped resources | observability.traces.read |
| build_evidence_timeline | Unified descriptive timeline | observability.timeline.read |

All tools take `query: ObservabilityQuery`, plus optional environment and request
audit correlation ID. The latter is separate from the telemetry query correlation
ID. Named log/metric/trace tools select their signal when `signal_types` is omitted;
an explicitly conflicting selection is rejected. `inspect_trace` also requires a
trace ID. Tools are opt-in in `mcp.server.enabled_tools`, read-only and require the
application `diagnose` operation, existing correlation/source permissions and
environment grants. Signal permissions are checked separately for combined tools.
Strict JSON validation accepts arrays, enum strings and ISO timestamps while
rejecting numeric coercion, extra fields, URLs and backend expressions.

Example `inspect_metrics` query:

```json
{
  "query": {
    "environment_id": "demo",
    "resource_refs": ["canonical-runtime-resource-id"],
    "time_window": {
      "start": "2026-09-24T12:00:00Z",
      "end": "2026-09-24T12:05:00Z"
    },
    "metric_intent": "availability",
    "metric_mode": "range",
    "limit": 20
  }
}
```

The response includes Evidence, timeline, consulted sources and their status,
warnings, enriched VirtualTrace when applicable, and the existing diagnosis.
FORBIDDEN, TIMEOUT, UNAVAILABLE, INVALID_DATA and UNSUPPORTED are per-source partial
outcomes. Unconfigured sources are explicit. Cancellation and invalid request scope
terminate the request. Provider exception messages and warning text are not returned.

## Prometheus protocol and configuration

The implementation uses the [official Prometheus HTTP API](https://prometheus.io/docs/prometheus/latest/querying/api/):
`/api/v1/query`, `/api/v1/query_range`, and the read-only `/-/ready` health endpoint.
Metric names and exact selectors come only from validated operator configuration.
No tool accepts PromQL. Intents map to configurable metric names, without 3scale
coupling. Availability, restarts, resource usage and latency return the configured
series values; units and counter/gauge semantics remain those of that series.
Error rate uses `rate(metric{scope,code=~"5.."}[Ns])`, with configurable status label
and bounded lookback up to 300 seconds. It represents 5xx events/second, not an error
percentage. Range evaluation has that explicit bounded lookback before each sample.
Operators must map metric names/status labels to the installation; absent names
produce an explicit unavailable-intent warning.

See [disabled example](../../config/server/observability.example.yaml). Configuration
loading does not resolve credentials or contact endpoints. A URL can use the
existing whole-value environment interpolation. Only a credential reference is
stored; custom CA is an operator file reference. A verified injected SSLContext is
the extension point for operator-managed mTLS; certificate provisioning is deferred.

## Bounds and limitations

Defaults: 1-hour window, 100 new telemetry items, 12 resources, 2,048 text characters,
8 log lines, 256 KiB/source HTTP response and 3 seconds/source. Hard caps apply in
the models; at most eight configured sources are accepted. Query limit bounds new
telemetry, not previously collected runtime/probe items. Existing correlation limits
also apply (default 10 total evidence items and depth 2); truncation remains explicit.
The final MCP byte limit can reject a response that cannot safely fit.

InMemory uses a bounded selection heap; HTTP body and decoded series are byte bounded.
Prometheus retains only bounded selected observations, ordered independently of
provider response order, and deduplicates repeated samples. The provider's own series
limit may omit data; no claim of complete cluster observability is made. Sources are
queried sequentially under source and request deadlines, with no persistent client
pool or cache. No proxy, redirects, compressed responses or live-cluster qualification.
See [data access controls](../security/observability-data-access.md) and
[validation checkpoint](../development/sprint-8-validation.md).
