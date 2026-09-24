# Deterministic correlation rules

Engine rule version: 1.0.0. These are relationships, not causal diagnoses.

| Type | Mechanism and limits |
|---|---|
| RESOURCE | Same requested resource or member of the selected component. |
| EVENT | Canonical scoped event with a known timestamp inside the window. |
| TEMPORAL | Known timestamps within configured proximity; mirrored origins excluded. |
| TOPOLOGICAL | Observed neighboring resources within bounded undirected graph distance. |
| COMPONENT | Runtime observations assigned to the same canonical semantic component. |
| STATUS | Unavailable observation; preserve same-resource or explicit Service/EndpointSlice ready contradictions. |
| DEPENDENCY | Declared graph link or explicitly unresolved target, without connectivity claim. |
| CONFIGURATION_REFERENCE | Secret/ConfigMap/configured_by/external connection metadata only. |
| KNOWLEDGE | Indexed, scoped, attributed document reference; no runtime support. |
| HISTORICAL_SIMILARITY | Attributed prior Incident; no runtime support and no inherited cause. |

Structural links use observed metadata. An unresolved target has a synthetic opaque
reference identity, not an invented observed resource. Missing targets retain source
provenance and resolution status (not_found/not_observed/forbidden/ambiguous).

Distances 0, 1 and 2 mean root, direct neighbor and one intermediate resource. Temporal
closeness cannot expand graph scope. External references do not trigger probes. Rules
never parse runbook instructions or infer cause from free-form event text.

Confidence follows [ADR-0008](../adr/0008-confidence-model.md): LOW when contradicted
or distance exceeds one; otherwise MEDIUM. HIGH additionally requires at least two
distinct authoritative source IDs, all supporting inputs HIGH, and direct proximity.
The built-in runtime source normally cannot independently satisfy HIGH. Knowledge/history
candidates are LOW and never support current runtime facts. Confidence is not a percentage.

Identical facts are deduplicated by resource, original provenance, observation, event
timestamp, kind and state; different IDs alone cannot raise confidence. Same ID with
different facts is rejected. Temporal pair duplicates are eliminated. Contradictions are
retained as separate references and result in INCONCLUSIVE status; evidence is not erased.

Candidate IDs hash subject, mechanism and references. Final ordering, capped selection
and timeline ordering are stable for the same inputs and clock. Event timestamp,
original retrieved_at, and correlated_at have distinct meanings. Original content
checksums describe provider evidence, not a newly computed correlation checksum.

Mandatory scenarios are executable in tests/unit/test_correlation_*.py and
tests/integration/test_correlation_mcp.py: no ready endpoints; unavailable Deployment,
Pod and restart; absent Route target; two historical 503 causes; ready endpoint
contradiction; matching 2.16 documentation; unknown version; malicious runbook; partial
history outage; cross-environment denial; separate installations; duplicate fact.
