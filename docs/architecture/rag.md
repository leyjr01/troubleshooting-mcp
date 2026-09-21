# RAG federado e separação do runtime

Fluxo futuro: document ingestion -> chunking -> metadata -> embedding -> index ->
retrieval -> reranking -> citation/provenance. Nenhuma etapa concreta agora.
Fontes candidatas: Git, Incident DB, CMDB, documentação oficial, runbooks,
arquitetura e bundles históricos. Cada chunk tem id, ambiente, ACL/access_labels,
revision e Provenance. Sem ACL default universal e sem indexar secrets.

EmbeddingProvider, VectorStoreAdapter e Retriever são Protocols async.
VectorStoreAdapter expõe somente search nesta sprint; ingestão/escrita de índices
é processo futuro separado do diagnóstico read-only. Embeddings são vetores
numéricos, não confiança de diagnóstico. Backend vetorial não aparece no core.
Filtrar permissão/ambiente ANTES da recuperação e depois conferir na composição;
preservar citações e versões. Reranking não autoriza dados novos ou cria prova.
Documento/log é dado não confiável, não instrução. Sanitização deve preceder
saída ao modelo; nenhuma chamada LLM existe aqui.
