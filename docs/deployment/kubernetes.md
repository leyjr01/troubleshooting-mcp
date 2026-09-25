# Kubernetes deployment

Sprint 10 supplies deployment definitions and offline/loopback qualification.
Docker and a real cluster were unavailable in the implementation environment;
image execution and live qualification remain operator validation steps.

## Build and configuration

Build with an approved **Python 3.12 slim Linux image by digest**:

```sh
docker build --build-arg PYTHON_IMAGE="$APPROVED_PYTHON_IMAGE" -t agt-mcp:sprint10 .
```

The build rejects an image without `@sha256:<64 hex characters>`. Publish an
immutable commit tag/digest and substitute it in `deploy/base/deployment.yaml`;
do not use latest. The unchanged `requirements.lock` is a Windows/Python 3.12
development snapshot, used as constraints rather than installed wholesale.
Only runtime dependencies of the project are installed. Linux-only keyring
dependencies are pinned in `deploy/runtime-linux.constraints`; build tools are
pinned and isolated in the builder. Binary dependency wheels are required, so
unsupported target platforms fail instead of silently compiling another stack.
Archive the wheelhouse/image digest in the trusted build system for artifact
reproducibility. Linux resolution/build has not been executed here. No SBOM tool
or build service is installed by this repository.

Linux dependency metadata: [SecretStorage 3.3.3](https://pypi.org/project/SecretStorage/3.3.3/)
and [jeepney 0.8.0](https://pypi.org/project/jeepney/0.8.0/).
Builder pins: [setuptools 75.8.0](https://pypi.org/project/setuptools/75.8.0/)
and [wheel 0.45.1](https://pypi.org/project/wheel/0.45.1/).

`deploy/base/configmap.yaml` contains only non-sensitive configuration. Replace
environment, namespace, cluster label, exact allowed Hosts and image before use.
Create an operator-managed Secret named `agt-mcp-auth` with key `token`, a random
ASCII bearer of at least 32 characters, through your approved secret-management
process. No Secret object or token is committed. Kubelet mounts this credential;
the MCP reads its configured local file, never the Kubernetes Secret API.
The dedicated ServiceAccount has no Secret read/list permission.

Alternative: configure `http_token.provider: environment`, reference
`AGT_HTTP_TOKEN` and populate that variable through `secretKeyRef`; do not put
the token in a ConfigMap or command argument. Mounted references use
`provider: mounted-file` and `reference: file:/var/run/agt-auth/token`.
Credential rotation/configuration changes require restarting the Pod.

## Installation and namespace scope

After reviewing the substitutions and creating the credential externally:

```sh
kubectl apply -f deploy/base/namespace.yaml
kubectl apply -f deploy/base/
kubectl rollout status deployment/agt-mcp -n agt-mcp
```

These are operator actions, not application runtime behavior. Do not grant the
application deployment verbs. Base Role grants only get/list of existing runtime
resources. Kubernetes API discovery uses authenticated discovery permissions
normally provided by the cluster; a hardened cluster may require its administrator
to grant read-only API discovery. No wildcard or cluster-wide resource role is shipped.

For one namespace, keep the Role/RoleBinding there and bind `agt-mcp` ServiceAccount.
For multiple namespaces, copy the Role and RoleBinding into **each explicitly
authorized namespace**, retaining the subject's ServiceAccount namespace. Add
only those namespaces to configuration include lists. Prefer separate environment
bindings when permissions differ; application environment ACLs still apply.
Do not silently convert these bindings into ClusterRoleBinding.

## Transport, health and shutdown

Local defaults remain STDIO and 127.0.0.1. The ConfigMap explicitly selects HTTP,
0.0.0.0:8000, `/mcp`, exact hostnames and a credential reference. Container CMD
starts the documented Python module entrypoint, not a debug server. A client
uses `Authorization: Bearer ...` from its credential store. Forward the header
through your trusted TLS proxy; never log it. Browser origins are rejected.
The shared reader's authorization mode is still named local-read-only for
compatibility; it never grants permissions beyond configured environment/tool ACLs.

Service is ClusterIP. Terminate external TLS at an Ingress, trusted reverse proxy
or optional OpenShift Route; do not expose bare HTTP to untrusted networks.
The proxy-to-Pod hop is HTTP in this initial profile. No certificate is committed.
Use network isolation; end-to-end mTLS is a future deployment hardening choice.

`/livez` returns only process/server status. `/readyz` returns 200 only after
configuration/registries/lifecycle initialize; before/after it returns 503.
Neither endpoint calls Kubernetes, Prometheus, Redis or databases. `system_health`
reuses the same initialized state behind MCP authentication/authorization.
Kubelet probes send Host 127.0.0.1; clients use configured service/proxy hostnames.
Startup budget is 60 seconds. SIGTERM is handled by Uvicorn; request draining is
bounded to 30 seconds and the Pod grace period is 45 seconds. Adapters close via
the existing AsyncExitStack. Linux SIGTERM is checked by the opt-in container test;
local integration validates the same server shutdown/lifecycle using should_exit.

## Security, storage and operations

No privilege escalation; all Linux capabilities dropped; RuntimeDefault seccomp;
non-root; read-only root filesystem. Only `/tmp` is writable (128 MiB emptyDir).
No fixed Pod UID/fsGroup is imposed. Initial requests 100m/256Mi and limits
1 CPU/512Mi are conservative starting points, **not profiled production sizing**.
Logs use stderr and the existing structured audit events; no persistent log files.

IncidentBundle remains serialized data. An operator may export it to `/tmp` or
copy it through a client; no new tool accepts an output path or creates permanent
storage. Process-local caches/indexes remain ephemeral. No database is added.

`deploy/examples/networkpolicy.yaml` is optional and intentionally uses a reserved
API-server CIDR placeholder. Review CNI/NAT behavior and replace selectors/CIDRs
for MCP ingress, API egress, DNS, Prometheus and approved probe destinations.
Never apply this template unchanged. Probes remain disabled/plan_only until
operator configuration, permissions and target provenance all permit execution.
Prometheus remains disabled unless the existing observability configuration is
explicitly supplied, with verified TLS, credential references and exact bindings.

See [OpenShift](openshift.md), [operations](operations.md),
[real lab](../development/real-lab.md) and [deployment ADR](../adr/0020-authenticated-container-deployment.md).
