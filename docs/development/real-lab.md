# Explicit real-lab profile

Default pytest excludes `tests/real_lab` at collection, so CI needs no network,
Docker, Kubernetes, OpenShift or 3scale. Execute explicitly:

```sh
python -m pytest -m real_lab --real-lab -q
```

Absent Docker or `AGT_REAL_LAB_CONFIG` yields clear SKIP/NOT EXECUTED reasons;
configured but broken infrastructure fails instead of silently skipping.
This profile does not install any platform software or apply cluster objects.

## Existing cluster (read-only)

Set `AGT_REAL_LAB_CONFIG` to an operator-owned configuration file based on
`config/server/kubernetes.example.yaml`, with exact namespace/context/cluster and
a least-privilege reader identity. Configure both trace and diagnosis tools and
their existing capabilities (see deploy/base/configmap.yaml). For LOCAL use
kubeconfig with token/certificate auth; exec/auth-provider plugins are rejected.
For IN_CLUSTER use ServiceAccount and run this test profile from an externally
prepared test Pod; the production image deliberately excludes pytest.

Set `AGT_REAL_LAB_QUERY` to a JSON resource selector, for example
`{"kind":"Service","name":"lab-backend","namespace":"agt-lab"}`.
The test discovers resources, inspects that resource and Events/topology, derives
its canonical ID, builds a Virtual Trace and invokes diagnosis through FastMCP.
Keep probes disabled for this read-only smoke. The same profile exercises either
auth mode; it does not assert a live mode passed unless actually executed.

For OpenShift/3scale additionally set `AGT_REAL_LAB_GATEWAY_ID` and configure the
existing APIManager allowlist, optional Route/APIManager Role and semantic tools.
It then calls existing gateway discovery and semantic topology. No 3scale
installation is required or automated. Prometheus configuration uses the existing
opt-in source; do not imply that fixture telemetry validates a live provider.

An operator with an existing kind/k3d/Docker installation may prepare
`deploy/examples/lab.yaml`: Namespace, Deployment, Service, ConfigMap, optional
unresolved SecretReference and Ingress. Kubernetes generates EndpointSlices from
the Service selector. The fixture Pod sleeps; it is an inventory fixture, not an
HTTP application or proof of connectivity. Do not create a Secret for its optional
reference. Reader RBAC is supplied separately by the operator. The MCP/test never
creates, patches, restarts or deletes these objects. Cleanup is an explicit operator
action confined to the dedicated lab namespace.

## Container smoke

Docker must already be installed with a usable daemon. Set `AGT_PYTHON_IMAGE` to
an approved Python 3.12 slim Linux image digest. The opt-in test builds locally,
starts the image with arbitrary UID 12345:0, read-only root, tmpfs /tmp, dropped
capabilities and a generated ephemeral reader token, then calls real HTTP MCP
list_tools/system_health/list_capabilities. It sends SIGTERM via docker stop,
checks zero exit, scans logs for the token and removes only its own uniquely named
container/image. This is distinct from live cluster qualification.

## Qualification record

For each target record image digest, platform, Kubernetes/OpenShift versions,
namespace scope, LOCAL versus IN_CLUSTER, auth/TLS policy, discovery limitations,
MCP result and shutdown result. Never include tokens, kubeconfig or Secret values.
Record PASS / FAIL / NOT EXECUTED separately for Kubernetes, OpenShift, 3scale
and container execution. Offline architecture/security tests and real loopback HTTP
integration remain mandatory irrespective of platform availability.
