# Threat model

## v1 release status

Historical sections below describe earlier controls. Current mitigated/accepted/
out-of-scope risks are recorded in the [final security review](../release/security-review.md).
Authenticated HTTP, probes and observability now exist under the approved boundaries.
Production SSO, HA, remediation and live qualification remain outside this release.

## Historical foundation

Sprint 3 adds an evidence-based 3scale classifier over the runtime port. Restricted
APIManager booleans and recognized metadata are projected in the adapter;
names-only detection is rejected and metadata-only candidates cannot receive HIGH.
See [3scale data access](threescale-data-access.md). No new credential or network
boundary is introduced outside the existing Kubernetes runtime.

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
| SSRF | SDK Kubernetes vinculado ao kubeconfig/contexto configurado, TLS obrigatório | Restrição de egress por operador; configuração é entrada privilegiada |
| privilege escalation | ReadOnlyPolicy confere principal, ambiente e operações | Autenticação transport/RBAC Kubernetes/DB least privilege |
| unsafe remediation | Recommendation executable=false | Executor separado com aprovação e auditoria, fora do escopo |
| cross-environment data leakage | Contextos, config e bundle validam escopo | ACL em retrieval/cache/pooling e testes de integração reais |

Bandit e testes são checks de desenvolvimento, não pentest nem garantia de
segurança produtiva. Limites de tamanho não substituem limites no driver.
Conteúdo sanitizado continua não confiável; não elevar a instrução.

## Sprint 2 runtime boundary

O SDK Kubernetes assíncrono usa configuração por ambiente, namespace allowlist,
deadline por chamada e leitura HTTP limitada antes do parse. API errors não
expõem bodies. Tokens, TLS keys, ConfigMap data, annotations, mensagens de Event
e specs arbitrários de CR não cruzam a projeção canônica. Kubeconfig exec e
auth-provider plugins são recusados; nenhuma credencial local foi acessada nos testes.
Secrets não são consultados. O grafo mantém apenas referências provenientes de
workloads/Ingress. ConfigMap get/list recebe conteúdo na fronteira HTTP, que é
descartado; remover esse RBAC é permitido e gera descoberta parcial.

As cinco tools novas têm permissions internas e testes pelo cliente MCP real.
O SDK é exercitado com respostas sintéticas, sem validação contra um cluster
real. RBAC efetivo, configuração confiável e restrições de rede continuam sendo
responsabilidade operacional. Veja [RBAC runtime](kubernetes-rbac.md).
