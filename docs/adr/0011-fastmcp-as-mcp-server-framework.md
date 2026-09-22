# ADR-0011 — FastMCP as MCP Server Framework

## Status

Accepted — Sprint 1, 2026-09-21.

## Context

Sprint 0 defined transport-neutral contracts. Sprint 1 needs executable MCP
tools, structured schemas, lifecycle and local STDIO/HTTP interoperability.
The repository uses pip/setuptools, not uv. The package index resolved FastMCP
4.0.5 (Requires-Python >=3.10), tested here on Python 3.12.10. Existing packages
were constrained to their Sprint 0 versions during installation; all 99 original
tests passed immediately afterward. requirements.lock records resolved versions.

## Decision

Use standalone `fastmcp==4.0.5`, not the older SDK's similarly named class.

FastMCP SHALL be restricted to the MCP interface layer.

The domain/core layer SHALL NOT depend on FastMCP.

Application services SHALL NOT require FastMCP objects.

Gateway adapters SHALL NOT depend on FastMCP.

Data source adapters SHALL NOT depend on FastMCP.

Evidence, topology and canonical models SHALL NOT depend on FastMCP.

Allowed execution direction: FastMCP -> MCP Interface Layer -> Application
Services -> Domain/Core -> Adapters. The last arrow describes runtime dispatch
through ports, not a dependency from core onto concrete adapters. Bootstrap
composes instances. Internal ExecutionContext extends OperationContext; tools
do not pass FastMCP Context into services. Architecture tests enforce imports.

`python -m agt_mcp serve --file ...` is the single supported launch interface.
STDIO is the development default. HTTP uses Streamable HTTP, loopback only,
strict Host/Origin protection and explicitly configured local read permissions.
No production authentication or externally reachable mode is offered.

## Consequences

FastMCP manages the wire protocol and schemas. Application metadata describes
permissions/capabilities; it does not replace FastMCP's tool registry. Services
own authorization, deadlines and adapter lifecycle. Seven tools use explicit
safe projections and a stable success/error envelope. Resources and prompts
were evaluated and omitted because no current use case needs them.

FastMCP brings transitive dependencies, including the OpenTelemetry API; no
exporter or external telemetry integration is configured. The exact resolver
snapshot is tested on Windows/Python 3.12, not claimed as a universal platform lock.

## Alternatives Considered

Raw SDK: more protocol plumbing without a benefit for this scope. FastMCP in
core/services: couples business contracts to transport and is prohibited.
Premature corporate OAuth or cluster deployment: outside this sprint.

References: [FastMCP 4 GA](https://blog.gofastmcp.com/3mufbh2vcv22o),
[HTTP deployment](https://github.com/PrefectHQ/fastmcp/blob/main/docs/deployment/http.mdx).
Installed package signatures were also inspected before implementation.
