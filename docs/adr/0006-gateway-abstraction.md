# ADR-0006 — Gateway abstraction

## Status

Accepted — Sprint 0, 2026-09-21.

## Context

3scale é o primeiro alvo, não o domínio.

## Decision

GatewayAdapter async usa Resource/Evidence/Dependency canônicos e capabilities, sem método vendor no core.

## Consequences

Novos gateways podem não suportar tudo e devem falhar explicitamente; tracing é leitura passiva.

## Alternatives Considered

Herança do SDK 3scale ou switch por vendor em core acoplaria futuras implementações.
