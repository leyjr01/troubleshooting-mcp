# ADR-0010 — Read-only security model

## Status

Accepted — Sprint 0, 2026-09-21.

## Context

Troubleshooting não deve alterar ambiente nem vazar secrets.

## Decision

Operações allowlisted, principal/ambiente/deadline, recomendações não executáveis, sanitização conservadora e threat model.

## Consequences

Read-only não dispensa RBAC/SSRF/limites nas integrações futuras. Não existe executor nesta sprint.

## Alternatives Considered

Modo admin implícito ou remediação automática seriam incompatíveis com o escopo.
