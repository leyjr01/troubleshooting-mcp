# ADR-0018 — Hypothesis and Troubleshooting Architecture

## Status

APPROVED — Sprint 6, 2026-09-24.

## Context

Sprint 5 correlates canonical observations without causal diagnosis. Consumers need
testable explanations, explicit evidence requirements and safe next inspections.
Historical similarity and matching documentation cannot establish a current cause.

## Decision

Compose HypothesisCatalog, HypothesisGenerator, HypothesisEvaluator and
TroubleshootingPlanner behind a gateway-neutral TroubleshootingEngine. Inject the
existing correlation engine and declarative providers; 3scale registration belongs
to application composition. Catalog text is not executable logic. Trusted rule IDs
select small evaluators operating on canonical structured observations.

Extend correlation results additively with typed observation state/signals, component
expectations, installation/version and scoped collection coverage. Reuse the single
runtime discovery; never recover signals by interpreting free-text documents/events.
Old correlation payloads lacking this context remain valid but cannot prove facts
requiring those signals. Disabled/optional components cannot create absence failures.

A Hypothesis is a testable explanation. A Finding remains the existing supported
observation/interpreted-condition model. A RootCauseCandidate is a sufficiently
supported explanation candidate with scope observed_condition; it does not confirm
the incident's root cause or a causal chain. No Finding is automatically manufactured.
IncidentBundle gains optional troubleshooting results; legacy hypotheses, findings,
recommendations and root_cause_finding_id remain compatible and unchanged.

Promote only SUPPORTED hypotheses with direct runtime support, no contradictory or
missing required evidence. Positive counterevidence can reject; missing evidence
cannot. Conflicting or truncated support is INCONCLUSIVE. Missing requirements block
evaluation. External connectivity hypotheses stay INCONCLUSIVE with missing probe
capabilities, even when a component is degraded and a reference is configured.

Keep qualitative LOW/MEDIUM/HIGH confidence. Extend ADR-0008's independence rule for
a narrowly bounded structural condition: independent declarative topology plus
completed scoped inventory/status can justify HIGH without different API providers.
For example, an explicit Service/EndpointSlice relationship plus fully observed zero
ready endpoints, or a declared Route target plus completed Service lookup returning
not_found. This does not claim high confidence in the upstream cause of an incident.
Missing/partial/truncated coverage cannot establish this structural proof. Otherwise,
HIGH requires distinct runtime sources and independent origins. Duplicate facts,
knowledge and history cannot raise confidence. Contradictions lower confidence.

Plans describe inspections and missing capabilities; nothing executes them. Current
steps are read-only inspections, with optional future PASSIVE_PROBE placeholders
marked CAPABILITY_UNAVAILABLE and executable=false. No WRITE/ACTIVE steps are generated.
No remediation, probes, LLM, Admin API or management API is introduced.

Results use deterministic IDs/order, explicit bounds, original evidence/provenance,
rule-derived reason codes and an environment/principal-scoped ephemeral cache.
Cached explanation/plan reads recheck source permissions. Unmapped API identities
return a structured limitation rather than invented API/Product associations.

## Consequences

Multiple supported conditions can coexist; ordering means evidence strength and scope,
not probability. The requested subject is prioritized under count limits. Explanations
remain auditable without chain-of-thought. Lack of probes stays visible as missing
evidence for Sprint 7. Bounded snapshots, local indexes and process-local IDs remain
operational limitations. Canonical contracts grow additively; no SDK leaks into core.

## Alternatives Considered

- LLM-led root cause guessing: rejected; deterministic evidence evaluation is required.
- Promoting historical matches: rejected; prior causes are not current observations.
- Parsing runbooks into commands: rejected; external text remains inert data.
- Treating partial RBAC as absence: rejected; record missing evidence instead.
- Reimplementing correlation or rediscovering topology: rejected; reuse Sprint 5.
- Executing plans or storing production diagnostic sessions: deferred to future scope.
