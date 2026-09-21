# Threat analysis inicial

Trust boundaries: cliente futuro -> autorização -> aplicação -> adapters ->
fontes não confiáveis; segredo -> consumidor autorizado; resultado -> sanitização
-> cliente/LLM; arquivo local -> safe parser. Sem acesso produtivo nesta sprint.

| Ameaça | Controle nesta sprint | Controle futuro / limite |
|---|---|---|
| malicious logs | Texto livre não liberado pelo sanitizer | Parser específico com corpus adversarial |
| malicious documentation | Mesma fronteira de dados não confiáveis | Ingestion ACL, revision e provenance |
| prompt injection | Sem LLM; dados nunca viram instruções executáveis | Separação de mensagens, ferramentas allowlisted e revisão |
| secret leakage | SecretStr, referências, erros seguros, projeção sem payload | Rotação, redaction contextual e política de retenção |
| oversized log payload | Limite de bytes no sanitizer/context | Limitar streaming antes de carregar driver |
| SQL injection | Query lógica e mapping sem expressões | Binding de parâmetros e allowlist de tabelas |
| shell injection | Nenhum subprocess de shell no produto | Preferir APIs e argv fixos; não interpolar comandos |
| SSRF | Nenhum cliente de rede concreto | Hosts/redirects/resolução IP/egress allowlisted por ambiente |
| privilege escalation | ReadOnlyPolicy confere principal, ambiente e operações | Autenticação transport/RBAC Kubernetes/DB least privilege |
| unsafe remediation | Recommendation executable=false | Executor separado com aprovação e auditoria, fora do escopo |
| cross-environment data leakage | Contextos, config e bundle validam escopo | ACL em retrieval/cache/pooling e testes de integração reais |

Bandit e testes são checks de desenvolvimento, não pentest nem garantia de
segurança produtiva. Limites de tamanho não substituem limites no driver.
Conteúdo sanitizado continua não confiável; não elevar a instrução.
