# Sprint 8 validation — 2026-09-24

Base: 14cbc5f14c5072300180cfe6a31e6aab737bcd2f, initially clean.
Impact: HIGH (external integrations, volume, secret handling and diagnostic evidence).
AGENTS.md unchanged. No dependency changes, coverage exclusions or new ADR.
One logical sprint session, one final commit, no push or production access.

## Validation strategy and current results

Baseline: 29 passed (existing trace service and correlation security).
L1: 39 observability model/redaction/volume tests, 38 service/timeline tests,
47 Prometheus protocol tests, 31 HTTP/TLS/SSRF tests, 8 MCP/composition tests validated.
MCP's strict Python validation initially rejected JSON arrays/timestamps; a strict
JSON boundary converter fixed the interface without weakening validation. Test error
assertions were corrected to match the existing string error contract. Only affected
MCP checks were rerun. Earlier approved work was reused.

L2: 108 passed for changed/new model, service, architecture, documentation and probe
refresh checks. Valid MCP and HTTP/TLS/security results were reused.

Final HIGH checkpoint: PASS.

| Check | Result |
| --- | --- |
| Single full regression | 995 passed, 0 failures/errors/skips; 205.65 seconds |
| Previous tests retained / new tests | 823 / 172 |
| Branch-inclusive global coverage | 97.30%; unchanged gate >=96% |
| L2 focused checkpoint | 108 passed |
| Ruff lint / format | PASS / PASS, 276 files |
| Strict mypy | PASS, 129 source files |
| Bandit / pip check | PASS / PASS |
| Documentation / compact checkpoint | PASS / PASS |
| AGENTS.md / dependencies / coverage exclusions | Unchanged / unchanged / unchanged |

Bandit initially flagged the empty initialization of the credential variable. Using
an explicit `None` sentinel resolved it without suppressions. Only the affected
file's security/type/style checks were repeated before coverage collection. No
Python source changed during or after the single full regression. The final report
and PROJECT_STATE updates received only the affected documentation recheck.
The containing commit is referenced by HEAD in PROJECT_STATE; its hash is reported
after the single sprint commit. No push was performed.

## Acceptance evidence

- Provider-neutral adapter, canonical bounded query, logs/metrics/traces, UTC windows.
- InMemory health/capabilities and 10,000-log deterministic bounded selection.
- Prometheus instant/range internal templates, configurable names, per-resource selectors,
  finite values, wrong-resource rejection, 2,000 sample ordering/dedup and byte limits.
- Actual local HTTP framing and TLS with custom CA, verified host, credential timing,
  exact echoed credential removal including JSON escapes, redirect and DNS blocking.
- Partial source status, environment isolation, signal permissions, cache TTL/principal/
  permission rechecks, invalid window rejection before external access, cancellation.
- Combined runtime/Event/log/metric/trace timeline with provenance and source dedup.
- Four-item Event/log/runtime/ProbeEvidence timeline with correct resource associations.
- Existing evaluator reused; CPU=95 alone produces no root cause candidate.
- Prompt injection stays data; synthetic secrets are absent from Evidence, timeline,
  serialized diagnosis and captured logs. Probes and secret access are not triggered.
- Five actual FastMCP tools; JSON schema rejects backend URLs and raw queries;
  opt-in registration and diagnose/source authorization preserve existing contracts.

Architecture checks prohibit concrete HTTP, Prometheus, FastMCP and Kubernetes imports
in neutral layers and Kubernetes imports in the 3scale semantic layer. Events and
ProbeEvidence reuse the original implementations; no duplicate collector/evaluator.

## Reproduction and limits

Focused tests live in `tests/unit/test_observability_*.py` and
`tests/integration/test_observability_mcp.py`. Final gates: pytest with branch-inclusive
coverage (unchanged >=96% gate), Ruff lint/format, strict mypy, Bandit and pip check.
Global gates are not repeated after PASS unless subsequent changes invalidate them.

No live Prometheus/cluster qualification. Logs/traces are fixture adapters. Metric
names/units/selectors require operator mapping; no generic CPU causality is inferred.
Existing correlation evidence/depth and MCP byte bounds can truncate or reject large
responses. No proxies, redirects, compression, incident store, RAG changes or remediation.
See [architecture](../architecture/observability-correlation.md) and
[security](../security/observability-data-access.md).
