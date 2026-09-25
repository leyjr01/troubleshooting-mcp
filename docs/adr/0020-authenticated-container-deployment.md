# ADR-0020 — Authenticated container deployment

## Status

Accepted — Sprint 10, 2026-09-25; implementation of explicitly requested deployment scope.

## Context

ADR-0011 defined a loopback-only development server. A Kubernetes/OpenShift Pod
must explicitly bind a routable interface while retaining all read-only,
environment and source permissions. Production SSO and authorization redesign
remain outside this sprint.

## Decision

Preserve loopback/STDIO defaults. Allow explicit 0.0.0.0 HTTP only with a scoped
credential reference. FastMCP's TokenVerifier authenticates one configured bearer
reader; existing local-client application ACLs still authorize every operation.
The name local-read-only is retained for compatibility: it is an ACL mode, not
a claim that an authenticated Pod listener is loopback-only. No caller controls
the application principal. This deliberately does not provide multi-user SSO.

Resolve a minimum 32-character ASCII token once at startup through the existing
CredentialProvider port, from an allowlisted environment variable or operator
configured mounted-file reference. Fail closed on missing/invalid credentials;
restart for rotation. Mounted credentials are Pod-local input, not Secret API
discovery. No Secret list/get permission is added. Token values never enter
configuration output, responses or audit events. Require exact Host allowlists,
reject browser origins and do not trust forwarded headers. Require TLS termination
and restricted network access outside the Pod for remote clients.

Expose only minimal unauthenticated /livez and /readyz status; readiness reuses
the initialization state used by system_health, not downstream availability.
Uvicorn performs bounded graceful shutdown and the existing runtime closes adapters.

Use namespace Roles with get/list, a dedicated ServiceAccount, restricted Pod
security, read-only root filesystem and bounded /tmp. The image uses non-root
by default and supports an assigned arbitrary UID. No runtime subprocesses,
deployment MCP tools or hot reload. Lab/container tests are explicit opt-in.

## Consequences

This adds a deployment mode to ADR-0011 without reopening its development-mode
decision or the approved runtime/probe/semantic ADRs. A shared bearer is a bounded
initial integration model; production identity, rotation automation, mTLS between
proxy and Pod and multi-user policies need a separately authorized design.
HTTP health reveals no inventory or configuration. Local SDK credentials remain
lazy until operations; external API failure need not kill a healthy server.

## Alternatives Considered

- Anonymous remote MCP or trusting forwarded identity headers: rejected.
- New OAuth/SSO platform: outside scope.
- Root/privileged container or cluster-wide Secret reader: rejected.
- Dependency-based liveness: would restart MCP during the incident it diagnoses.
- Replacing the existing runtime, evaluator or credential abstraction: unnecessary.
