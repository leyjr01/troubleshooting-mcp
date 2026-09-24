# ADR-0019 — Virtual Trace and Safe Probe Architecture

## Status

APPROVED — 2026-09-24, Sprint 7.

## Context

Sprint 6 distinguishes structural evidence from present incident causes and leaves
connectivity requirements explicit. Network observations can add missing facts but
have externally observable effects, even when they never mutate application state.

## Decision

VirtualTraceBuilder traverses bounded canonical runtime and semantic relationships.
STRUCTURAL_TRACE describes declared relationships; PROBED_TRACE adds point-in-time
observations from the MCP process network vantage point. Neither verifies an entire
request path. Each hop preserves structural status, observations, evidence references,
warnings and provenance; unresolved dependencies stay visible.

ProbePlanner accepts scoped traces or cached TroubleshootingResult missing evidence.
Targets come only from operator-configured approved endpoints associated with a
resolved resource in the trace. Tools accept cached IDs, never hosts, URLs, arbitrary
plans, headers or payloads. No Secret is read to discover an endpoint. Missing Route
Service references block planning; other unresolved targets remain unavailable.

ProbePolicy checks environment, exact approved endpoint identity and provenance,
host, protocol, port, timeout and CIDRs. All DNS answers must pass policy before
connection; numeric addresses are pinned to sockets while TLS SNI/hostname and HTTP
Host retain the approved name. No resolver is invoked by subsequent sockets. Exact
host allowlists and explicit network allowlists are both required. Private/loopback/
link-local ranges need explicit corresponding CIDRs; broad public ranges cannot
implicitly authorize them. Metadata, unspecified, multicast and broadcast targets
are rejected. IPv4-mapped IPv6 is checked as IPv4; zone identifiers are rejected.

Configuration defaults: probes disabled, execution_mode plan_only, redirects zero.
Execution requires probe.execute.active_readonly plus source/trace permissions and
probe.plan. DNS/TCP/TLS/HTTP are active network observations, distinct from Kubernetes
reads. The execute tool advertises openWorldHint and is not idempotent. No application
credential, client certificate, API key, proxy environment or authentication header
is used. HTTP supports HEAD and explicitly configured GET, with no request body and
no response body returned. Only bounded numeric Content-Length is retained.

Redirects are manual, bounded and require an exact approved endpoint for the same
resource/environment, a fresh policy decision, DNS check and address pinning. No
HTTPS downgrade, credential URL, query/fragment or relative redirect is followed.

ProbeExecutor is an injected protocol. The concrete standard-library asyncio/socket/
TLS implementation lives under datasources. TCP closes without payload; TLS enforces
system trust and hostname verification. TCP success, handshake completion, certificate
verification, chain validation and hostname validation remain separate. On a verified
handshake rejection, completion is UNKNOWN rather than inferred successful. There is
no insecure retry. HTTPS is skipped after failed TLS. Generic TCP success never proves
Redis/database protocol health; HTTP 503 is an observed status, not a causal finding.

Bounded per-target DNS → TCP → TLS → HTTP(S) chains run with configured concurrency,
timeouts, total budget and count limits. Failures skip dependent stages. Cancellation
is audited as CANCELLED and propagates to the existing request cancellation boundary;
budget expiry returns cancelled/remaining unexecuted stages. Each result becomes
ProbeEvidence with checksum, target provenance, timestamp, duration and safe metadata.
Audit logs contain IDs/decision/status, never URLs, bodies, headers or exceptions.

Correlation refresh reuses the existing correlation engine with the original bounded
runtime snapshot and probe atoms; it does not recollect runtime data. The existing
HypothesisEvaluator evaluates generic TCP/TLS conditions. Two definitions extend the
catalog; external Redis/database protocol hypotheses remain inconclusive. Refreshed
inference does not use knowledge/history enrichment; the original context remains
available. Original snapshot age is preserved, not relabeled as freshly collected.

## Consequences

Safe defaults require deliberate operator endpoint/CIDR configuration. Plans/results
are principal/environment-scoped, bounded, expiring and process-local. Permission
checks repeat on use. Config changes require rebuilding the runtime. The first approved
DNS address is used; multi-address failover, authenticated probes, custom trust-store
configuration, continuous monitoring and application protocol probes remain future work.
OS DNS resolution may finish in its worker after coroutine timeout; no connection is
created from late results. Coverage and tests are offline, including local TLS fixtures.

## Alternatives Considered

- Arbitrary tool URLs: rejected due to SSRF and missing target provenance.
- Transparent redirects/proxies: rejected because destination policy could be bypassed.
- Reading Secrets for endpoints or client certificates: outside approved access policy.
- An independent diagnosis engine: rejected; reuse correlation and hypothesis evaluation.
- Treating topology or transport failure as root cause: rejected by evidence-first design.
