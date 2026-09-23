# 3scale data access boundary

The semantic adapter consumes canonical runtime data only. It imports neither
the Kubernetes client nor shell/network libraries. It never invokes oc, kubectl,
exec, port-forward, probes, Admin Portal or APIcast management APIs.

Only [get/list APIManager](../../config/rbac/threescale-reader.example.yaml) is
added to the existing [runtime RBAC](kubernetes-rbac.md). There are no Secret
permissions, write verbs, wildcard grants, service-account token reads or bindings.
The manifest is an example and is not applied automatically.

Secret policy remains reference-only for backend-redis, system-redis,
system-database, zync, certificates and provider credentials. Neither .data nor
.stringData is requested, decoded, logged, embedded or persisted. Names from
observed workload references can map documented connection roles; host, port,
username and password remain unknown. External does not mean reachable or healthy.

APIManager raw content stays inside the runtime projection. Only fixed boolean
configuration fields and bounded recognized labels can leave it. Unknown fields,
annotations, Event messages, ConfigMap values, TLS keys and container literals
are withheld. A malicious instruction in metadata cannot change permissions,
trigger a Secret query or become an executable instruction. Every returned
external observation remains untrusted, even when its syntax is safe.

Internal authorization precedes discovery. Namespace configuration narrows runtime
scope. Canonical snapshot environment/namespace is rechecked by the composed
adapter. Installations are partitioned using namespace and observed UID ownership;
metadata-only candidates cannot receive HIGH confidence. Partial reads produce
warnings rather than fabricated absence. Unexpected adapter exceptions map to
safe MCP errors without original exception messages or payloads.

Fake-client tests prove these boundaries for synthetic input. They do not certify
effective RBAC or compatibility of an untested production cluster. No live cluster
was contacted during Sprint 3 validation.
