# Sprint 6 validation — 2026-09-24

Status: PASS. Base: a3e0c6d7ccaf8fa7d4ecc15a5a1c3235da4528ef.
Initial working tree clean; targeted baseline 90 passed. AGENTS.md unchanged.
Sprint commit: the single containing commit; resolve using
`git log -1 --format="%H %s" -- docs/development/sprint-6-validation.md`.
Subject: feat: add hypothesis troubleshooting engine (Sprint 6).
PROJECT_STATE.md and its compact checkpoint updated. ADR-0018: APPROVED.

## Verification

| Check | Result |
| --- | --- |
| Full suite | 648 passed, 0 failed, 0 skipped |
| Previous tests preserved | YES, all 556; only existing ADR count assertion updated |
| New tests | 92 passed |
| Hypothesis tests | 40 total, 40 passed, 0 failed |
| Troubleshooting service/security tests | 37 total, 37 passed, 0 failed |
| All MCP integration tests | 64 total, 64 passed, 0 failed |
| Dedicated security modules | 112 total, 112 passed, 0 failed |
| Branch-inclusive coverage | 96.65%; configured gate >=95.5% |
| Ruff lint / formatting | PASS / PASS; 226 files |
| Strict mypy | PASS; 104 source files |
| Bandit / pip check | PASS / PASS |
| Documentation and ADR structure | PASS |

Counts overlap: new tests comprise 40 hypothesis, 24 security, 13 service and 15 MCP
cases. Security totals combine previous 88 and new 24 cases. MCP excludes CLI tests.
No dependencies or coverage exclusions were added.

## Architecture and models

One canonical correlation snapshot feeds injected generic/Kubernetes/3scale providers,
deterministic generation/evaluation, supported candidate extraction and safe planning.
Existing correlation contracts have additive typed projections; vendor discovery remains
outside the engine. Runtime, knowledge, history and inference stay separate.

HypothesisCatalog, HypothesisGenerator, HypothesisEvaluator, TroubleshootingEngine: PASS.
HypothesisDefinition, HypothesisInstance, EvidenceRequirement, HypothesisEvaluation,
RootCauseCandidate, TroubleshootingPlan, TroubleshootingResult: PASS.
TroubleshootingContext, TroubleshootingStep, optional IncidentBundle extension: PASS.
Generic, Kubernetes and 3scale sources: PASS (15 definitions).
CANDIDATE, SUPPORTED, REJECTED, INCONCLUSIVE, BLOCKED_BY_MISSING_EVIDENCE: PASS.
Missing/contradicting evidence, deterministic promotion and provenance: PASS.
Confidence LOW / MEDIUM / HIGH: PASS. Structural HIGH is scoped to observed conditions,
not confirmation of the entire incident's root cause (ADR-0018).
Plan: PASS; available inspections read-only; all steps non-executable. Future passive
probe placeholders explicitly report capability unavailable.

## MCP acceptance

| Tool | Result |
| --- | --- |
| diagnose_component | PASS |
| diagnose_gateway | PASS |
| diagnose_api | PASS for mapped runtime resources and explicit LIMITED unmapped response |
| explain_hypothesis | PASS |
| get_troubleshooting_plan | PASS |

Real FastMCP Client tests cover registration, structured responses, permission denial,
strict inputs, isolation and explanation/plan reuse without recollection. Service tests
cover TTL, eviction, byte bounds, principal scope and permission revocation. No actual
3scale Admin API mapping is claimed. There are 28 tools with opt-in registration.

## Mandatory scenarios

- Service without ready endpoints: SUPPORTED/HIGH; ready endpoint: REJECTED.
- External Redis and System database: INCONCLUSIVE, explicit missing probe capability.
- Missing Route Service target: SUPPORTED/HIGH only with completed inventory.
- CrashLoop: supported observed condition, no invented deeper cause.
- Disabled/optional Zync: no false failure; external Redis never requires an internal Pod.
- Historical APIcast incidents and matched documentation: references, not current proof.
- Healthy runtime contradicts historical suggestions; missing evidence is not contradiction.
- Partial RBAC, truncated inventory and absent observations prevent absence-based certainty.
- Malicious runbooks/runtime text inert; invalid lineage/provenance rejected.
- Multiple installations and environments isolated; duplicated facts do not inflate confidence.
- Unknown versions limit specialized hypotheses; multiple supported candidates retained.
- No data for applicable subjects yields missing evidence and inspection plans.
- User-reported and runtime-observed symptoms have distinct origin and evidence linkage.

## Boundaries and safety

Environment isolation, multi-installation isolation, prompt injection boundary: PASS.
Core imports FastMCP: NO. Core imports Kubernetes client: NO.
ThreeScale semantic layer imports Kubernetes client: NO.
Core imports Git implementation: NO. Core imports vector vendor: NO.
Correlation core imports ThreeScale implementation: NO.
Troubleshooting core imports ThreeScale implementation: NO. LLM required: NO.
History alone confirms root cause: NO. Knowledge alone confirms root cause: NO.
External dependency without probe confirmed failed: NO.
Secret exposed: NO. Credential exposed: NO. External content executed: NO.
External write executed: NO. Cross-environment leak: NO.

## Reproduction and limitations

Use the project's Python environment:

```text
python -m pytest --cov=agt_mcp --cov-report=term-missing -q --tb=short
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m bandit -r src -q
python -m pip check
git diff --check
```

Offline validation with simulated cluster responses; bounded non-atomic snapshots,
pattern-based redaction, lexical references and process-local caches. Structural proof
does not confirm end-to-end incident causality. Unmapped APIs return LIMITED.
No live production qualification is claimed.

Missing next capabilities: virtual trace and explicit DNS/TCP/TLS/HTTP/Redis/database
probe foundations with separate permissions and safety policy in Sprint 7.
Pending mandatory Sprint 6 items: none. Deliberately excluded: actual probes, active
execution, remediation, LLM diagnosis, remote Git and live DB/Admin API access.
Checkpoint records capabilities, ADR, bounds, safety, test totals and Sprint 7 handoff.
Final Git verification requires exactly one sprint commit, unchanged AGENTS.md and a
clean working tree; the resulting commit hash is reported to the user.
