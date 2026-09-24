# ADR-0017 — Evidence Correlation Engine

## Status

APPROVED — Sprint 5, 2026-09-23.

## Context

Runtime snapshots, semantic topology, retrieved documents and prior incidents exist
as separate canonical contracts. Troubleshooting needs auditable relationships
between them before any hypothesis or causal diagnosis is justified.

## Decision

Use a deterministic EvidenceCorrelationEngine with injected canonical evidence/topology,
knowledge and historical ports, a clock, bounded configuration and a rule registry.
Vendor composition belongs in application providers, outside the correlation engine.
The 3scale bridge reuses one discovery snapshot and selects one installation before
bounded traversal; shared installation resources cannot bridge evidence.

CorrelationResult contains EvidenceSets, candidates, provenance, a timeline and
separate knowledge/historical references. It never produces Findings, root causes
or executable recommendations. IncidentBundle gains an optional correlations tuple;
existing bundles remain valid. Historical causes and remediation remain attributed
to their original Incident, never transferred to the current incident.

Use qualitative LOW/MEDIUM/HIGH confidence with reasons. Deduplicate identical facts;
mirrored observations do not create independent sources. Preserve contradictions and
lower confidence. Retrieval similarity is not diagnostic confidence.

Time windows, event/resource/candidate counts, topology depth, enrichment deadlines
and cache lifetime are explicit and bounded. Missing/stale/future timestamps remain
visible but do not support temporal correlation. Structural references do not prove
external connectivity. Optional source failures produce PARTIAL; authorization and
invalid scope fail closed. Cancellation propagates.

Expose three read-only opt-in MCP tools. Store results only in a bounded process-local
cache, keyed by environment and principal; recheck permissions on every cache read.
Treat every external document, event and annotation as inert data; never call an LLM,
execute source text or fetch an attribution URL.

## Consequences

Results are reproducible for the same canonical inputs, clock, configuration and rule
version. Provenance timestamps/checksums survive correlation; correlated_at and engine
version are separate metadata. Sorting and truncation are explicit and observable.
Non-atomic runtime snapshots, incomplete history and lexical retrieval limit confidence.
Cached IDs expire and are unavailable across workers/restarts. Sprint 6 can consume
these contracts without treating correlation as a finding.

## Alternatives Considered

- LLM correlation: rejected for this sprint; less deterministic and expands trust boundary.
- Generic cause ranking from history: rejected; similarity cannot establish current causality.
- Vendor-specific engine: rejected; retain canonical ports and application bridges.
- Persistent correlation database: deferred; bounded ephemeral cache meets current scope.
- Silent enrichment fallback: rejected; missing sources and compatibility require warnings.
