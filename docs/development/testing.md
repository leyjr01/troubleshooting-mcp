# Test strategy e observabilidade

Unit: configuração/precedência, modelos, grafo/bundle, mapping, credenciais,
sanitização, política/timeout e erros. Contract: fakes async dos adapters, lifecycle,
capabilities, ausência de escrita. Integration: CLI e composição offline.
Scenario: documentação dos 12 casos futuros; não são testes de diagnóstico já implementado.

Suíte padrão impede socket real por fixture autouse. Testes não precisam de
infraestrutura e não chamam LLM. Fixtures sanitizadas em tests/fixtures.
Coverage branch mínimo 80%; métodos abstratos não são funcionalidade executável.
Documentação validada por seções/links/ADRs/catálogo; isso não avalia correção
semântica automaticamente. Bandit analisa src; não substituir revisão humana.
As duas supressões locais são justificadas: B506 no loader derivado de
yaml.SafeLoader (testado contra tags Python, aliases e chaves duplicadas);
B105 no valor de enum ResourceKind.SECRET, que não é uma senha.

Observabilidade usa AuditEvent validado e emit_event(logger, event), JSON
da biblioteca logging. request_id e correlation_id obrigatórios; duração em ms,
adapter/datasource, status e ErrorCode. Não enviar exception/payload/segredo.
Produtor garante IDs não sensíveis. Futuro MCP STDIO reservará stdout ao protocolo
e logs a stderr. OpenTelemetry traces e métricas Prometheus serão adapters
futuros; evitar labels de alta cardinalidade ou conteúdo de usuário.
