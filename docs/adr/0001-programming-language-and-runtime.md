# ADR-0001 — Programming language and runtime

## Status

Accepted — Sprint 0, 2026-09-21.

## Context

É necessário validar contratos tipados com pouco peso e testes locais.

## Decision

Python 3.12+, Pydantic 2, PyYAML seguro, pytest/cov, Ruff, mypy e Bandit. Logging e async pela biblioteca padrão; SDK MCP adiado ao transporte.

## Consequences

Há dependências de validação, mas nenhum driver/LLM. Exigir typing e limites na fronteira.

## Alternatives Considered

Dataclasses puras exigiriam validação manual; framework web/ORM seria prematuro.
