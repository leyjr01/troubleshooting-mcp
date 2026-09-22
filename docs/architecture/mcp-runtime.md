# Sprint 1 — MCP runtime

## Launch and configuration

Install with `python -m pip install -r requirements.lock`, then
`python -m pip install -e ".[dev]" -c requirements.lock`.
The pip snapshot records FastMCP 4.0.5 and all resolved dependencies; the original
Sprint 0 dependency versions were preserved. Snapshot validation platform:
Windows, Python 3.12.10. Re-resolve and review for another platform/Python version.

```bash
python -m agt_mcp serve --file config/server/local.example.yaml
python -m agt_mcp serve --file config/server/local.example.yaml --transport http --port 8000
```

STDIO is the default. HTTP endpoint: `http://127.0.0.1:8000/mcp`.
Stop with Ctrl+C (or close STDIO input). No `fastmcp run` entrypoint is published.
The CLI's offline validate-config/validate-mapping and help remain compatible.
Serve without configured environments fails safely on stderr. No automatic dev,
homolog or prod environments exist. The standalone local example explicitly
declares one synthetic `demo` environment; do not merge it accidentally with
the five historical Sprint 0 blueprints (lists replace, they do not append).

Server configuration lives at `mcp.server`: name, transport, host, port,
log_level, request_timeout_seconds, authorization and enabled_tools. Environment
selection stays in `application.environment`; AGT_ENVIRONMENT still overrides it.
Timeout uses the smaller of application.timeout_seconds and the server deadline.
CLI transport/port override files and are revalidated. File/environment overlays
otherwise use the existing configuration loader. Credentials are never resolved
by in-memory bootstrap. Enabling an unsupported provider fails, never falls back
silently to a mock.

## Security and execution

Authorization defaults to deny-all, empty environments and permissions.
`local-read-only` explicitly trusts the local OS client as `local-client`;
tools cannot choose principal/permissions. This is not remote user authentication.
HTTP binding is restricted to 127.0.0.1 and strict Host/Origin checks are enabled.
Do not publish this local endpoint using a proxy/tunnel. Corporate OAuth, TLS,
OpenShift Route/Ingress and remote access need a separate design and sprint.

Flow: typed tool -> Dispatcher -> internal ExecutionContext -> Runtime authorization
-> service operation -> instance-owned AdapterRegistry -> canonical adapter result
-> explicit safe projection -> ToolResponse. FastMCP only appears inside `mcp/`.
CLI imports the launcher lazily. Services, models and adapters have no SDK imports.
Related small services are grouped in services/runtime.py instead of one file
per tool; tools/inventory.py contains only typed delegation and registration.

Each call generates a unique UUID request_id. A valid UUID correlation_id is
normalized and retained; absent/invalid correlations generate a UUID. Neither
external request strings nor arguments are written to logs. ExecutionContext
contains principal, environment, operation, UTC start_time, monotonic deadline,
limits and internal metadata. No FastMCP Context object is needed by these tools.

Service errors return `ok=false`, stable error category, null data, and execution
IDs. Unknown exceptions become internal_error, never exception text. Cancellation
propagates. Protocol/schema errors use FastMCP's masked MCP errors (before a tool
execution begins); clients should check both MCP is_error and ToolResponse.ok.
Successful responses expose structuredContent with the ToolResponse schema.
Response byte limits reject oversize output. Output DTOs omit credentials,
connection host/port/database, labels, annotations and raw endpoints.

JSON audit logs go to stderr and contain execution IDs, operation, duration,
status and safe error code. Framework diagnostics are reduced to framework_event;
raw tracebacks/arguments are not logged. stdout belongs exclusively to STDIO MCP.

## Registry and lifecycle

ToolDefinition is application governance: name, description, category, required
capabilities/permissions, read_only, enabled and version. Disabled tools are not
registered. list_capabilities filters features, configuration, registered adapter
support and permissions for the authorized environment. There are no evidence,
topology or knowledge capabilities advertised before those features exist.

AdapterRegistry rejects duplicate IDs and cross-environment resolution, and seals
registration on startup. It exposes entries/capabilities through each adapter;
health runs through the application service. Runtime opens adapters during the
FastMCP lifespan and closes them in reverse order on exit or startup failure.
No process-global adapter exists. Supported memory operations: gateway discovery
and health; datasource health only. Query/schema discovery and other gateway
methods fail explicitly as unsupported. Synthetic delay/failure options are
constructor injection for tests, not client-controlled tool arguments.

Inventory status `ready` means initialized, not external gateway health.
Datasource inventory reports unknown until inspected; disabled sources remain
visible as disabled without an instantiated adapter. system_health reports only
this MCP process. All services restrict data by authorized environment.

## Implemented tools

All tools accept optional environment_id and correlation_id. None writes to an
external system. Common side effects are local read-only adapter calls and audit
events. All carry readOnlyHint=true, destructiveHint=false, openWorldHint=false.

| Tool | Inputs beyond common fields | Output | Permissions |
|---|---|---|---|
| system_health | none | process health, version, uptime and scoped counts | system.read |
| list_capabilities | none | effective capabilities and tool governance | capability.read |
| list_environments | none | only configured and granted environments | environment.read |
| list_gateways | none | scoped registered gateway metadata | gateway.read |
| list_datasources | none | safe configured metadata, including disabled sources | datasource.read |
| inspect_datasource | datasource_id | safe metadata and memory health when enabled | datasource.read; datasource.health when enabled |
| discover_gateway | gateway_id | safe projection of canonical mock Gateway | gateway.discover |

Resources/prompts are intentionally absent. The broader Sprint 0 tool catalog
remains a roadmap; only discover_gateway overlaps it, and only with mock data.

## Validation

Run `python -m pytest --cov=agt_mcp --cov-report=term-missing`, Ruff, mypy, Bandit
and pip check as in README. Tests include FastMCP in-memory clients, actual STDIO
subprocesses and actual HTTP over numeric loopback; no external environment is
required. The network fixture permits loopback only for marked transport tests.
Architecture tests reject SDK imports outside mcp/ and MCP-layer imports from
core/services/adapters. Lifecycle, failures, deadlines, cancellation, permission
filters, safe output and Host/Origin protection are tested separately.
