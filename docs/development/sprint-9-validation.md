# Sprint 9 validation

## Sprint 9.1 corrective checkpoint

Status: **PASS**. Sprint 9 moves from PARTIAL to PASS after this corrective checkpoint.
Base: `24a6a931bed6898931fc2d64de329213aeefdf87` (Sprint 9 PARTIAL).
Corrective commit: containing commit, resolved by
`git log -1 --format="%H %s" -- PROJECT_STATE.md`.
Impact: MEDIUM; one corrective commit, no new engine, adapter, protocol or ADR.
AGENTS.md unchanged. Only this report and PROJECT_STATE.md documentation updated.

The existing probe-to-correlation mapping now retains typed DNS failure/success,
HTTP server-error/response/timeout and certificate expiry/chain facts. Three missing
declarative network hypotheses feed the same evaluator and candidate promotion.
No free-form log matching or global evidence-source priority was added.
Relevant direct TLS success rejects handshake failure while the preserved TLS log
does not manufacture support; HTTP 500 independently supports the backend candidate.

Explicit current `unresolved_not_found` ConfigMap/Secret links plus current workload
evidence satisfy the existing dependency-reference requirement. Forbidden,
not_observed and stale references do not prove absence. Provenance includes the
original reference and supporting Evidence IDs; no Secret content is accessed.
The existing planner retains target TLS inspection after support and adds distinct
certificate-validity or chain/trust requirements from typed evaluation reason codes.
Expiry recommends review and renewal/replacement through an approved change process;
steps remain read-only descriptions and never execute remediation.

Baseline selected the union of the seven failures and six golden cases once:
**7 FAIL, 2 PASS**, exactly reproducing the original report. Corrected L1:
**7 PASS** with original semantic expectations. Focused rule, probe, contradiction,
temporal and recommendation tests: **93 PASS**, including 33 new negative/boundary
tests. Strict L2: **64 PASS** including **35/35 diagnostic cases, 6/6 golden**, 22
harness controls, aggregate report and six real MCP cases. HTTP 500 and contradictory
evidence both passed through real FastMCP calls. No new scenario category was added.
Six expected-inconclusive cases remain inconclusive; false-positive and false-negative
counts are zero. All seven known-gap allowances were removed; required/forbidden
expectations were not weakened. Golden cases require PASS even without the strict
CLI flag, and the aggregate report now requires zero failures.

Final single complete run: **1,092 PASS, 0 failures/errors/skips**, 259.70 seconds,
exit code 0. All 1,058 baseline tests retained; 34 added (33 focused controls and
one additional MCP case). Unlike the historical Sprint 9 accounting below, this
is one successful complete execution, with strict scenario acceptance enabled:

```powershell
& .\.venv\Scripts\python.exe -m pytest --scenario-acceptance --cov=agt_mcp --cov-fail-under=97 --cov-report=term-missing --cov-report=json:coverage-sprint91.json.tmp --junitxml=sprint91-full.xml.tmp -q --tb=short
```

Coverage **97.38%**, branch-inclusive, passes the corrective >=97% gate; project
minimum >=96% remains unchanged. Rules/catalog/planner are 100% covered; evaluator
99%. No source exclusions or artificial coverage tests were added. Lint PASS,
format PASS (289 files), strict mypy PASS (133 source files), Bandit PASS and pip
check PASS. Existing architecture/security/authorization gates passed in the full
run. No source/test code changed after it; only final documentation numbers.
The three affected documentation/checkpoint checks passed after the final update.

Artifacts: `sprint91-full.xml.tmp`, `coverage-sprint91.json.tmp`,
`sprint91-scenarios.xml.tmp` and the regenerated `sprint9-scenarios.json.tmp`.
All seven fixes, provenance, rejected hypotheses, qualitative confidence,
recommendations, contradiction handling, six inconclusive cases, false-positive
prevention, Secret protection, prompt-injection/SSRF boundaries, environment
isolation, authorization and affected MCP paths PASS. No duplicate diagnosis,
recommendation or evaluation engine; no new architecture decision or ADR.
No mandatory Sprint 9/9.1 item remains pending. The verified containing corrective
commit is the baseline for Sprint 10. The original record below is historical.

Remaining limits: fixture-only qualification; HTTP timeout is an observed request
timeout, not proof of its underlying cause; metadata-only unresolved references;
TLS details require explicit parseable dated/chain facts; Redis/DB protocol causes
remain inconclusive; confidence and candidate scope remain unchanged. Sprint 10
should start from the verified corrective commit.

## Original Sprint 9 record (historical)

Status at original commit: PARTIAL. The validation harness is implemented, but diagnostic acceptance
fails seven scenarios, including four golden cases. Passing regression tests
for the known-gap baseline does not override these failures.

Base commit: `789dd79c95c374b3ab87f6a4e7b2320abb15dac5` (Sprint 8).
Sprint commit: the containing commit; resolve with
`git log -1 --format="%H %s" -- docs/development/sprint-9-validation.md`.
Impact: MEDIUM, unchanged. Existing engine, approved ADRs and AGENTS.md are
unchanged. No dependencies, coverage exclusions, adapters, protocols or MCP tools
were added. No new ADR was needed.

### Original diagnostic results

35 scenarios: **28 PASS, 7 FAIL**. Golden: **2 PASS, 4 FAIL** of 6.
6 expected-inconclusive cases; 0 false-positive assertions; 6 false-negative
assertions and 1 recommendation failure. Counts describe this fixture suite,
not production accuracy or confirmation of incident root causes.

| Failed scenario | Failed semantic assertion | Existing limitation |
| --- | --- | --- |
| dns-failure (golden) | support:DNS_RESOLUTION_FAILURE | No DNS diagnosis definition |
| backend-http-500 (golden) | support:BACKEND_HTTP_ERROR | No HTTP application-error definition |
| backend-timeout | support:BACKEND_TIMEOUT | No backend latency/timeout definition |
| missing-configmap | support:CONFIGURATION_REFERENCE_UNRESOLVED | Missing dependency requirement prevents promotion |
| missing-secret-reference | support:CONFIGURATION_REFERENCE_UNRESOLVED | Same promotion limitation; metadata only |
| contradictory-evidence (golden) | support:BACKEND_HTTP_ERROR | TLS rejected correctly, backend candidate absent |
| tls-expired (golden) | recommend:tls_verification | Supported TLS candidate lacks target-specific validation step |

Passing cases: backend-down (golden), tcp-failure, tls-chain-failure,
service-no-endpoints, route-missing-target, redis-storage-failure (golden),
redis-queues-failure, system-redis-failure, system-database-failure,
apicast-pod-failure, observability-only-support, stale-history,
insufficient-evidence, partial-discovery, active-probes-disabled, provider-failure,
secret-in-log, malicious-annotation, malicious-event, malicious-trace-attribute,
ssrf-attempt, unapproved-target, unauthorized-environment, unauthorized-diagnosis,
large-data, duplicate-evidence, runtime-contradiction and healthy-control.

TLS expiry and chain remain distinct evidence, with a shared generic candidate.
Redis/DB tests validate a TCP candidate on each correctly separated dependency
target and explicitly forbid unsupported protocol-specific conclusions.
Observability enriches evidence without establishing arbitrary causality.
History cannot replace runtime support. LOW/MEDIUM/HIGH behavior is preserved.
Safe recommendations pass; the TLS-specific recommendation acceptance fails.

### Original validation record

Baseline: clean Git at Sprint 8; minimal hypothesis baseline 40 PASS, reused.
L1/L2: 35 scenario contracts plus aggregate report and 22 harness tests passed;
the five real MCP cases passed after correcting the test driver's invocation
of the existing cached-trace interface. Only the four affected MCP cases were
rerun (4 PASS, 1 deselected). Security cases are included in these valid results.
The structured 35-case report is `sprint9-scenarios.json.tmp`; generation reuses
completed results rather than rerunning scenarios.

Final single full regression: 1,023 PASS and 35 failures caused exclusively by
late registration of `--scenario-acceptance` in the nested conftest. All existing
995 tests passed. The diagnostic flow completed in all cases, but their pytest
contract lookup failed. Moved option registration to `tests/conftest.py`; the
affected marker then passed **36 tests, 1,022 deselected** from the repository
root. This includes regenerating its aggregate report. No second full run.

Consolidated by test identity across those two runs: **1,058 PASS, zero remaining
regression failures/errors/skips**, including 63 new tests. This is a consolidated
result, not a claim that the initial full command exited successfully.
Coverage: **97.36%**, branch-inclusive, above unchanged >=96% gate. Source code
did not change after measurement; the repair only relocated a pytest option.
Assertion evaluator and ScenarioRunner: 100% coverage; validation models: 98%.

Strict golden gate was then executed using the corrected root-level option:
**2 PASS, 4 FAIL**, confirming the diagnostic limitations above. These are separate
acceptance failures, not hidden regression successes. The seven full-suite
diagnostic failures remain in the structured report. Acceptance is not PASS.

Ruff lint/format PASS (288 files); affected conftests rechecked after repair.
Strict mypy PASS (133 source files), Bandit PASS, pip check PASS. Existing
architecture, authorization, security and MCP results from the full run remain
valid. Documentation/checkpoint tests rechecked after final documentation updates.
No tests were skipped, no thresholds lowered and no source exclusions added.

Artifacts (ignored, local): `sprint9-full.xml.tmp`,
`sprint9-scenarios-recheck.xml.tmp`, `sprint9-golden.xml.tmp`,
`coverage-sprint9.json.tmp`, `sprint9-scenarios.json.tmp`.
The focused recheck emitted a Windows WMI diagnostic during platform discovery
but completed all selected tests and exited zero; no workaround changed product
or fixture behavior.

### Original acceptance and next work (superseded by Sprint 9.1)

PASS: canonical models, runner, reports, more than 15 scenarios, golden subset,
negative cases, false-positive prevention, evidence/trace provenance, runtime /
VirtualTrace / ProbeEvidence / observability reuse, MCP path, Secret protection,
prompt-injection boundary, SSRF policy and environment/operation authorization.

FAIL: full golden acceptance, complete contradictory-evidence diagnosis,
required candidates in six cases and TLS recommendation in one case.
Contradictory evidence is preserved and TLS rejected; absence of the required
backend candidate prevents marking that critical scenario PASS.

The final rule requiring DNS, TCP, TLS, HTTP 500 and backend-unavailable diagnoses
to be distinguished is not fully met. This checkpoint records the blind spots;
it does not expand the engine or reopen approved confidence/protocol decisions.
Next work should explicitly authorize diagnosis catalog/requirement/recommendation
changes for these failures and then require strict golden acceptance. Live lab
qualification and protocol-specific Redis/DB diagnosis remain outside this sprint.

See [harness commands and interpretation](diagnostic-scenario-harness.md).
