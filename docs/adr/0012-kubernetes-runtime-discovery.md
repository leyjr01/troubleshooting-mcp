# ADR-0012 — Kubernetes Runtime Discovery

## Status

APPROVED — Sprint 2, 2026-09-22; implementation of the approved sprint scope.

## Context

Sprint 1 exposes transport-neutral read-only services. Runtime topology requires
real Kubernetes API observations without coupling core models to SDK objects.
OpenShift is Kubernetes plus optional APIs, not a separate runtime implementation.

## Decision

Use the official `kubernetes==36.0.3` Python client, specifically its asynchronous
`kubernetes.aio` API. This release supports Python >=3.10; the project requires
Python >=3.12. Keep FastMCP 4.0.5 and every previous dependency pin unchanged.
`requirements.lock` records the resolved Windows/Python 3.12 development snapshot.

Only `datasources/kubernetes/client.py` imports the SDK. Each environment has its
own Configuration, ApiClient, authentication binding and namespace allowlist.
Kubeconfig loading never changes global defaults or persists credentials. TLS
verification is mandatory. Exec and auth-provider credential plugins are rejected
in this sprint: configuration must not execute arbitrary programs.

Use generated read/list methods and bounded API discovery requests. No writes,
watch, Secret reads, broad retries or cluster-global default discovery. The optional
OpenShift Route descriptor uses CustomObjectsApi and normal API availability checks.
Custom resources require an explicit group/version/plural/kind allowlist.

Project raw dictionaries inside the adapter into canonical Resources, Evidence
and Topology. Preserve UID-based ownership, unresolved references and collection
completeness. Distinguish label selection from ready EndpointSlice membership.
Evidence is observation, never root-cause inference. Secret nodes represent only
references; no Secret endpoint is called. ConfigMap content, Event messages,
annotations and custom specs do not cross the adapter boundary.

Enforce namespace, resource, node, edge, event, byte and depth limits; paginate
with Kubernetes continue tokens. Propagate the execution deadline to SDK calls.
Discovery is a bounded non-atomic snapshot; cache is unnecessary at this stage.

## Consequences

Five opt-in tools extend the seven existing local tools. Fake SDK and MCP client
tests are mandatory and need no cluster. In-cluster loading is prepared but no
MCP Kubernetes deployment is created. Live authentication, RBAC and server-version
compatibility still require operator validation against the intended cluster.

## Alternatives Considered

- kubectl/oc subprocesses: rejected; executable and output parsing boundaries.
- A second OpenShift runtime: rejected; duplicates common discovery logic.
- Sync SDK in thread pools: rejected in favor of native async cancellation.
- Raw YAML to MCP: rejected; secret and prompt-injection exposure.

References: [official client](https://github.com/kubernetes-client/python),
[EndpointSlice semantics](https://kubernetes.io/docs/concepts/services-networking/endpoint-slices/),
[RBAC guidance](https://kubernetes.io/docs/concepts/security/rbac-good-practices/).
