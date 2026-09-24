# Probe safety boundary

Network probes are active read-only observations with external effects. They require
explicit execution mode and a separate probe.execute.active_readonly grant. Planning
alone performs no DNS or network access. The default is disabled/plan_only.

Tools never accept a destination, arbitrary request, HTTP header, credentials, payload,
redirect policy or serialized plan. The server resolves scoped cached IDs. Targets come
from operator-approved configuration and scoped trace membership. Configuration provenance
is checked against the exact endpoint and checksum before every stage. Changing the
configuration requires rebuilding the runtime; cached IDs are not transferable.

Hostnames and paths are normalized/restricted. Credential URLs, alternate numeric IPv4,
zone identifiers, malformed labels, query strings, fragments and path escapes are rejected.
Policy checks environment, host, port, protocol, timeout and DNS addresses. Deny CIDRs
override allow CIDRs. RFC1918, loopback and link-local access requires an explicit matching
network; broad public ranges are insufficient. Metadata addresses remain blocked even
when a range is otherwise approved. Multicast/unspecified/broadcast targets are blocked.
IPv4-mapped IPv6 cannot bypass IPv4 checks. DNS answers are checked as a whole and pinned;
the TCP/TLS/HTTP socket never independently resolves an approved hostname again.

Redirects are not automatic. Every redirect needs an exact configured endpoint associated
with the same resource/environment plus fresh policy/DNS validation. HTTPS downgrade,
unapproved hosts, relative URLs, credentials and query/fragment URLs are blocked. Zero
redirects is the default. HTTP supports only HEAD/GET without body/authentication. It
does not use proxy environment variables, cookie jars, auth hooks or application secrets.

TLS chain and hostname verification remain enabled; no unverified diagnostic retry.
Metadata is bounded and redacted; no key/certificate blob is returned. Errors carry
stable categories, not raw messages. Response bodies and authentication/cookie headers
are never emitted; only numeric Content-Length is retained. Audit includes request and
correlation IDs, environment, target ID/origin, type, duration, status and policy decision.

Per-request probe/parallel/time/budget limits bound work. Cancellation closes writers
through finally blocks and is audited as CANCELLED; dependent stages never run after a
failed prerequisite. External cancellation propagates through the existing MCP boundary.
Trace/plan caches enforce principal/environment, TTL, count and response-size bounds.

Observed failure is not root cause: no firewall inference, Redis protocol claim or database
failure assertion follows automatically from TCP/TLS outcomes. Provenance and missing
evidence remain explicit during reuse of the existing evaluator. No LLM or external
content supplies executable behavior. Production rollout and authenticated probes are
outside this sprint. Offline tests use fake resolvers, injected executors and ephemeral
127.0.0.1 servers with generated test-only TLS certificates.
