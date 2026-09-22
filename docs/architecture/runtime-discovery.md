# Runtime discovery — Sprint 2

FastMCP tools delegate to application services, the RuntimeAdapter core port,
then the Kubernetes adapter. Only the client boundary imports the official SDK.
The seven Sprint 1 tools remain enabled by default. The five new tools require
explicit enabling and runtime permissions; see the
[example](../../config/server/kubernetes.example.yaml).

## Configuration and authentication

Each enabled environment binds a cluster, runtime provider, authentication mode
and namespace scope. `kubernetes` uses the common catalog; `openshift` also enables
Route discovery. Kubeconfig defaults to `~/.kube/config`; explicit context and
cluster binding prevent accidental context switching. A selected context must
match the configured cluster alias. Relative certificate paths resolve against
the kubeconfig directory. Static tokens and certificate authentication are
supported; exec/auth-provider credential plugins are deliberately unsupported.
Kubeconfig is never written back. In-cluster credentials use the SDK loader
and per-instance Configuration. HTTPS with certificate verification is required.

An empty include list means the environment namespace, otherwise the selected
kubeconfig namespace, otherwise `default`. Exclusions always win. Explicit
disallowed namespace requests fail before loading credentials. Environment
authorization precedes adapter execution. No credentials are returned or logged.

## Inventory and extensions

Namespaced catalog: Pod, Deployment, ReplicaSet, StatefulSet, DaemonSet, Service,
EndpointSlice, ConfigMap, PersistentVolumeClaim, ServiceAccount, Event, Ingress,
NetworkPolicy. Optional cluster catalog: Namespace, PersistentVolume,
CustomResourceDefinition. `cluster_scoped` defaults to false.

Discovery checks v1, apps/v1, networking.k8s.io/v1, discovery.k8s.io/v1,
storage.k8s.io/v1, rbac.authorization.k8s.io/v1, apiextensions.k8s.io/v1 and
route.openshift.io/v1 capabilities. RBAC/storage discovery does not imply listing
all objects in those groups. Route absence is normal on Kubernetes.
Only explicitly configured custom resource types are queried; CRD discovery
does not enable arbitrary instance enumeration. Custom resources expose identity
and metadata projection, never vendor-specific semantics or spec content.

## Tools and return semantics

All five tools take `environment_id`, optional `correlation_id`, and a `query`
object. Example inspect arguments:

```json
{"environment_id":"dev","query":{"namespace":"example","kind":"Pod","name":"app-pod","depth":1,"limit":50}}
```

| Tool | Behavior | Internal permission |
| --- | --- | --- |
| discover_environment | Counts, APIs, safe connection health, completeness, warnings | runtime.discover |
| inspect_resource | Canonical resource, observations and bounded neighborhood | resource.read |
| inspect_events | Related UID-filtered Event observations | event.read |
| find_related_resources | Bounded adjacent resources and graph | topology.read |
| get_resource_topology | Bounded graph, provenance and unresolved references | topology.read |

Inspect/related/topology require kind/name and an unambiguous namespace; api_version
disambiguates configured custom kinds. Namespace is the discovery scope filter;
kind/name/api_version filter the summary counts while scoped topology collection
still resolves surrounding relationships.
`depth` is 1..3, `limit` is 1..200, `direction` is both/dependencies/dependents,
and `relationship` filters edges. Direction refers to stored edge orientation,
not a claim about operational dependency. `since` is timezone-aware for Events.
Event ordering is timestamp ascending within the bounded collected window, not
an assertion that the API returned the latest events. No opaque API continuation
token crosses MCP; explicit limits, warnings and truncation flags bound responses.

## Identity and relationships

Resource IDs hash environment, cluster, namespace, API version, kind, name and
UID. Recreated resources have new identities. ownerReferences require matching
UIDs; missing/stale references cannot be repaired merely by matching names.
Endpoint address nodes are snapshot-scoped to their slice and index, never a
permanent IP identity. All graph nodes and edges are deterministically sorted.

Relations: owns, selects, has_endpointslice, targets, has_endpoint, routes_to,
references_configmap, references_secret, mounts, bound_to, uses_service_account.
A missing owner is retained as an unresolved managed_by reference.
Service selects Pod uses labels. Service has_endpoint uses EndpointSlice readiness;
ready null means usable per Kubernetes semantics. Readiness, serving, terminating,
addresses, ports, protocol, targetRef, hostname, nodeName and zone are projected.
NetworkPolicy selectors describe configuration and do not establish that traffic
is blocked. Route/Ingress routing and TLS mode are structural observations.

Each edge carries mechanism, source, retrieval time and qualitative confidence.
Provenance hashes the safe projection, never raw content. Status and known Event
reasons become OBSERVATION Evidence with timezone-aware UTC timestamps. Unknown
reasons/free messages are withheld. No causal findings or recommendations are made.

## Safety, health and completeness

SecretReference nodes come only from workload/Ingress references; type and keys
remain unknown. Source edges identify every referencing resource and usage.
No get/list/watch Secret request or permission is used. ConfigMap content is
discarded before retention; exceeding max_configmap_bytes emits truncation.
The HTTP response also has a strict streamed byte cap. Arbitrary labels,
annotations, Event messages, environment literals, TLS keys and custom specs
are omitted. Structural fields are bounded and all external data remains untrusted.

Defaults: 5 namespaces; 100 resources per type per namespace; 50 events; 1000
edges/unresolved references; 500 nodes; depth 3; ConfigMap 16 KiB; API response
1 MiB; API page 50. These can be reduced or increased only within validated caps.
The application envelope has its independent max_payload_bytes limit. Excess
output fails safely rather than emitting an unchecked partial JSON document.

SDK requests receive the remaining execution deadline (also capped by runtime
timeout). No automatic retry policy is added. 401 is fatal authentication failure;
403 per category yields partial discovery; 404 means absent resource or unsupported
API; timeouts/unavailability are categorized without exposing server bodies.
Connection health reports API accessibility and namespaces with successful reads;
it does not expose host URLs, tokens or certificate material. Per-category counts
are objective collection outcomes, not a fabricated completeness percentage.
Snapshots are non-atomic and uncached. Missing targets remain unresolved with
not_found/not_observed/forbidden/ambiguous resolution and structured warnings.
