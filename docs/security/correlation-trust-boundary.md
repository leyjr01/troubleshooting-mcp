# Correlation trust boundary

Authentication/authorization precede collection. Caller arguments cannot supply a
principal or permissions. Correlation requires its own permission plus permissions
for every requested source. Cache access repeats source-permission checks and uses
principal/environment/result identity, never a globally readable result ID.

Canonical providers remain responsible for read-only access and minimized projections.
The engine rechecks snapshot, node, evidence and provenance environments, namespace and
installation ownership. 3scale selection rejects ambiguity. Resources shared with a
different installation cannot join its evidence into the selected installation.
Knowledge can be explicitly global; runtime evidence cannot use global to bypass scope.

External content is untrusted_data. No command evaluation, model invocation, URL fetch,
tool chaining from document text, Secret read, Redis/DB probe or remediation is present.
Annotations/details/labels and edge metadata are omitted from correlation topology.
Observations, symptom and confidence text are redacted; original provenance is preserved.
Canonical provenance references reject explicit credential patterns but retain content
hashes and long public document paths. They are attribution, not fetch instructions.
Knowledge remains sanitized by the existing pre-index pipeline and rechecked at the
correlation boundary. Historical fields never become current Findings.

Pattern-based redaction is not a universal secret detector. Source minimization and
reviewed metadata remain required. Provider ports are trusted application integrations,
not public interfaces accepting arbitrary user-provided snapshots. New providers must
meet their canonical scope and sanitization contracts.

Bounds cover window, traversal, observations, candidates, references, deadlines, cache
size/TTL and response bytes. Optional source failures warn; scope/auth failures fail
closed. Raw exception messages and request content are absent from audit envelopes.
No persistence is added; sensitive process memory follows the serving process lifecycle.

The tests cover inert malicious runbooks/events/annotations, credential suppression,
cross-environment provenance, cross-installation snapshots, permission revocation,
cache principal isolation, TTL and read-only MCP schemas. Validation uses synthetic
fixtures and local transport; it does not qualify a live cluster or enterprise identity.
