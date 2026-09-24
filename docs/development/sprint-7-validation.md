# Sprint 7 validation — 2026-09-24

Base: 70e1b3d83b61b1a9e17e54f18ee2778463aad6bf. Initial working tree clean.
Targeted baseline: 68 passed. AGENTS.md unchanged. No dependency changes or new
coverage exclusions. Coverage gate raised from 95.5% to 96%.

Final checkpoint validation: PASS.

| Check | Final result |
| --- | --- |
| Unique tests validated | 823 passed, 0 outstanding failures, 0 skipped |
| Previous tests preserved | All 648 |
| New tests | 175 |
| Probe/network/policy/runner/security | 136 passed |
| Trace builder/service units | 28 passed |
| New MCP integration / documentation | 9 passed / 2 passed |
| All MCP integration | 73 passed |
| Branch-inclusive coverage | 97.05%; gate >=96% |
| ProbePolicy coverage | 100% statements and branches |
| Ruff lint / format | PASS / PASS, 255 files |
| Strict mypy | PASS, 119 source files |
| Bandit / dependencies | PASS / PASS |
| Documentation / checkpoint | PASS / PASS |

The complete suite ran once: 822 passed and one documentation checkpoint test failed
because the literal Tests: field was missing. Only the affected documentation/checkpoint
validation was repeated after correction. No application behavior changed afterward.
The Bandit enum-status false positive is locally documented with B105; only Bandit
was repeated for that annotation. Because the annotation moved source lines during
coverage collection, stale measurements for probes/models.py alone were removed and
recollected with 99 focused tests, preserving all other full-run coverage data.
The consolidated coverage above reflects the final source. No exclusion was added.
Focused rechecks: 99 probe tests passed and 3 affected documentation/checkpoint tests
passed. Windows platform/WMI emitted a diagnostic during these runs; the generated
JUnit records confirm zero test failures/errors. Git checks were confirmed separately
in the normal workspace context. No second full-suite execution was performed.

## Scope and architecture

VirtualTrace/TraceHop/TraceRelationship, ProbePlanner, ProbePolicy, ProbeExecutor,
DNS/TCP/TLS/HTTP(S), ProbeEvidence and existing-engine re-evaluation implemented.
Five tools: trace_resource, trace_gateway_component, plan_probes, execute_probe_plan,
explain_trace. ADR-0019 APPROVED. Default: disabled/plan_only.

Targets require operator configuration, scope membership and checksummed provenance.
DNS addresses are all policy-checked and pinned; private/loopback networks require
explicit approval; redirects require exact approved endpoints and fresh policy checks.
No target or serialized plan can be submitted through a tool. Trace explains structural
relationships independently of network observations. TCP/TLS observations do not prove
Redis/DB protocol health or incident causality. Runtime snapshots are not recollected
or relabeled fresh during correlation refresh. Existing evaluator is reused.

## Focused validation

Offline tests cover SSRF aliases/IPv6/metadata, provenance forgery, unsafe URL/path,
redirects, TLS verification stages, controlled local HTTP/TLS, dependency sequencing,
timeouts, budgets, cancellation, bounded concurrency, audited errors, no credentials,
principal/environment caches, permission revocation, missing targets and re-evaluation.
Actual FastMCP Client exercises all five tools, plan_only and rejection paths.
Architecture tests forbid concrete SDK/network/LLM imports in neutral packages.

Previous tests remain present. Existing assertions change only to accommodate ADR-0019
and the additive network hypothesis provider in the enum completeness check.

## Safety results

Arbitrary user target executable: NO. Secret content read: NO.
Credentials sent by probes: NO. Blocked redirect followed: NO.
Write operation executed: NO. Cross-environment target allowed: NO.
Trace core imports concrete network implementation: NO.
Troubleshooting core imports concrete probe implementation: NO. LLM required: NO.
Previous architecture boundaries remain enforced by regression tests.

## Reproduction

During development, only focused tests were executed. Final checkpoint commands:

```text
python -m pytest --cov=agt_mcp --cov-report=term-missing -q --tb=short
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m bandit -r src -q
python -m pip check
git diff --check
```

Local networking uses ephemeral loopback servers; TLS keys/certificates are synthetic,
generated under pytest temporary directories, never application credentials. No public
internet, production cluster, database, Redis or administrative gateway API is contacted.

## Limitations and handoff

Targets must be explicitly configured and associated with scoped canonical resources.
MCP-host vantage point; first approved address only; bounded non-atomic runtime snapshot;
system TLS trust only; absolute configured redirects; no response bodies. OS DNS worker
may finish after cancellation, but late results cannot create a connection. Expiring
in-memory caches; config changes require runtime reconstruction. No production qualification.

Next recommended scope: explicitly authorized Redis/database protocol probes and richer
target mapping, preserving these safety contracts. Authenticated probes, Secret decoding,
Admin APIs, telemetry ingestion, continuous monitoring, writes/remediation and deployment
remain out of scope. No required Sprint 7 item pending.

One commit: feat: add virtual trace and safe probes (Sprint 7).
Resolve containing commit using git log -1 --format="%H %s" -- PROJECT_STATE.md.
