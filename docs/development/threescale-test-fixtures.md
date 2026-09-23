# 3scale fixtures and tests

tests/threescale_support.py constructs the synthetic healthy-threescale-216
fixture: APIManager, ten workload roles, Services, Routes, EndpointSlices, Pods,
ConfigMap references, documented external Secret references and a related Event.
It also includes unrelated backend-payments. No real credentials or cluster data
are used. Fake credential sentinels are deliberately present only in raw fixtures.

The fixture is normalized by the real Kubernetes adapter over a fake SDK port.
The resulting RuntimeSnapshot is injected through FakeRuntime into the actual
ThreeScaleGatewayAdapter. FastMCP Client tests exercise all four gateway tools
through the protocol and assert one runtime discovery per gateway operation.

Variants cover external Redis/System DB without Deployments, Zync disabled,
unknown/unsupported versions, forbidden resources, labels without ownership,
conflicting labels, missing Service, unready endpoints, Pod recreation, namespace
separation, two roots in one namespace, malicious metadata and oversized raw CR
fields. Architecture tests reject SDK/network/shell imports in the semantic layer.

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=agt_mcp --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m bandit -r src -q
.\.venv\Scripts\python.exe -m agt_mcp validate-config --file config/server/threescale.example.yaml
```

Required coverage is 93% including branches. All 251 Sprint 2 tests remain in
the suite. ADR/RBAC structural counts grow with the new ADR and Role. The legacy
disabled datasource configuration remains accepted. No test requires Docker,
OpenShift, kubeconfig credentials, Admin Portal access or network probes.

Optional live structural validation requires an existing authorized read-only
context and explicit operator setup. This sprint provides no live deployment,
production credentials or automatic environment changes.
