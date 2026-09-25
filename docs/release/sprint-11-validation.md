# Sprint 11 release validation

Base: 0f7ad273ae95924b803e98090cdd05624931d0ca (Sprint 10 PASS).
Impact HIGH. Status PASS. v1.0.0: READY WITH LIMITATIONS, technical preparation only.
AGENTS.md unchanged; no new ADR or troubleshooting capability.

Baseline reused: 1124 PASS / 97.76%, 35 scenarios, six golden.
Minimal Sprint 11 baseline: 67 PASS (configuration/deployment), 1.06s.
Catalog and runtime dependency/license inventory generated from the installed package.
Version now uses package metadata. Audit adds configured principal and hashed
resource/query references; payloads are not logged. Prior security architecture preserved.

Focused release tests: 43 PASS. L2 release checkpoint: 590 PASS, 543 deselected, 132.21s.
All 35 diagnostic scenarios and six golden PASS; existing candidate-provenance and
inconclusive/contradiction assertions retained. Large graph/evidence/telemetry tests
included as sanity checks, no formal performance or memory benchmark.
Wheel/sdist build PASS; isolated install/system_health 1.0.0 PASS.
Wheel contents/metadata PASS; only runtime package and dist-info included.
Documented quickstart PASS through an actual STDIO client. The first attempt exposed
the Windows Store python alias; using sys.executable fixed the documentation.
Only the failed quickstart was repeated, not the approved wheel-content check.
Secret-pattern scan matched 78 files across implementation, docs and intentional
fixtures; high-confidence AWS/private-key patterns found none in src/config/deploy/scripts.
The official-local example attribution was replaced with a reserved .invalid URL,
consistent with the release requirement that examples contain no real endpoints.
Focused/checkpoint collection emitted Windows WMI diagnostics but exited zero;
no product or platform workaround changed test behavior.
Lint/format PASS (314 files); strict mypy PASS (134 source files); Bandit/pip check PASS.
Single final full regression: **1133 PASS**, zero failures/errors/skips, **267.47s**.
All 1124 baseline tests retained; 9 added. Branch-inclusive coverage **97.81%**,
required >=97% PASS. Full regression executed once; no runtime source changed afterward.
Final artifact refresh incorporates documentation/manifest/inventory updates only;
the isolated-install result remains valid for unchanged runtime code and dependencies.
Release status: **READY WITH LIMITATIONS**. No mandatory Sprint 11 item remains pending.
Evidence: sprint11-checkpoint.xml.tmp, sprint11-full.xml.tmp,
coverage-sprint11.json.tmp and the existing runner's sprint9-scenarios.json.tmp.
Artifacts: dist/api_gateway_troubleshooting_mcp-1.0.0.tar.gz,
dist/api_gateway_troubleshooting_mcp-1.0.0-py3-none-any.whl and dist/SHA256SUMS.
Artifacts/evidence stay local and ignored; nothing is published automatically.
Resolve the single containing commit with git log -1 --format="%H %s" -- PROJECT_STATE.md.
Docker/kind/k3d/kubectl/oc remain unavailable; real Kubernetes/OpenShift/3scale and
container execution NOT EXECUTED. This is a non-blocking qualification limitation.

Blockers: failed security/secret/SSRF/authorization/isolation/read-only/RBAC gate,
golden or diagnostic failure, architecture/MCP/deployment failure, package build
failure, test/lint/typecheck failure. No gate may be waived to mark the release ready.
Public distribution additionally needs a maintainer licensing decision; no publish performed.
