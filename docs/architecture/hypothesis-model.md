# Hypothesis model

[ADR-0018](../adr/0018-hypothesis-and-troubleshooting-architecture.md) defines the boundary.

HypothesisDefinition is a reusable, declarative catalog entry: scope, applicable
resource/component types, gateway/version constraints, trusted rule ID, priority,
required evidence and optional strengthening evidence. Providers register entries;
duplicate IDs fail configuration. The initial catalog has 15 entries: two generic,
six Kubernetes and seven 3scale. Only used modules exist.

HypothesisInstance binds a definition to a bounded subject/resources and optional
component. It contains its statement, generation reasons, version compatibility,
separate knowledge/history references and a HypothesisEvaluation. The evaluation
owns status, supporting/contradicting evidence IDs, missing EvidenceRequirements,
topology references, confidence, factual reason codes and original provenance.

| Status | Formal rule |
| --- | --- |
| CANDIDATE | Instantiated and awaiting evaluation; not a diagnosis. |
| SUPPORTED | Direct current support; requirements met; no counterevidence or truncation. |
| REJECTED | Positive direct counterevidence and no current support; never mere absence. |
| INCONCLUSIVE | Conflicting/limited evidence, uncertain compatibility or unverified external connectivity. |
| BLOCKED_BY_MISSING_EVIDENCE | Required observations or complete scoped inventory are missing. |

Ready endpoint evidence contradicts the universal no-ready-endpoint claim. Negative
and positive observations together remain INCONCLUSIVE; neither is erased. Missing
EndpointSlice permission/coverage blocks support rather than proving no endpoints.
CrashLoopBackOff supports lifecycle instability, not an application bug. Route target
not_found is distinct from forbidden/not_observed and from a missing configuration
reference of a different resource kind.

RootCauseCandidate is extracted only from SUPPORTED evaluations. Its scope is an
observed condition, never CONFIRMED_ROOT_CAUSE. Multiple candidates are retained within
the configured bound. Confidence/order are qualitative, not numerical probability.
Knowledge/history remain references; previous incident causes stay attributed to
the prior Incident and never become runtime support.

HIGH is possible for narrowly bounded structural proof: declared topology plus
complete current lookup/readiness, with no contradictions or missing coverage.
Otherwise it needs independent runtime sources/origins. Other supported conditions
are MEDIUM; unresolved/contradicted/missing cases are LOW. Historical similarity and
retrieval scores never supply this confidence. See ADR-0018 for the scoped extension
to ADR-0008's independence rule.

Finding remains an interpreted observed condition; Hypothesis is testable; Candidate
is sufficiently supported to present as a possible explanation. Existing Recommendation
retains its finding requirements. This sprint uses TroubleshootingStep for proposed
inspections instead of fabricating Findings to populate Recommendations.

ReportedSymptom records user_reported versus runtime_observed/unspecified origin.
User symptom text is sanitized context, never observed Evidence. All IDs and original
provenance resolve through the included CorrelationResult. Rule summaries expose
factual support/missing/contradiction reasons, not free-form hidden reasoning.
