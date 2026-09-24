# Virtual trace and safe probes

FastMCP → TraceService → VirtualTraceBuilder / ProbePlanner → ProbePolicy →
ProbeRunner → injected ProbeExecutor → ProbeEvidence → correlation refresh →
existing HypothesisEvaluator. Networking stays in datasources/probe_network.py;
trace, probe and troubleshooting cores have no concrete network/vendor imports.
See [ADR-0019](../adr/0019-virtual-trace-and-safe-probe-architecture.md) and
[security boundary](../security/probe-safety.md).

## Models and semantics

VirtualTrace has separately typed relationships and TraceHops. Hops contain a resource,
component or unresolved dependency reference, depth, structural status, original
observations/evidence and provenance. Deterministic traversal supports outgoing,
incoming and both directions. Defaults: depth 3, 40 hops/nodes, 8 branches per node.
The upstream correlation snapshot has its own limits; trace cannot recover omitted nodes.
Limit warnings propagate. Unresolved Service routing targets prevent probe planning.

STRUCTURAL_TRACE never means communication works. PROBED_TRACE only means some
observations were attempted; communication_verified remains false. Each probe has its
own status and timestamp. Blocked-only plans leave the trace structural. Explain exposes
relationships, evidence, warnings, the plan, policy reasons and executed probe results.

Targets are derived from approved configuration and must match a resolved resource in
the scoped trace. Endpoint identity, environment, resource reference and checksummed
configuration provenance are retained. No target guessing or Secret escalation occurs.
For diagnosis planning, only resources with missing evidence are considered. Missing
protocol capabilities are not falsely fulfilled by generic transport observations.

Probe types/capabilities: DNS/dns.resolve, TCP/tcp.connect, TLS/tls.handshake,
HTTP and HTTPS/http.request. Chains follow DNS → TCP → optional TLS → optional HTTP(S).
Concrete executor capabilities are checked during planning and execution. Default limits:
16 probes, 2 parallel chains, 3 seconds per probe, 15 seconds total, 8 DNS addresses,
8192 response-header bytes, zero redirects. Cache: 16 records, TTL 300 seconds.

Each result retains target, status, timestamp, duration and safe structured observation.
ProbeEvidence pairs that result with canonical Evidence (probe.dns/tcp/tls/http metadata)
and enforces its checksum/scope. Correlation keeps its existing sanitized projection;
full safe observation metadata remains in ProbeEvidence on the trace. TCP/TLS signals
are distinct from workload readiness. DNS failure, TCP refusal/timeout, TLS verification,
HTTP protocol/timeout and policy blocks have stable error categories; no exception text.

## MCP contracts

All tools accept optional environment_id and correlation_id. Register tools explicitly.
Application operation diagnose must be enabled. Defaults never execute network probes.

| Tool | Input | Permission and output |
| --- | --- | --- |
| trace_resource | CorrelationQuery with resource_id; direction/max_depth optional | trace.read plus correlation/source ACLs; structural trace |
| trace_gateway_component | CorrelationQuery with component_id; optional gateway_id | Same plus semantic source ACLs; related runtime/component trace |
| plan_probes | trace_id or troubleshooting_id | probe.plan plus original read ACLs; requests, allowed/blocked reasons, capabilities |
| execute_probe_plan | plan_id | probe.execute.active_readonly, probe.plan and original read ACLs; trace with ProbeEvidence and reevaluated diagnosis |
| explain_trace | trace_id | trace.read and original read ACLs; structural rationale, plan and observations |

Troubleshooting IDs require troubleshooting.read and a valid scoped diagnostic cache
entry. Caller permissions are never tool arguments. Cache reads repeat source checks;
expired, foreign and unknown IDs fail without network activity. Arbitrary URL-shaped
plan IDs cannot resolve to executable plans. Result IDs are process-local, not durable.

## Configuration

[Example](../../config/server/probes.example.yaml) is a merge fragment with placeholders,
not a standalone environment or an enabled production probe configuration. Replace
resource IDs with canonical runtime IDs, configure the actual environment and grant
only needed tools/permissions. Approved endpoint configuration and allowlists both apply.
No runtime endpoint is inferred from labels or Secret values.

## Limits

Probes run from the MCP host, not inside a Pod. OS DNS uses the host resolver and no
reverse lookup. Only the first approved address is connected; all answers must be safe.
TLS trust uses system defaults; no client credentials. Verification failure leaves any
unobserved stages unknown. Redirects require absolute, exact configured endpoints.
HTTP GET bodies are not consumed/returned; a server may still transmit bytes before close.
Execution changes no application state but is externally observable network traffic.
