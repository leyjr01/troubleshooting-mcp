# ADR-0007 — Data source abstraction

## Status

Accepted — Sprint 0, 2026-09-21.

## Context

Drivers têm protocolos, pooling e retries diferentes.

## Decision

DataSourceAdapter async, Query lógica, SchemaDescription, lifecycle explícito, timeout/cancelamento e erros próprios.

## Consequences

Pooling e retry serão locais ao adapter/ambiente; dados de schema não incluem linhas.

## Alternatives Considered

SQL/HTTP livres no core e conexões globais foram rejeitados.
