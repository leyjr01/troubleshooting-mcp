# Troubleshooting safety

Troubleshooting reuses the correlation trust boundary and adds read-only hypothesis
evaluation. Environment/resource/installation scope is enforced before collection;
canonical lineage is revalidated before evaluation. Knowledge and history retain
their original access scopes. Results and cached explanations/plans require the
same principal/environment and source permissions; IDs do not grant access.

Only typed, relevant runtime observations and bounded topology support hypotheses.
User reports, historical causes and retrieved documentation cannot independently
confirm any cause. Missing evidence is not counterevidence. Optional/disabled
components do not imply failure; unavailable RBAC prevents absence claims.
Contradictions and discarded evidence lower certainty rather than creating support.

Runbooks, event text, annotations and symptoms remain inert data. The catalog is
trusted application code, not content loaded from RAG. No eval, command execution,
LLM, Secret access, Admin API, management API, socket/HTTP probe or write endpoint
exists in troubleshooting. Original evidence/provenance remains traceable; redaction
and minimized runtime projections are retained. No secret text or exception detail
is deliberately copied into explanations, plans or audit records.

Generated steps are read-only descriptions or disabled future passive probes.
No ACTIVE_PROBE/WRITE_OPERATION step is emitted and every step is non-executable.
Existing Finding/Recommendation contracts are preserved; supported candidates do not
set Incident.root_cause_finding_id or claim a confirmed incident cause.

Bounds apply to components, hypotheses, evidence, candidates, steps, response bytes
and cache count/TTL. Optional source failure remains visible through correlation
warnings. Cross-scope/authentication failures remain fatal, never successful partial
diagnoses. Validation uses synthetic clusters and local MCP, not live production.

Pattern-based redaction, bounded non-atomic snapshots, lexical knowledge retrieval
and process-local caches remain limitations. Probe capabilities and production
persistence are outside this sprint.
