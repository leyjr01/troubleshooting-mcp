# Sprint 5 validation — 2026-09-24

Base: ec6211eb986be48c8c54212e3542a4fb2b671ee9. Initial working tree clean.
Targeted baseline: 48 passed. All 448 previous tests are preserved; the sole change
to a previous test is the expected ADR count, from 16 to 17. AGENTS.md is unchanged.
No dependency or coverage exclusion was added. The coverage gate increases to 95%.

## Verification

| Check | Final result |
| --- | --- |
| Full suite | 556 passed, 0 failed, 0 skipped |
| Previous tests | All 448 preserved |
| Correlation tests | 108 passed: 96 unit, 12 integration |
| All MCP integration tests | 49 passed, 0 failed |
| Dedicated security modules | 88 passed, 0 failed |
| Branch-inclusive coverage | 96.34%; gate >=95% |
| Ruff lint / formatting | PASS; 204 files formatted |
| Mypy strict | PASS; 92 source files |
| Bandit / pip check | PASS / PASS |
| Documentation links, ADR structure, checkpoint | PASS |

Counts overlap. Dedicated security modules are test_security (19),
test_kubernetes_security (12), test_threescale_security (15),
test_knowledge_security (31) and test_correlation_security (11). Additional
authorization/cache/configuration cases remain in their respective modules.
MCP integration excludes the four CLI tests, which remain in the full suite.

Mandatory scenarios are covered by executable assertions: Service without ready
endpoints; unavailable Deployment/CrashLoop Pod/recent event; missing Route target;
two historical APIcast 503 incidents with distinct causes; ready-endpoint contradiction;
official 2.16 versus 2.15 knowledge; unknown version; malicious runbook; partial history
failure; environment isolation; multiple installations; mirrored duplicate facts.

FastMCP Client exercises all three tools and strict inputs, permission/operation denials,
environment denials and cache lookup. Unit tests cover principal-scoped cache, permission
revocation, expiry, eviction and byte bounds. A single canonical discovery is reused;
timeline and explanation reads do not call providers again.

Runtime, knowledge and history stay separate. Canonical history preserves original
INC-001/INC-002 IDs, prior cause and remediation. No history or knowledge reference
appears in runtime supporting Evidence. Malicious runbooks/events remain inert text;
credentials are removed or rejected. Topology excludes annotations/details/labels.
Cross-environment source and evidence scope fail closed. Shared resources cannot
bridge installations. Correlation imports no FastMCP, Kubernetes or gateway implementation.

Determinism covers input permutations, duplicate IDs/facts, rule ordering, timeline,
confidence and result identity. Contradicted candidates survive bounded selection.
Original provenance is retained, while engine version and correlated_at are explicit.
Missing/stale/future times cannot silently become current support. Optional source
failures/timeouts preserve runtime results and return PARTIAL; cancellation propagates.
IncidentBundle round trips with optional correlations and unchanged findings/root cause.

Corrections found by tests include long canonical hashes/public attribution URLs being
mistaken for opaque secrets, default windows ending before collection, and category
truncation potentially suppressing contradictions. These are covered by regression tests.

## Reproduction

Use the project Python environment to run:

```text
python -m pytest --cov=agt_mcp --cov-report=term-missing -q --tb=short
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m bandit -r src -q
python -m pip check
```

## Limits and next scope

Validation is offline, using synthetic clusters, local Git/incident/official sources and
local MCP transport. No live cluster or enterprise identity qualification is claimed.
Runtime snapshots remain bounded/non-atomic. Knowledge remains lexical and process-local.
The correlation cache is bounded, per process/principal/environment, nonpersistent;
IDs expire and cannot be shared across workers. Redaction remains pattern-based.
Unresolved references do not prove missing infrastructure or connectivity failure.

No mandatory Sprint 5 work remains. Sprint 6 — Hypothesis &
Troubleshooting Engine — is the next recommended scope. LLM reasoning, causal
Findings, automatic remediation, database probes and persistent correlation storage
are deliberately outside this implementation.
