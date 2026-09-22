# Kubernetes local testing

Mandatory tests are offline. No kubeconfig, token, real cluster, Docker, kind,
k3d or OpenShift installation is needed. Fixtures are synthetic; generated SDK
methods are exercised with mocked HTTP responses. FastMCP Client tests use the
real MCP protocol with a fake runtime backend. Existing STDIO/loopback HTTP
transport tests remain mandatory regressions.

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=agt_mcp --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m bandit -r src -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m agt_mcp validate-config --file config/server/kubernetes.example.yaml
```

Coverage includes branches and must reach 92%. SDK tests verify namespace paths,
read/list verbs, pagination, bounded streaming, deadline propagation, error-body
withholding, kubeconfig binding, in-cluster loading and TLS validation. Security
tests cover Secret exclusion, prompt injection, scope isolation and RBAC examples.
See the [runtime scenarios](../../tests/scenarios/runtime/README.md).

Optional live validation requires an existing authorized test cluster and an
explicitly selected read-only context. Copy and adapt the example locally, validate
it offline, then start the server with `python -m agt_mcp serve --file <local-file>`.
Call discover_environment for a single allowed namespace, inspect a known Pod,
then compare UID, ready endpoints, event timestamps and partial warnings with
the operator's read-only view. On Kubernetes without Route API, ordinary discovery
must work; on OpenShift test admitted/unresolved routes. Never add cluster-admin
or Secret permissions to make a test pass. No such live test was run for Sprint 2.

In-cluster authentication is unit-tested through the official loader boundary;
this sprint does not deploy the MCP into a cluster. Static-token/certificate
kubeconfigs are supported; exec and auth-provider plugins fail safely.
