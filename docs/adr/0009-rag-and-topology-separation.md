# ADR-0009 — RAG and topology separation

## Status

Accepted — Sprint 0, 2026-09-21.

## Context

Similaridade documental e conectividade operacional são conceitos diferentes.

## Decision

Retriever/EmbeddingProvider/VectorStoreAdapter isolados; grafo com edges observados e provenance. ACL precede retrieval.

## Consequences

Banco vetorial será substituível; nenhuma ingestão/embedding implementada agora.

## Alternatives Considered

Usar índice vetorial como grafo factual criaria dependências não comprovadas.
