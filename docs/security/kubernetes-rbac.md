# Kubernetes runtime RBAC

The internal MCP authorization gate and Kubernetes RBAC both apply. Neither
replaces the other. Start with a pre-existing read-only identity and one explicit
namespace. The adapter never grants privileges or modifies the cluster.

- [Namespace Role](../../config/rbac/runtime-reader.example.yaml): get/list only
  for the supported namespaced resource catalog.
- [OpenShift extension](../../config/rbac/openshift-route-reader.example.yaml):
  optional get/list routes in route.openshift.io.
- [Cluster extension](../../config/rbac/cluster-reader.example.yaml): optional
  Namespace/PV/CRD reads; requires explicit cluster_scoped configuration.

These are examples, not applied manifests. No ServiceAccount, production binding,
Deployment, Service, MCP Route, Helm chart or operator is delivered. A cluster
administrator decides whether to bind the appropriate Role to an existing
identity. Custom-resource allowlists need equally narrow group/plural permissions.
API discovery URLs ordinarily use the cluster's authenticated discovery grant;
a hardened cluster may require explicit discovery access. Do not grant wildcards
or cluster-admin to work around a 403: partial discovery is supported.

No Secret get/list/watch, token creation, impersonation, logs, exec, port-forward,
watch or mutation permissions are required. ConfigMap read permission necessarily
allows its data at the Kubernetes API boundary; the adapter drops content and
enforces response/ConfigMap byte limits before any MCP projection. Prefer removing
ConfigMap permission if that access is unnecessary; the category reports forbidden.
Secret names only come from existing workload/Ingress references. No Secret
content is requested or exposed, and service-account Secret values are unresolved.

Tests inspect every example rule and reject broad or modifying privileges. These
offline checks cannot prove effective permissions of a real cluster identity.
