# Sprint 4 validation — 2026-09-23

Base: ca83d25. Initial working tree clean; targeted baseline: 75 passed.
All 339 prior tests are preserved. The only prior test assertion changed is the
ADR count, from 14 to 16. No coverage exclusion or dependency pin was changed.

## Final results

| Check | Result |
| --- | --- |
| Full suite | 448 passed, 0 failed, 0 skipped |
| Branch-inclusive coverage | 95.87%; gate >=94%; previous baseline 95.23% |
| Knowledge unit tests | 97 passed |
| Pipeline / retrieval / source tests | 17 / 11 / 12 passed |
| Mapping and knowledge configuration | 24 passed |
| Knowledge security | 31 passed |
| Workflow checkpoint and examples | 2 passed, included in knowledge unit count |
| MCP integration | 37 passed, including 12 knowledge cases |
| Combined security category | 103 passed |
| Ruff lint / formatting | PASS |
| Mypy strict | PASS, 83 source files |
| Bandit | PASS |
| pip check | PASS; no dependency changes |
| Documentation links / ADR structure / checkpoint | PASS |

Counts overlap: security is the previous 72 plus 31 knowledge security tests.
MCP integration excludes four CLI tests, which remain in the full total.
Knowledge unit count includes pipeline, retrieval, sources, mapping, security and
checkpoint tests; the 12 knowledge MCP tests bring all additions to 109.

## Verification evidence

Temporary real Git repositories validate pinned commit snapshots, branch selection,
subpath/includes, ignored uncommitted changes and new/changed/unchanged/deleted files.
Unchanged refresh makes no embedding calls. Rebuild preserves reproducible chunk IDs.
Missing refs, oversized files, excessive counts and invalid documents fail closed.
Failed refresh preserves the prior complete index/manifest. Source freshness reports
HEALTHY, NOT_INDEXED, STALE, DEGRADED and UNAVAILABLE as applicable.

All five tools are exercised through the actual FastMCP client. Tests verify JSON
array filters, product/version filters, source categories, permissions, operation
allowlists, environment denials, safe audit and structured provenance. Existing
STDIO/local HTTP, runtime and 3scale tests continue to pass.

Synthetic INC-001 and INC-002 share APIcast 503 symptoms with different historical
causes. Both return as similar prior incident, without generating a Finding or
confirming a current root cause. Mappings retain canonical Incident, discard
unmapped private fields and reject SQL-shaped table identifiers and scope overrides.
Schema inspection returns mapped columns without incident row values.

Secrets/private keys/connection credentials and emails are removed before indexing.
Git remote URL credentials are never copied into the index or logs. A malicious
runbook remains inert text. PROD document data does not appear in DEV/demo retrieval.
No Secret contents, real DB credentials, external HTTP or paid model calls are used.
Core/semantic import boundaries remain intact. Knowledge is not runtime Evidence.

Corrections during validation: strict MCP JSON arrays required explicit canonical
conversion; URL sanitization now examines individual URL components to avoid
rejecting legitimate long documentation paths; production assert statements were
replaced with explicit checks/accurate return types after Bandit findings. All are
resolved in the final suite. No security suppression was added for these findings.

## Reproduction

```powershell
& .\.venv\Scripts\python.exe -m pytest --cov=agt_mcp --cov-report=term-missing
& .\.venv\Scripts\python.exe -m ruff check .
& .\.venv\Scripts\python.exe -m ruff format --check .
& .\.venv\Scripts\python.exe -m mypy
& .\.venv\Scripts\python.exe -m bandit -r src -q
& .\.venv\Scripts\python.exe -m pip check
```

## Scope and limitations

Sources are local clones, curated official snapshots and fictional incident rows.
There is no remote clone/fetch/authentication, live database, live documentation
fetch, production vector backend or trained embedding model. The serving Runtime
must receive explicit programmatic refresh; the default CLI starts with an empty
index. Indexes/manifests are in memory and rebuild after restart. Redaction is
pattern-based and cannot guarantee detection of every secret or personal name.

Implementation and limits: [ingestion guide](knowledge-ingestion.md),
[source contracts](../architecture/knowledge-sources.md),
[trust boundary](../security/knowledge-trust-boundary.md).
No paid embedding service, live HTTP, real database or production cluster is used.

No mandatory Sprint 4 item is pending. Causal correlation, LLM diagnosis, remediation,
deployment and live operational probes are deliberately outside this sprint.

The checkpoint is [PROJECT_STATE.md](../../PROJECT_STATE.md). Its Commit field uses
the containing commit reference: embedding a commit's own hash in its tracked
contents is self-referential. The final response records the resulting hash; the
next sprint verifies Git HEAD and the checkpoint's expected subject/base.
