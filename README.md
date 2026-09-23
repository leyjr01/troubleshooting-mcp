# API Gateway Troubleshooting MCP

Fundação modular para diagnóstico de gateways. Alvo inicial: Red Hat
3scale/APIcast em OpenShift. Sprint 3 acrescenta classificação e topologia semântica
3scale à descoberta Kubernetes/OpenShift read-only. O servidor FastMCP preserva
STDIO/HTTP local e as ferramentas anteriores. A configuração local original continua em memória.

Resultados e limites verificados: [validação da Sprint 3](docs/development/sprint-3-validation.md).

Sprint 4 adiciona fontes Git locais, documentação curada, incidentes locais,
ingestão sanitizada e cinco ferramentas MCP de conhecimento. O índice em memória
é derivado e reconstruível; a recuperação não produz diagnóstico causal.
Comece por [PROJECT_STATE.md](PROJECT_STATE.md) e pelas
[instruções de ingestão](docs/development/knowledge-ingestion.md).

## Goals e non-goals

Permitir múltiplos ambientes, clusters, gateways e fontes com conclusões
rastreáveis. A integração runtime permite leituras Kubernetes explicitamente
configuradas. Bancos reais, Git remoto, LLMs, remediação e diagnóstico causal
permanecem fora do escopo. Descoberta 3scale não é diagnóstico de troubleshooting.

## Architecture

```text
MCP client -> FastMCP interface -> application services
  query / diagnosis / knowledge -> evidence correlation
  topology / mapping / retrieval -> read-only data access boundary
  RuntimeAdapter | DataSourceAdapter | GatewayAdapter | CredentialProvider
  Kubernetes + optional OpenShift Route | future Git / DB / REST | gateways
```

Core não importa adapters nem bibliotecas de fornecedores. Portas assíncronas,
modelos Pydantic e injeção de dependências, sem singletons de ambiente.
Veja [arquitetura](docs/architecture/overview.md) e [ADRs](docs/adr/README.md).

## Repository layout

- src/agt_mcp/core: modelos, erros e operações.
- gateways/base, datasources/base: contratos; datasources/kubernetes: integração runtime.
- configuration, credentials, security: configuração, resolução explícita de segredos e fronteiras locais.
- evidence, topology: modelos e validação de referências.
- mapping, rag, knowledge: mapeamento de incidentes, fontes e recuperação local; mcp: servidor.
- diagnostics: extensão futura para correlação explícita de evidências.
- observability: eventos JSON sem payload bruto.
- config, mappings: exemplos artificiais; knowledge: convenções para repositórios futuros.
- tests/unit, contract, integration, scenarios, fixtures: validações offline.
- docs: arquitetura, modelos, segurança e desenvolvimento.

## Development setup

Python 3.12+ e Git. No PowerShell, na raiz do checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e ".[dev]" -c requirements.lock
.\.venv\Scripts\python.exe -m agt_mcp --help
```

No Linux/macOS, use python3.12 e .venv/bin/python. Ativação é opcional;
nos comandos seguintes, python representa o executável da .venv.

```bash
python -m agt_mcp validate-config --file config/application.example.yaml --file config/datasources.example.yaml --file config/gateways.example.yaml --file config/rag.example.yaml --file config/diagnostics.example.yaml
python -m agt_mcp validate-mapping mappings/incidents/incident.example.yaml
python -m pytest --cov=agt_mcp
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m bandit -r src -q
python -m pip check
```

CLI retorna 0 no sucesso, 1 para configuração/mapping inválido, 2 para argumentos
inválidos. Não imprime valores de configuração nem resolve credenciais.
Os cinco exemplos da Sprint 0 podem ser validados offline; fontes permanecem desabilitadas.
O comando sem arquivos valida defaults. Configuração de ambiente é fornecida
com --environment-file; veja [configuração](docs/architecture/configuration.md).

Para reproduzir as versões resolvidas, instale `requirements.lock` e use-o como
constraints na instalação editável, conforme [runtime MCP](docs/architecture/mcp-runtime.md).

Iniciar o servidor com dados sintéticos declarados no exemplo:

```bash
python -m agt_mcp serve --file config/server/local.example.yaml
python -m agt_mcp serve --file config/server/local.example.yaml --transport http --port 8000
```

STDIO é o padrão; HTTP atende em `http://127.0.0.1:8000/mcp`. Os comandos de
validação continuam offline. Somente o exemplo local ativa adapters em memória.
Autorização padrão deny-all; o exemplo concede leitura ao cliente do sistema
operacional local. Nenhum modo de acesso remoto está disponível nesta sprint.

## Testing e current status

Fixtures são sintéticas, nenhum teste exige rede. Coverage mínimo configurado
em 94%, com branches e relatório de linhas; cobertura não prova segurança produtiva.
Testes de integração incluem cliente MCP em memória, subprocesso STDIO e HTTP
em loopback. O SDK Kubernetes real usa respostas simuladas nos testes; nenhum
cluster foi acessado durante a validação. A matriz de cenários
descreve expectativas futuras, sem diagnóstico
simulado apresentado como funcionalidade pronta.
[Desenvolvimento](docs/development/testing.md) descreve os checks e suas limitações.
[Validação da Sprint 0](docs/development/sprint-0-validation.md) registra os resultados.
[Validação da Sprint 1](docs/development/sprint-1-validation.md) registra os checks do servidor.
[Validação da Sprint 2](docs/development/sprint-2-validation.md) registra os checks de runtime.

## Kubernetes e OpenShift

Cliente oficial `kubernetes==36.0.3`, com API assíncrona e autenticação kubeconfig
ou in-cluster. Nenhum Secret é lido; somente referências são representadas.
Discovery cluster-scoped é opcional e desabilitado por padrão. A integração
OpenShift acrescenta Routes quando a API está disponível.

Valide [o exemplo](config/server/kubernetes.example.yaml) antes de adaptá-lo a
um contexto existente. Credenciais permanecem fora do repositório.
Veja [runtime discovery](docs/architecture/runtime-discovery.md),
[RBAC](docs/security/kubernetes-rbac.md),
[testes locais](docs/development/kubernetes-local-testing.md) e
[ADR-0012](docs/adr/0012-kubernetes-runtime-discovery.md).

## Security principles

O suporte 3scale tem perfil primário 2.16, com Redis e banco System externos,
Zync configurável e evidência por classificação. Versões desconhecidas ou sem
perfil continuam com warnings e expectativas limitadas. Configure
[threescale.example.yaml](config/server/threescale.example.yaml) para habilitar
discover_gateway, get_gateway_topology, inspect_gateway_component e
get_gateway_dependencies. As tools consultam estrutura e referências; não acessam
Admin Portal, management API, valores de Secrets ou endpoints de banco/Redis.
Veja [discovery 3scale](docs/architecture/threescale-discovery.md),
[topologia semântica](docs/architecture/threescale-semantic-topology.md),
[segurança](docs/security/threescale-data-access.md) e
[fixtures](docs/development/threescale-test-fixtures.md).

READ, DIAGNOSE, RECOMMEND; nenhuma operação de escrita externa.
Autorização e escopo precedem adapters; deadline obrigatório; recomendações
não executáveis. Sanitização inicial remove texto livre e campos desconhecidos.
Não resolve prompt injection por semântica: não há chamada ao modelo.
[SECURITY.md](SECURITY.md), [ameaças](docs/security/threat-model.md).

## Roadmap

1. Sprint 0: fundação, contratos, modelos e governança.
2. Sprint 1: FastMCP, application services, autorização local e adapters em memória.
3. Sprint 2: descoberta Kubernetes/OpenShift, topology e Evidence de observação.
4. Sprint 3: descoberta e topologia semântica 3scale/APIcast.
5. Sprint 4: fontes de conhecimento, mappings de incidentes e RAG local com ACL/provenance.
6. Sprint 5 recomendada: Evidence Correlation Engine, sem remediação automática.
7. Futuro: autenticação corporativa MCP, observabilidade externa e hardening operacional.

Todos os textos do projeto são UTF-8. No Windows PowerShell use
Get-Content -Encoding UTF8 para leitura explícita.
