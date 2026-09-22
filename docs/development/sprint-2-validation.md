# Sprint 2 validation — 2026-09-22

Base commit: `42d0ee7c5683f74165835e36fabf744b6acc2d53`.
Baseline was clean and all 127 original tests passed before implementation and
after installing Kubernetes. All remain in the final suite. The original MCP
enumeration assertion now uses LEGACY_TOOLS so the unchanged local configuration
still exposes exactly seven tools. ADR completeness now expects 13 documents.

## Results

| Check | Result |
| --- | --- |
| Full pytest suite | 251 passed, 0 failed, 0 skipped |
| Branch-inclusive coverage | 94.12%; required minimum 92% |
| MCP integration | 15 passed, including STDIO and loopback HTTP regressions |
| New runtime MCP client tests | 9 passed: five tools and four rejection cases |
| Kubernetes adapter + SDK tests | 77 passed |
| Runtime boundary tests | 26 passed |
| Security tests | 57 passed: 19 existing, 12 Kubernetes, 26 runtime boundary |
| Ruff lint / format | PASS |
| Mypy strict | PASS, 64 source files |
| Bandit | PASS; domain enum B105 false positives have local documented suppressions |
| pip install editable with lock constraints / pip check | PASS |
| Original dependency pins | All preserved; FastMCP remains 4.0.5 |
| Kubernetes Python client | 36.0.3, official native asynchronous API |
| Documentation links, ADRs, import boundaries and RBAC examples | PASS |

Counts intentionally overlap: runtime boundary checks also count as security.
Integration totals exclude the four CLI integration tests, which are included in
the full 251. No coverage exclusion was added to reach the threshold.

## Scope and security review

The implementation contains five opt-in tools, environment-scoped Kubernetes
discovery, optional OpenShift Route and optional Namespace/PV/CRD discovery,
explicit custom-resource allowlists, canonical projections, safe connection
health, Event observations, UID-based ownership and bounded topology.
Secret content requested: NO. Secret content exposed: NO. Secret list permission
required: NO. ConfigMap content and arbitrary external text are withheld.
All HTTP operations are read-only; error bodies do not enter results/logs.

Evidence includes pagination, repeated continuation handling, per-category 403
partial results, fatal 401, 404/timeout/unavailability mapping, kubeconfig context
and cluster binding, in-cluster loader, per-instance TLS configuration, scope
spoof rejection, untrusted annotations/events and bounded streaming responses.
API responses never become root-cause findings. Malformed resources cannot add
nodes outside the requested namespace/type. Event output includes effective
limit and actual collection truncation; root status does not consume event slots.

The initial pre-SDK-test coverage gate failed at 85.79% and was resolved by tests
of the actual SDK boundary and MCP execution paths. Installation with
--no-build-isolation found no local setuptools backend; the documented standard
isolated-build installation completed successfully. Neither issue is pending.

## Limitations and deliberately excluded work

No live Kubernetes/OpenShift cluster was contacted. Kubeconfig/in-cluster results
refer to fake loader/SDK tests, not validation of the user's credentials or RBAC.
Optional operator validation is documented separately. No kubeconfig was read,
global SDK configuration changed or cluster resource created during this work.

Snapshots are bounded, non-atomic and uncached. Event order applies to the
collected window, not necessarily the newest events. Exec/auth-provider
kubeconfig credential plugins are unsupported. ConfigMap get/list receives raw
content inside the adapter HTTP boundary, then discards it before canonical output.

No 3scale/APIcast semantics, log analysis, diagnosis engine, root-cause ranking,
remediation, LLM/RAG, Prometheus, cluster deployment, Helm, operator, production
ServiceAccount or external write operation was added.
