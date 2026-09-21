# ADR-0002 — Modular adapter architecture

## Status

Accepted — Sprint 0, 2026-09-21.

## Context

Múltiplos vendors/fontes não podem contaminar diagnóstico.

## Decision

Portas e adapters, dependência para dentro, instâncias injetadas por ambiente. Pacotes reservados possuem propósito explícito.

## Consequences

Fakes substituem infraestrutura; engines poderão ser implementados sem transporte.

## Alternatives Considered

Monólito específico 3scale aumentaria acoplamento; microserviços são excesso nesta fase.
