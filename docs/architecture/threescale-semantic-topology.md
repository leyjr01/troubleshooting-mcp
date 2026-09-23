# 3scale semantic topology

Installation IDs combine environment, namespace and root runtime identity.
Components use installation plus semantic role, remaining stable across Pod
replacement. Staging/production, System app/sidekiq, Backend listener/worker/cron,
Zync app/queue and database roles remain separate. Role prefixes provide logical
System/Backend/APIcast/Zync grouping without inventing extra infrastructure.

Runtime resources attach through UID ownership, Service selection, EndpointSlice
membership and Route/Ingress backend references. Hostname resemblance is never
an association rule. References to ConfigMap, Secret and PVC are retained as
leaves. A missing Service remains unresolved and is never fabricated. Runtime
edges remain distinct from product-semantic edges and preserve original provenance.

Implemented semantic relations:

- manages: APIManager ownership supports component management.
- component_of: component belongs to a scoped installation.
- exposes: component-to-runtime representation bridge, not a reachability claim.
- configured_by: observed workload ConfigMap/Secret reference.
- uses_storage / uses_queue: documented dependency role supported by references.
- describes_connection_to: documented Secret name identifies an external role.

Runtime routes_to remains in the runtime graph. No authorizes_via or arbitrary
depends_on edge is invented without observable configuration. External dependency
nodes carry unresolved endpoint status and detection evidence. Backend Redis
storage and queues remain separate even when referenced through one Secret.

Topology depth 1 includes the installation and semantic components; depth 2 adds
their direct runtime representation; depth 3 permits the same already-attached
leaf resources. Nodes are limited deterministically, and edges are clipped to
returned node IDs. A truncation flag makes incomplete output explicit. Runtime
unresolved references and forbidden/partial warnings survive the semantic layer.
Evidence timestamps preserve event time and retrieval provenance; statuses such
as unavailable replicas or Pending remain observations, not explanations.

Future bridges are intentionally unimplemented:

- ExternalDependency.mapping_reference → configured DataSource inventory.
- Component type/version → knowledge/RAG/documentation/runbooks/incidents.

Neither bridge initiates a database, Redis, HTTP, TCP, DNS or TLS connection.
