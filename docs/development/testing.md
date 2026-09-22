# Test strategy e observabilidade

Unit: configuração/precedência, modelos, grafo/bundle, mapping, credenciais,
sanitização, política/timeout e erros. Contract: fakes async dos adapters, lifecycle,
capabilities, ausência de escrita. Integration: CLI e composição offline.
Scenario: documentação dos 12 casos futuros; não são testes de diagnóstico já implementado.

Suíte padrão bloqueia rede externa por fixture autouse; somente testes marcados
local_transport permitem resolução de 127.0.0.1 para o HTTP local da Sprint 1.
Também há subprocessos STDIO. Testes não precisam de infraestrutura externa e
não chamam LLM. Fixtures sanitizadas em tests/fixtures.
Coverage branch mínimo 92%; métodos abstratos não são funcionalidade executável.
Documentação validada por seções/links/ADRs/catálogo; isso não avalia correção
semântica automaticamente. Bandit analisa src; não substituir revisão humana.
As supressões locais são justificadas: B506 no loader derivado de
yaml.SafeLoader (testado contra tags Python, aliases e chaves duplicadas);
B105 nos valores de enum SECRET, SECRET_REFERENCE e REFERENCES_SECRET,
que são rótulos de domínio, não senhas.

Sprint 2 adiciona SDK Kubernetes com respostas simuladas e cinco tools exercitadas
pelo cliente MCP. Testes validam RBAC, fronteiras de imports, UID, Secret exclusion,
isolamento, paginação, respostas malformadas e limites de payload. Veja
[testes Kubernetes](kubernetes-local-testing.md) e
[validação Sprint 2](sprint-2-validation.md).

Observabilidade usa AuditEvent validado e emit_event(logger, event), JSON
da biblioteca logging. request_id e correlation_id obrigatórios; duração em ms,
adapter/datasource, status e ErrorCode. Não enviar exception/payload/segredo.
Produtor garante IDs não sensíveis. Futuro MCP STDIO reservará stdout ao protocolo
e logs a stderr. OpenTelemetry traces e métricas Prometheus serão adapters
futuros; evitar labels de alta cardinalidade ou conteúdo de usuário.
