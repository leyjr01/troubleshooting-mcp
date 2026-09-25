# Operating and troubleshooting the MCP

Startup: validate the exact ConfigMap content with `python -m agt_mcp validate-config
--file <config>`, then start `python -m agt_mcp serve --file <config> --transport http`.
Offline validation does not resolve credentials; server startup resolves the HTTP
reader credential and fails closed if missing/invalid. Kubeconfig/ServiceAccount
credentials remain lazily loaded for runtime operations. No doctor existed, so
this sprint retains the existing validator, health tools and discovery diagnostics.

Shutdown: send SIGTERM through the orchestrator, allow the configured 45-second
Pod grace, and inspect sanitized lifecycle/audit logs. Do not use liveness to
restart Pods merely because an observed dependency is down. Configuration/token
rotation needs a rollout; hot reload and persistence are not implemented.

| Symptom | Read-only investigation |
| --- | --- |
| Kubernetes API unreachable | Inspect the environment auth mode, API address, mounted CA/token and namespace binding; check egress/DNS and API health externally. Never disable TLS verification. |
| RBAC forbidden | Review Role/RoleBinding in the target namespace and ServiceAccount subject. Missing categories should report PARTIAL; do not grant wildcard/Secret/write permissions. |
| Route API unavailable | Verify this is OpenShift and optional API Role exists. Kubernetes-only environments may legitimately report unavailable. |
| Prometheus unavailable | Check explicitly enabled source, URL/TLS/network policy and resource bindings. Keep the source disabled when absent; other diagnostics continue with limitations. |
| Probe execution disabled | Expected default. Review enabled/execution_mode, application capability and exact endpoint/CIDR policy before opting in. Tool input cannot supply arbitrary URLs. |
| Configuration invalid | Check validator output and schema. Startup errors omit raw exceptions/credentials. Do not bypass authorization to make startup succeed. |
| MCP HTTP 401 | Missing/wrong bearer or credential rotation without restart. Check the secret reference without printing the value. |
| MCP HTTP 403/invalid Host | Use the exact configured service/Route hostname and no untrusted browser Origin. Preserve proxy Authorization; avoid wildcard Hosts. |
| Readiness failing, liveness healthy | Inspect startup configuration and credential availability; initialization must finish. External discovery availability is not part of readiness. |

Audit records contain operation IDs, statuses and safe metadata. Raw framework
exceptions/access logging are suppressed by the existing logging boundary. Keep
credentials out of URLs, shell history, log collectors and support attachments.
Use the [real-lab checklist](../development/real-lab.md) before promoting an image.
