# Security policy

Read-only por padrão: READ, DIAGNOSE, RECOMMEND. Não executar apply/delete/patch,
restart, update de banco, mudança de secret ou remediação automática.
Gateway/resource de tipo Secret revela identidade autorizada, nunca valor.

Least privilege por ambiente: RBAC futuro de get/list/watch apenas em recursos
necessários; logs requerem autorização própria. Banco com usuário SELECT e
schema allowlist; não credenciais administrativas. Sem kubeconfig global herdado
sem escolha explícita. Nenhum acesso externo existe nesta sprint.

No secrets in Git: referências em YAML; valores apenas pelo CredentialProvider,
scoped e allowlisted. Não logar payload, Authorization headers, cookies, passwords,
tokens, API keys, private keys, connection strings ou client secrets.
Sanitizer/Redactor são contratos; implementação conservadora retém só status
enum e contagem limitada, descartando campos desconhecidos e texto livre.
Ela reduz utilidade propositalmente: sanitização produtiva contextual é sprint futura.

Timeout obrigatório, cancelamento cooperativo, limite de logs/itens/bytes.
Proteções de shell/query injection por ausência de execução arbitrária e schemas
restritos; SSRF precisará controles do adapter futuro. Separar dados/instruções:
logs/docs maliciosos nunca escolhem operações, credenciais ou comandos.
Allowlist de leitura e isolamento multi-environment na fronteira de aplicação.

Auditabilidade: request/correlation ID, escopo, adapter, duração, resultado e
categoria segura de erro; IDs não podem ser preenchidos com secrets.
Eventos não incluem mensagens externas, dados pessoais ou stacktrace bruto.
Referências/provenance brutas são internas e devem passar sanitização antes de saída.

Validação local: pytest, Bandit em src, revisão de diff e arquivos staged.
[Threat model](docs/security/threat-model.md) define cobertura e limites.
Para reportar vulnerabilidade, contate o mantenedor por canal privado acordado;
não publique credenciais, dumps ou dados de cliente em issue.
