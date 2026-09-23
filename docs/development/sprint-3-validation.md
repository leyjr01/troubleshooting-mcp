# Sprint 3 validation — 2026-09-23

Base commit: `4b237be663010d6dd7da788b10ea6bdd63fecd92`.
The initial working tree was clean and all 251 baseline tests passed before
implementation. All remain in the final suite; 88 tests were added. The ADR count
and RBAC example count were updated for the newly implemented functionality.

## Results

| Check | Result |
| --- | --- |
| Full pytest suite | 339 passed, 0 failed, 0 skipped |
| Branch-inclusive coverage | 95.23%; required minimum 93%; Sprint 2 baseline 94.12% |
| Classification | 35 passed |
| ThreeScale adapter | 14 passed |
| Semantic topology | 7 passed |
| Semantic application service | 7 passed |
| MCP integration | 25 passed, including 10 new 3scale cases |
| Security | 72 passed, including 15 new 3scale cases |
| Ruff lint / format | PASS; 154 Python files formatted |
| Mypy strict | PASS; 72 source files |
| Bandit | PASS |
| pip check | PASS; no broken requirements |
| 3scale example configuration validation | PASS, offline, credentials not resolved |
| Documentation, ADRs, import boundaries and RBAC | PASS |
| Dependencies / lock file | No dependency or pin changes |

MCP integration excludes four CLI integration tests, which are included in the
full total. Security combines 19 existing security tests, 12 Kubernetes security
tests, 26 runtime boundary tests and 15 3scale security tests. Counts overlap by
design. No coverage exclusion was added to meet the threshold.

Reproduce the principal checks from the repository root:

```powershell
& .\.venv\Scripts\python.exe -m pytest --cov=agt_mcp --cov-report=term-missing
& .\.venv\Scripts\python.exe -m ruff check .
& .\.venv\Scripts\python.exe -m ruff format --check .
& .\.venv\Scripts\python.exe -m mypy
& .\.venv\Scripts\python.exe -m bandit -r src -q
& .\.venv\Scripts\python.exe -m pip check
& .\.venv\Scripts\python.exe -m agt_mcp validate-config --file config/server/threescale.example.yaml
```

## Scope and security evidence

The four gateway MCP tools were exercised through the actual FastMCP client with
a fake canonical RuntimeAdapter. Synthetic Kubernetes objects also pass through
the existing runtime normalization and graph construction, including APIManager,
UID ownership, Service/EndpointSlice/Pod chains and Route relationships.

Tests cover supported, unsupported and unknown versions, missing resources,
partial RBAC, optional/disabled Zync, external System DB/Redis and distinct Backend
Redis roles. Names alone never classify; spoofed labels cannot establish HIGH
confidence. Installation boundaries cover separate namespaces and conflicting
roots in one namespace. Cross-environment snapshots and evidence are rejected.
Snapshot reuse, stable component IDs, deterministic ordering, limits and operation
allowlists are verified. Every semantic edge carries mechanism and provenance.

Secret content read: NO. Secret content exposed: NO. Secret list permission
required: NO. Tests inject fake values for backend-redis, system-redis,
system-database and zync and confirm they never reach responses or logs. Arbitrary
annotations, raw CR content and environment literals remain untrusted and omitted.
The new RBAC example allows only APIManager get/list; it grants no Secret access.
Core imports FastMCP/Kubernetes: NO. Semantic layer imports Kubernetes: NO.
There is no shell, Admin Portal, APIcast management, database or Redis connection
in the semantic implementation. Audit tool completion identifies the 3scale adapter.

## Corrections during validation

Initial configuration regressions involving disabled legacy gateway examples were
corrected while retaining their prior behavior. Formatting issues and the new
audit test's event filter were corrected; runtime_read events have a different
schema from tool_finished events. These are resolved, not pending defects.

Two earlier runs emitted a Windows/Python WMI diagnostic (`0x8007000e`) during
Kubernetes SDK import. Both continued and exited successfully. Later verification
did not reproduce the diagnostic. No global Python, SDK or WMI configuration was
changed to suppress it.

## Limitations and excluded work

No live Kubernetes/OpenShift cluster or user kubeconfig was accessed. Results
validate offline behavior, not production credentials, RBAC or cluster readiness.
The primary expectation profile is 3scale 2.16. Other versions retain conservative
generic discovery; missing trustworthy version metadata produces UNKNOWN. Version
labels and owner references are observations, not cryptographic proof of product
identity. Operator observation means recognized management metadata, not an
operator health check. Secret endpoint identities remain unresolved.

Snapshots remain bounded and non-atomic. Depth 3 exposes the same already-associated
runtime leaves as depth 2. Oversized final envelopes fail safely. See
[discovery contracts](../architecture/threescale-discovery.md) and
[semantic graph rules](../architecture/threescale-semantic-topology.md).

Causal diagnosis, Admin API entities, APIcast management calls, database/Redis
probes, RAG, remediation and deployment are deliberately outside Sprint 3.
No required implementation item is pending.
