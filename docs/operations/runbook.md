# v1 operations runbook

## Start, stop and health

Validate reviewed config with `python -m agt_mcp validate-config --file CONFIG`.
Start `python -m agt_mcp serve --file CONFIG`; explicit `--transport http` uses
the configured host/port. STDIO stdout is protocol-only; safe logs go to stderr.
Stop with Ctrl+C locally or SIGTERM through the orchestrator; adapter clients
close through the existing lifecycle. Container SIGTERM remains unqualified here.
Default HTTP graceful timeout is 30s and Pod grace 45s.

`system_health` is authorized and reports server/version/status/uptime/configured
environment and registered source counts. `/livez` returns `{"status":"alive"}`;
`/readyz` returns `{"status":"healthy"}` (200) or `{"status":"not_ready"}` (503).
These HTTP endpoints reveal no inventory and require no bearer. External source
failure does not make a initialized MCP process unready; discovery reports source errors.

## Upgrade and rollback

Keep the previous immutable image or wheel plus its reviewed config. Verify SHA256,
install in a new environment, run validate-config and the installed-wheel smoke,
then update the reviewed deployment image. Observe readiness and an authorized
read-only discovery before promoting. Roll back by restoring the prior artifact
and compatible configuration. Do not reuse tokens from public examples. No durable
schema migration exists; process caches and indexes are rebuilt.

## Config, credentials, RBAC and logs

Config is privileged operator input. Unknown fields/duplicate identities fail;
lists replace rather than merge identities. Defaults deny access and disable probes.
Restart for config/token changes. Credentials come from scoped environment variables
or explicit mounted files; never place values in config, CLI arguments or logs.
The reader Role allows get/list of specified kinds only: no write, wildcard or Secret
API grants. Optional OpenShift Role must match the authorized namespace.

Audit JSON includes request_id, correlation_id, principal_id, operation, environment_id,
duration_ms, result_status, error_category and a resource/query reference SHA256.
The fingerprint supports correlation without logging raw selectors or query text;
it is not encrypted storage or permission to include credentials in identifiers.
Outputs retain Evidence provenance. Treat logs as restricted operational data.

## Common failures

| Symptom | Read-only check / action |
|---|---|
| Startup / invalid config | validate-config, required fields, duplicate IDs, exact environment binding |
| HTTP unavailable | host/port, Service/Route Host, TLS termination, reader token, Origin policy |
| 401 | configured token/mount, restart after rotation; never print token |
| RBAC denied | effective reader RoleBinding and namespace; no automatic privilege escalation |
| Kubernetes unavailable | selected context/CA/API connectivity; health can remain healthy |
| Prometheus unavailable | enabled configured source/binding/timeout/network policy; no raw query bypass |
| Probes disabled | expected safe default; separate authorization and approved endpoints required |
| LIMITED/INCONCLUSIVE | inspect missing/stale/contradictory evidence; do not treat as confirmed cause |

See [deployment details](../deployment/operations.md) and [real-lab qualification](../development/real-lab.md).
