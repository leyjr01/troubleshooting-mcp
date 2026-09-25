# Sprint 10 validation

Baseline: `c80518197268c3b99d49f8fc516a0af03f560f10`, Sprint 9.1 PASS.
Impact: HIGH. **PASS for deployment readiness**; real infrastructure NOT EXECUTED.
AGENTS.md and existing approved ADRs unchanged. One containing sprint commit;
resolve with `git log -1 --format="%H %s" -- PROJECT_STATE.md`.

## Delivered scope

Authenticated external HTTP is opt-in; loopback remains the default. Native FastMCP
token verification resolves an environment or explicitly allowlisted mounted-file
credential and preserves the existing principal, environment and operation ACLs.
The same runtime/services/SDK power local kubeconfig and in-cluster operation;
no diagnostic engine, adapter or remediation path was introduced.

The image definition requires a digest-pinned Python 3.12 Linux base, installs only
runtime wheels, uses non-root execution and supports an arbitrary UID by design.
Manifests include namespace, dedicated ServiceAccount, get/list-only namespaced
RBAC, non-sensitive ConfigMap, restricted Deployment, Service and optional
OpenShift Route/reader role. No Secret API permission or Secret object is supplied.
The operator provisions the server's authentication credential separately.

Readiness reuses runtime initialization, liveness is minimal, and external API
availability is independent of either endpoint. Shutdown preserves runtime client
cleanup; the server timeout fits inside the Pod termination grace period.
Probes remain disabled, with existing authorization and SSRF boundaries intact.

See [Kubernetes](../deployment/kubernetes.md), [OpenShift](../deployment/openshift.md),
[operations](../deployment/operations.md), [real-lab profile](real-lab.md) and
[ADR-0020](../adr/0020-authenticated-container-deployment.md).

## Reused and focused evidence

- Approved baseline: 1092 PASS, 97.38% coverage, 35 scenarios and six golden PASS.
- Initial configuration/runtime baseline: 62 PASS.
- Focused deployment validation: 27 unit cases plus authenticated HTTP passed
  across the initial run and correction-only recheck (10 PASS, 17 deselected).
  Initial failures exposed mounted-reference syntax and a missing cluster field;
  both were fixed before the checkpoint. HTTP tests use the installed httpx2 client.
- L2 checkpoint: **117 PASS**, zero failures/errors/skips, 10.916 seconds.
  Includes actual loopback HTTP bearer rejection/success, scope denial, health,
  graceful lifecycle cleanup, unavailable Kubernetes, transport compatibility,
  runner settings/log redaction, SSRF/probe protections, architectural boundaries,
  kubeconfig/in-cluster SDK behavior, documentation and all **six golden PASS**.
  Artifact: `sprint10-checkpoint.xml.tmp` (ignored local evidence).
- Explicit opt-in discovery: **2 SKIPPED**, 1120 deselected at that checkpoint;
  no Docker and no `AGT_REAL_LAB_CONFIG`. Default collection excludes real_lab.

## Final gates

Single complete regression: **1124 PASS**, zero failures/errors/skips, **115.93s**.
All 1092 baseline tests retained, 32 added; no second full regression.
Strict diagnostic acceptance: **35/35 PASS**, **6/6 golden PASS**, zero false
positives, false negatives or recommendation failures.
Branch-inclusive coverage: **97.76%**, required >=97%: PASS.
Lint and formatting: PASS, 301 files. Strict mypy: PASS, 134 source files.
Bandit and installed dependency consistency (`pip check`): PASS.
Bandit initially flagged B104 for the explicit remote bind literal and comparison;
two inline exceptions document the required, authenticated behavior in ADR-0020.
No global security rule was disabled. These comments/formatting and documentation
are the only edits after regression; application behavior is unchanged.
The gate was rechecked on that exact comment-only version, without repeating tests.

Command:

```sh
python -m pytest --scenario-acceptance --cov=agt_mcp --cov-fail-under=97 --cov-report=term-missing --cov-report=json:coverage-sprint10.json.tmp --junitxml=sprint10-full.xml.tmp -q --tb=short
```

Artifacts (ignored, local): `sprint10-full.xml.tmp`, `coverage-sprint10.json.tmp`
and the existing scenario runner's `sprint9-scenarios.json.tmp` (now produced by
this complete run; the legacy filename does not indicate an old result).
Existing coverage exclusions and the project's configured 96% floor are unchanged;
the final command enforces this sprint's stricter 97% gate.

## Real infrastructure and limits

Kubernetes: **NOT EXECUTED**. OpenShift: **NOT EXECUTED**. 3scale: **NOT EXECUTED**.
Container build/smoke: **NOT EXECUTED**. No Docker, kind, k3d, kubectl or oc is
available; no platform software was installed and no cluster resources were changed.
The opt-in profile and operator commands are ready, but Linux image resolution,
arbitrary-UID execution, SCC admission, Route TLS and Linux SIGTERM remain unqualified.
Static artifact and local HTTP results do not claim live infrastructure acceptance.

The deployment requires operator-provided image digests, credentials and environment
bindings. Optional network policy is a template, not a universal cluster policy.
No production federation/SSO, HA, Operator, persistent database or automatic remediation.
Secret-content discovery remains forbidden; only the explicitly configured server
credential may be read through CredentialProvider and is never returned or logged.
