# ADR-0004 — Configuration and secret separation

## Status

Accepted — Sprint 0, 2026-09-21.

## Context

YAML versionado não pode carregar valores de credenciais.

## Decision

Defaults, arquivos, ambiente, env vars e resolução explícita final por CredentialProvider. Só referências em config.

## Consequences

Load é offline e não resolve segredos; provider futuro precisa escopo e rotação próprios.

## Alternatives Considered

DSNs com passwords ou interpolação indiscriminada de segredo em YAML foram rejeitadas.
