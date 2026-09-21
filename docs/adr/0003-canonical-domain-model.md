# ADR-0003 — Canonical domain model

## Status

Accepted — Sprint 0, 2026-09-21.

## Context

Evidência, observação e conclusão precisam de identidade e proveniência.

## Decision

Modelos canônicos Pydantic extra=forbid com IDs, timestamps com fuso e referência de ambiente; incident/bundle validam relações.

## Consequences

Schema reproduzível e validação estrutural; conteúdo ainda precisa de segurança e julgamento.

## Alternatives Considered

Dicionários soltos perderiam contrato; classes de SDK vendor vazariam ao core.
