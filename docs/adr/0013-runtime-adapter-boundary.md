# ADR-0013 — Runtime Adapter Boundary

## Status

APPROVED — Sprint 2, 2026-09-22.

## Context

DataSourceAdapter models generic observations and datasource health. Runtime
discovery additionally needs scoped inventory, canonical topology, resource
identity and structured partial-result reporting.

## Decision

Define RuntimeAdapter in core/runtime.py, separately from DataSourceAdapter.
Its discover/inspect/events/close operations accept ExecutionContext and
RuntimeQuery and return canonical RuntimeSnapshot/RuntimeEvents/Evidence. No SDK or FastMCP
objects enter the port. Bootstrap injects environment-specific implementations.

RuntimeDiscoveryService owns summary and inspection orchestration;
TopologyService computes bounded subgraphs. The inspection responsibility is
co-located in RuntimeDiscoveryService rather than an extra forwarding class.
Connection health is a safe canonical projection of actual API discovery and
per-category read outcomes, returned by discover_environment.

## Consequences

Existing datasource and gateway ports are unchanged. Runtime access requires
separate internal permissions and an enabled environment binding. Services do
not resolve credentials or traverse raw Kubernetes dictionaries. Futures such
as logs, metrics, gateway semantics and diagnostic correlation remain separate.

## Alternatives Considered

- Expanding DataSourceAdapter: forces generic sources to implement topology.
- SDK objects in services: violates vendor independence and projection safety.
- A universal untyped read port: weakens explicit scope and return contracts.
